# tests/test_anomaly.py
import pytest
from backend.app.anomaly import AnomalyEngine


def test_tool_signature_order_independence():
    engine = AnomalyEngine()

    args1 = {"user": "alice", "action": "search", "query": "trackton"}
    args2 = {"query": "trackton", "user": "alice", "action": "search"}

    hash1 = engine.generate_tool_signature("search_tool", args1)
    hash2 = engine.generate_tool_signature("search_tool", args2)

    assert hash1 == hash2


def test_infinite_loop_detection():
    engine = AnomalyEngine(threshold=3)
    tool = "query_db"
    args = {"sql": "SELECT * FROM telemetry;"}

    # First two calls should not trigger loop detection
    assert not engine.check_for_infinite_loop(tool, args)
    assert not engine.check_for_infinite_loop(tool, args)

    # 3rd identical call trips the threshold
    assert engine.check_for_infinite_loop(tool, args)