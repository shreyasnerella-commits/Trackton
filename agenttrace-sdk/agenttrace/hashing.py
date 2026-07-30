"""
agenttrace.hashing
-------------------
Generates the "loop signature" used by the Anomaly Engine (Member 2) to
detect infinite delegation loops.

IMPORTANT DESIGN DECISION (per team spec):
We hash ONLY (agent_id + tool_name), NOT the raw input.

Why: if we hashed the full input, a loop like:
    "search: weather"
    "search: weather, retrying because error: timeout"
    "search: weather, retrying again because error: timeout, timeout"
would produce 3 DIFFERENT hashes even though it's clearly the same
recursive loop with a slightly mutated prompt each time. Hashing just
(agent_id + tool_name) means Member 2's engine can catch this by
counting how many times this exact signature repeats in a rolling
window, regardless of what the input text says.
"""

import hashlib


def compute_signature(agent_id: str, tool_name: str) -> str:
    """
    Returns a stable sha256 hex digest for a given (agent, tool) pair.

    This value goes into the 'input_hash' field of every span. Member 2's
    cycle-detection engine will count repeats of this exact string across
    a rolling window of recent spans within the same trace_id.
    """
    if not agent_id or not tool_name:
        raise ValueError("agent_id and tool_name are required to compute a signature")

    raw = f"{agent_id.strip().lower()}:{tool_name.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def truncate_input_preview(value, max_len: int = 200) -> str:
    """
    Produces a short, safe string preview of whatever was passed into the
    tool call, for debugging in the dashboard. This is NOT used for hashing
    (see compute_signature) -- it's purely for humans reading the trace.
    """
    try:
        text = value if isinstance(value, str) else repr(value)
    except Exception:
        text = "<unrepresentable input>"

    if len(text) > max_len:
        return text[:max_len] + "...(truncated)"
    return text
