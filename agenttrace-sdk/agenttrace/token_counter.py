"""
agenttrace.token_counter
--------------------------
Implements the fix for the SDK "Trap": relying solely on token counts
from API response headers breaks on streaming responses or mid-call
failures.

Strategy:
1. BEFORE the call: estimate prompt_tokens locally using tiktoken.
   This guarantees we always have *a* number, even if the call never
   returns.
2. AFTER the call: if the provider's response object exposes real usage
   data (response.usage.prompt_tokens / completion_tokens), overwrite
   the estimate with the real number.
3. ON STREAMING: accumulate text chunk by chunk and count tokens only
   once the stream ends (or is interrupted) -- never assume the whole
   completion exists up front.
4. ON EXCEPTION/TIMEOUT: keep whatever estimate/partial count we had
   instead of leaving the field null. Null tokens make cost dashboards
   silently wrong; a slightly-off estimate is far more useful.

tiktoken is optional. If it isn't installed, we fall back to a rough
whitespace-based estimate so the SDK never hard-crashes just because a
teammate hasn't pip-installed it yet.
"""

from typing import Optional

try:
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
    _HAS_TIKTOKEN = True
except Exception:
    _ENCODING = None
    _HAS_TIKTOKEN = False


def estimate_tokens(text: str) -> int:
    """
    Local, pre-call token estimate. Always succeeds (never raises),
    so it's safe to call before we know if the downstream API call
    will work.
    """
    if not text:
        return 0

    if _HAS_TIKTOKEN:
        try:
            return len(_ENCODING.encode(text))
        except Exception:
            pass

    # Fallback: rough heuristic (~4 chars per token for English text)
    return max(1, len(text) // 4)


def extract_real_usage(response) -> Optional[dict]:
    """
    Attempts to pull real prompt/completion token counts off a provider
    response object (OpenAI/Anthropic-style `.usage`). Returns None if
    the shape doesn't match anything recognizable -- callers should keep
    their tiktoken estimate in that case.
    """
    if response is None:
        return None

    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")

    if usage is None:
        return None

    def _get(obj, key, *alt_keys):
        for k in (key,) + alt_keys:
            if isinstance(obj, dict) and k in obj:
                return obj[k]
            val = getattr(obj, k, None)
            if val is not None:
                return val
        return None

    prompt_tokens = _get(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _get(usage, "completion_tokens", "output_tokens")

    if prompt_tokens is None and completion_tokens is None:
        return None

    return {
        "prompt_tokens": int(prompt_tokens) if prompt_tokens is not None else None,
        "completion_tokens": int(completion_tokens) if completion_tokens is not None else None,
    }


class StreamTokenAccumulator:
    """
    Helper for the streaming case. Wrap chunk-by-chunk text as it
    arrives; call .finalize() when the stream ends OR when it breaks/
    times out early -- either way you get a real count of what was
    actually received, never a null.
    """

    def __init__(self):
        self._buffer_parts = []

    def add_chunk(self, text_chunk: str):
        if text_chunk:
            self._buffer_parts.append(text_chunk)

    def finalize(self) -> int:
        full_text = "".join(self._buffer_parts)
        return estimate_tokens(full_text)
