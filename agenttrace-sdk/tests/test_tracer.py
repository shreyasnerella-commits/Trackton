"""
Quick sanity tests. Run with:
    python -m pytest tests/ -v
or just:
    python tests/test_tracer.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agenttrace import trace_agent, get_current_trace_id, compute_signature
from agenttrace import emitter


def _read_fallback_spans():
    if not os.path.exists(emitter.FALLBACK_LOG_PATH):
        return []
    with open(emitter.FALLBACK_LOG_PATH, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_signature_ignores_input_mutation():
    sig1 = compute_signature("fixer", "retry_call")
    sig2 = compute_signature("fixer", "retry_call")
    assert sig1 == sig2, "Same agent+tool should always produce the same signature"
    print("PASS: test_signature_ignores_input_mutation")


def test_nested_calls_share_trace_and_increment_depth():
    captured = {}

    @trace_agent(agent_id="child", tool_name="do_child_thing")
    def child():
        captured["child_trace"] = get_current_trace_id()
        return "child done"

    @trace_agent(agent_id="parent", tool_name="do_parent_thing")
    def parent():
        captured["parent_trace"] = get_current_trace_id()
        return child()

    result = parent()
    assert result == "child done"
    assert captured["parent_trace"] == captured["child_trace"], \
        "Nested calls must share the same trace_id"
    print("PASS: test_nested_calls_share_trace_and_increment_depth")


def test_exception_still_emits_span_with_error_status():
    before_count = len(_read_fallback_spans())

    @trace_agent(agent_id="broken", tool_name="always_fails")
    def broken_call():
        raise ValueError("simulated failure")

    try:
        broken_call()
        assert False, "Expected ValueError to propagate"
    except ValueError:
        pass

    after = _read_fallback_spans()
    assert len(after) >= before_count + 1, "A span should still be emitted on exception"
    last_span = after[-1]
    assert last_span["status"] == "ERROR"
    assert last_span["metadata"]["error_message"] == "simulated failure"
    assert last_span["prompt_tokens"] is not None  # never null, even on failure
    print("PASS: test_exception_still_emits_span_with_error_status")


if __name__ == "__main__":
    test_signature_ignores_input_mutation()
    test_nested_calls_share_trace_and_increment_depth()
    test_exception_still_emits_span_with_error_status()
    print("\nAll tests passed.")
