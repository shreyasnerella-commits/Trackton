import hashlib
import json
from typing import Dict, Any, List

class AnomalyEngine:
    def __init__(self, threshold: int = 3):
        """
        Initialize the Anomaly Engine.
        :param threshold: Number of identical tool calls required to trigger a loop detection.
        """
        self.threshold = threshold
        self.call_history: List[str] = []

    def generate_tool_signature(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Generates a deterministic SHA-256 hash for a given tool call.
        Key sorting guarantees identical hashes regardless of dict key order.
        """
        # Sort keys so parameter order doesn't affect hash consistency
        canonical_args = json.dumps(arguments, sort_keys=True)
        payload = f"{tool_name}:{canonical_args}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def check_for_infinite_loop(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """
        Records the tool call and checks if the last N calls are identical.
        Returns True if an infinite loop anomaly is detected.
        """
        signature = self.generate_tool_signature(tool_name, arguments)
        self.call_history.append(signature)

        # Ensure we have enough history to evaluate against the threshold
        if len(self.call_history) < self.threshold:
            return False

        # Check if the last `threshold` calls are all equal to the latest signature
        recent_window = self.call_history[-self.threshold:]
        if all(sig == signature for sig in recent_window):
            return True

        return False