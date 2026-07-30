# AgentTrace SDK (Member 1 — Telemetry Collector Wrapper)

Lightweight, non-intrusive Python decorator that wraps agent/tool calls
and emits structured telemetry spans for the AgentTrace observability
platform.

## Install

```bash
cd agenttrace-sdk
pip install -r requirements.txt
```

## Quick usage

```python
from agenttrace import trace_agent

@trace_agent(agent_id="researcher", tool_name="web_search")
def search(query: str):
    ...  # your actual agent/tool logic, e.g. an LLM or API call
    return result
```

Every call to `search(...)` automatically emits a span like:

```json
{
  "trace_id": "b6b6...",
  "span_id": "9f21...",
  "parent_span_id": null,
  "agent_id": "researcher",
  "tool_name": "web_search",
  "input_hash": "3a5c...",
  "prompt_tokens": 42,
  "completion_tokens": 128,
  "latency_ms": 812.4,
  "depth": 0,
  "status": "SUCCESS",
  "metadata": {
    "input_preview": "((<args>,), {<kwargs>})",
    "error_message": null,
    "started_at": "2026-07-30T10:12:03.001Z",
    "ended_at": "2026-07-30T10:12:03.813Z"
  }
}
```

This shape is validated to match Member 3's real `SpanIngestPayload`
pydantic model 1:1 — top-level fields are exactly the model's declared
fields, and anything not a real backend column (`input_preview`,
`error_message`, `started_at`, `ended_at`) is nested under `metadata`,
which the backend stores as a JSON/JSONB column. `status` is always
uppercase (`SUCCESS` / `ERROR` / `CIRCUIT_BROKEN`) to match backend
convention.

## Where spans go

By default spans POST to `http://localhost:8000/api/telemetry`
(Member 3's FastAPI endpoint). Override with:

```bash
export AGENTTRACE_ENDPOINT="http://localhost:8000/api/telemetry"
```

If the backend isn't running or the request fails, spans are written
locally to `agenttrace_spans.jsonl` instead — nothing is ever silently
dropped, and this means the SDK works completely standalone before the
backend exists.

## Run the demos

```bash
python demo/happy_path.py
python demo/infinite_loop_path.py
cat agenttrace_spans.jsonl
```

- `happy_path.py` — 3 clean nested agent calls, proves trace_id/depth/
  parent_span_id chaining works.
- `infinite_loop_path.py` — an agent that calls itself repeatedly with
  a mutated prompt each time, proving that hash-based
  (agent_id + tool_name) loop signatures catch recursive loops even
  when the raw input text changes every call.

## Run tests

```bash
python tests/test_tracer.py
```

## Notes for the rest of the team

- **Member 2 (Anomaly Engine):** `agenttrace/tracer.py` has a stub
  `check_circuit_breaker(signature)` that currently always returns
  `False`. Replace its internals (or point it at your endpoint) —
  the `CircuitBrokenError` control flow around it is already correct
  and tested (`tests/test_tracer.py`).
- **Member 3 (Backend):** the exact span shape you'll receive on
  `POST /api/telemetry` is in `agenttrace/tracer.py::_build_span`.
  Match your `spans` table columns to it 1:1.
- **Member 4 (Dashboard):** `depth` and `parent_span_id` are already
  computed by the SDK — you should never need to reconstruct the tree
  client-side from scratch, just group by `trace_id` and sort by
  `depth`/`started_at`.
