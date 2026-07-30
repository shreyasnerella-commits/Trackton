"""
agenttrace.tracer
-------------------
The core @trace_agent decorator. This is the SDK's main surface.

Key design decisions:

1. contextvars, NOT globals or thread-local dicts.
   Agents can call each other in nested/concurrent ways (including
   async code). contextvars.ContextVar correctly isolates
   trace_id/parent_span_id/depth per logical call chain, so two
   concurrent traces never corrupt each other's parent/depth info.
   A plain global variable WOULD corrupt state under concurrency.

2. depth and parent_span_id are set BEFORE calling the wrapped
   function, and reset in a `finally` block after -- this is what
   makes nested @trace_agent calls automatically link to their caller
   and increment depth, with zero manual wiring needed by whoever
   writes the agent code.

3. Token counting, latency, and status are all captured even when the
   wrapped function raises an exception or times out (the SDK "Trap").

4. check_circuit_breaker() is a stub for now (Phase E3). Member 2 will
   supply the real implementation (or an HTTP call to their endpoint).
   The control flow -- raising CircuitBrokenError when tripped -- is
   already correct and won't need to change when that lands.
"""

import contextvars
import functools
import time
import uuid
from typing import Callable, Optional

from . import emitter
from .hashing import compute_signature, truncate_input_preview
from .token_counter import estimate_tokens, extract_real_usage

# --- Context state: isolated per logical call chain, safe under concurrency ---
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)
_parent_span_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("parent_span_id", default=None)
_depth_var: contextvars.ContextVar[int] = contextvars.ContextVar("depth", default=0)


class CircuitBrokenError(Exception):
    """Raised when the Anomaly Engine has flagged this signature as looping
    and the run must halt before burning more budget."""
    pass


def check_circuit_breaker(signature: str) -> bool:
    """
    STUB -- Member 2 owns the real logic.

    Later this will either:
      (a) be swapped for a direct import of Member 2's detector function, or
      (b) call Member 2's /api/circuit-check endpoint.

    Returns True if this signature should halt execution, False otherwise.
    Currently always returns False so the SDK is fully testable standalone.
    """
    return False


def get_current_trace_id() -> Optional[str]:
    """Useful for demo scripts that want to print/group traces manually."""
    return _trace_id_var.get()


def trace_agent(agent_id: str, tool_name: str):
    """
    Decorator factory. Usage:

        @trace_agent(agent_id="researcher", tool_name="web_search")
        def search(query: str):
            ...

    Emits one span per call, capturing tokens/latency/depth/status, and
    raises CircuitBrokenError if the anomaly engine flags this call's
    signature as a detected loop.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            span_id = str(uuid.uuid4())

            # If no trace is active yet, this call starts a brand new trace.
            trace_id = _trace_id_var.get()
            is_root = trace_id is None
            if is_root:
                trace_id = str(uuid.uuid4())

            parent_span_id = _parent_span_id_var.get()
            depth = _depth_var.get()

            signature = compute_signature(agent_id, tool_name)

            # Circuit breaker check BEFORE doing any real work / spending tokens.
            if check_circuit_breaker(signature):
                span = _build_span(
                    trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id,
                    agent_id=agent_id, tool_name=tool_name, signature=signature,
                    input_preview=truncate_input_preview((args, kwargs)),
                    depth=depth, prompt_tokens=0, completion_tokens=0,
                    latency_ms=0.0, status="CIRCUIT_BROKEN",
                    error_message="Halted before execution: loop signature detected",
                    started_at=emitter.now_iso(), ended_at=emitter.now_iso(),
                )
                emitter.emit_span(span)
                raise CircuitBrokenError(
                    f"Circuit broken for agent={agent_id} tool={tool_name} "
                    f"(signature={signature[:8]}...) -- possible infinite loop."
                )

            # Rough pre-call token estimate from stringified args (Trap fix).
            input_text = truncate_input_preview((args, kwargs), max_len=4000)
            prompt_tokens_estimate = estimate_tokens(input_text)

            # Push this call's context down for any NESTED @trace_agent calls.
            token_trace = _trace_id_var.set(trace_id)
            token_parent = _parent_span_id_var.set(span_id)
            token_depth = _depth_var.set(depth + 1)

            start_time = time.time()
            started_at = emitter.now_iso()
            status = "SUCCESS"
            error_message = None
            result = None
            completion_tokens = 0
            prompt_tokens = prompt_tokens_estimate

            try:
                result = func(*args, **kwargs)

                # Trap fix: override the estimate with real provider usage
                # if the return value looks like an API response object.
                real_usage = extract_real_usage(result)
                if real_usage:
                    if real_usage.get("prompt_tokens") is not None:
                        prompt_tokens = real_usage["prompt_tokens"]
                    if real_usage.get("completion_tokens") is not None:
                        completion_tokens = real_usage["completion_tokens"]
                else:
                    # No usage object found -- estimate completion tokens
                    # from the stringified result as a last resort.
                    completion_tokens = estimate_tokens(truncate_input_preview(result, max_len=4000))

                return result

            except Exception as exc:
                status = "ERROR"
                error_message = str(exc)
                raise

            finally:
                latency_ms = round((time.time() - start_time) * 1000, 3)
                ended_at = emitter.now_iso()

                span = _build_span(
                    trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id,
                    agent_id=agent_id, tool_name=tool_name, signature=signature,
                    input_preview=input_text, depth=depth,
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    latency_ms=latency_ms, status=status, error_message=error_message,
                    started_at=started_at, ended_at=ended_at,
                )
                emitter.emit_span(span)

                # Restore context so siblings/parent see the correct state.
                _trace_id_var.reset(token_trace)
                _parent_span_id_var.reset(token_parent)
                _depth_var.reset(token_depth)

        return wrapper

    return decorator


def _build_span(*, trace_id, span_id, parent_span_id, agent_id, tool_name,
                 signature, input_preview, depth, prompt_tokens, completion_tokens,
                 latency_ms, status, error_message, started_at, ended_at) -> dict:
    """
    Assembles a span dict matching Member 3's SpanIngestPayload pydantic
    model EXACTLY:

        class SpanIngestPayload(BaseModel):
            trace_id: UUID
            span_id: UUID
            parent_span_id: Optional[UUID] = None
            agent_id: str
            tool_name: str
            input_hash: str
            prompt_tokens: int = 0
            completion_tokens: int = 0
            latency_ms: float
            depth: int = 0
            status: str = "SUCCESS"
            metadata: Optional[Dict[str, Any]] = {}

    Only the fields that exist as real columns on the backend's model go
    top-level. Everything else useful for debugging (input_preview,
    error_message, started_at, ended_at) is nested under `metadata`,
    which the backend stores as a free-form JSON/JSONB column and
    SpanNode later re-exposes as `metadata` in the tree response.
    """
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "agent_id": agent_id,
        "tool_name": tool_name,
        "input_hash": signature,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "depth": depth,
        "status": status,
        "metadata": {
            "input_preview": input_preview,
            "error_message": error_message,
            "started_at": started_at,
            "ended_at": ended_at,
        },
    }
