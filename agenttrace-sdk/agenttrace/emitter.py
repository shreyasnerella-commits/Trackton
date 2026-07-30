"""
agenttrace.emitter
--------------------
Sends finished spans to Member 3's FastAPI ingestion endpoint
(POST /api/telemetry). Two design choices matter here:

1. Emitting telemetry must NEVER crash or block the agent being
   observed. If the backend is down, we swallow the error and fall
   back to writing the span to a local .jsonl file instead. This also
   means you (Member 1) can build and demo the entire SDK before
   Member 3's backend exists.

2. The endpoint is configurable via the AGENTTRACE_ENDPOINT env var so
   nothing is hardcoded once the real backend URL exists.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests

    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

DEFAULT_ENDPOINT = os.environ.get("AGENTTRACE_ENDPOINT", "http://localhost:8000/api/telemetry")
FALLBACK_LOG_PATH = Path(os.environ.get("AGENTTRACE_FALLBACK_LOG", "agenttrace_spans.jsonl"))

_lock = threading.Lock()


def _write_local_fallback(span: dict):
    with _lock:
        with open(FALLBACK_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(span) + "\n")


def emit_span(span: dict, endpoint: str = None, timeout_seconds: float = 2.0):
    """
    Sends a single span dict to the backend. Never raises -- worst case
    it falls back to a local file so no telemetry is ever silently lost
    during a hackathon demo.
    """
    target = endpoint or DEFAULT_ENDPOINT

    if not _HAS_REQUESTS:
        _write_local_fallback(span)
        return {"status": "local_fallback", "reason": "requests library not installed"}

    try:
        resp = requests.post(target, json=span, timeout=timeout_seconds)
        if resp.status_code >= 400:
            _write_local_fallback(span)
            return {"status": "local_fallback", "reason": f"HTTP {resp.status_code}"}
        return {"status": "sent", "response": _safe_json(resp)}
    except Exception as exc:
        _write_local_fallback(span)
        return {"status": "local_fallback", "reason": str(exc)}


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
