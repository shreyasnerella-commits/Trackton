import hashlib
import json
from typing import Dict, Any, Optional
from supabase import Client


class AnomalyEngine:
    def __init__(self, threshold: int = 3, window_size: int = 10):
        self.threshold = threshold
        self.window_size = window_size
        self.call_history: list[str] = []

    def generate_tool_signature(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Generates a deterministic SHA-256 hash for a tool call."""
        canonical_args = json.dumps(arguments, sort_keys=True)
        payload = f"{tool_name}:{canonical_args}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def is_loop_detected(self, signature: str) -> bool:
        """Records the signature and checks if an infinite loop threshold is hit."""
        self.call_history.append(signature)

        if len(self.call_history) < self.threshold:
            return False

        recent_window = self.call_history[-self.threshold:]
        return all(sig == signature for sig in recent_window)

    def check_for_infinite_loop(self, tool_name: str, tool_input: dict) -> bool:
        """Generates signature and checks for infinite loop (expected by test suite)."""
        signature = self.generate_tool_signature(tool_name, tool_input)
        return self.is_loop_detected(signature)


# Global engine instance for app-wide use
engine = AnomalyEngine(threshold=3)


def check_for_infinite_loop(
    supabase_client: Optional[Client] = None,
    trace_id: str = "",
    agent_id: str = "",
    tool_name: str = "",
    input_hash: str = "",
    threshold: int = 3
) -> bool:
    """
    Wrapper function to maintain compatibility with backend/app/main.py
    while utilizing the in-memory AnomalyEngine.
    """
    return engine.is_loop_detected(input_hash)