import functools
import time
import hashlib
import httpx
import tiktoken

# 1. Custom Exception for Circuit Breaker
class TracktonCircuitBreakerException(Exception):
    """Raised when Trackton halts execution due to loops or high token usage."""
    pass


# 2. Token Counting & Hashing Helpers
def count_tokens(text: str) -> int:
    """Estimates token count for text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(str(text)))
    except Exception:
        # Fallback heuristic (~4 chars per token)
        return max(1, len(str(text)) // 4)

def generate_signature(agent_name: str, tool_name: str, inputs: str) -> str:
    """Creates a SHA256 hash signature for (Agent + Tool + Input)."""
    raw_string = f"{agent_name}:{tool_name}:{inputs}"
    return hashlib.sha256(raw_string.encode('utf-8')).hexdigest()


# 3. Core Decorator
def trace_agent(agent_name: str, tool_name: str):
    """Decorator to measure timing, tokens, signatures, and mock telemetry."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Record start time and inputs
            start_time = time.perf_counter()
            inputs_str = str(args) + str(kwargs)
            prompt_tokens = count_tokens(inputs_str)
            sig_hash = generate_signature(agent_name, tool_name, inputs_str)
            
            print(f"\n[Trackton SDK] 🛰️ Intercepted call to '{tool_name}' by '{agent_name}'")
            print(f"  ├─ Signature Hash: {sig_hash[:12]}...")
            print(f"  ├─ Estimated Prompt Tokens: {prompt_tokens}")
            
            # Execute original function
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                print(f"  └─ ❌ Function raised error: {e}")
                raise e

            # Record completion details
            end_time = time.perf_counter()
            latency_ms = round((end_time - start_time) * 1000, 2)
            completion_tokens = count_tokens(str(result))

            print(f"  ├─ Latency: {latency_ms} ms")
            print(f"  ├─ Completion Tokens: {completion_tokens}")

            # Construct Telemetry Payload
            telemetry_payload = {
                "agent_name": agent_name,
                "tool_name": tool_name,
                "inputs": inputs_str,
                "outputs": str(result),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "signature_hash": sig_hash
            }

            # Dispatch Telemetry
            _send_telemetry(telemetry_payload)

            return result
        return wrapper
    return decorator


def _send_telemetry(payload: dict):
    """
    Simulates receiving circuit breaker feedback from Member 2/3.
    """
    # If the backend flags a loop, halt execution immediately!
    if payload.get("is_loop_detected"):
        print("  └─ 🚨 CIRCUIT BREAKER TRIPPED! Infinite loop detected.")
        raise TracktonCircuitBreakerException("Execution halted by Trackton: Infinite delegation loop detected.")
    
    print("  └─ 🚀 Telemetry successfully dispatched to backend!")