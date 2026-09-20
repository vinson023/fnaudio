"""Bounded error text projection for process-supervisor state."""

MAX_PROCESS_ERROR_TEXT = 512

def process_error_text(value, default="process operation failed"):
    fallback = default if isinstance(default, str) else "process operation failed"
    if isinstance(value, BaseException):
        value = next((part for part in value.args if isinstance(part, str)), "")
    if not isinstance(value, str):
        return fallback
    text = value.strip()
    return text[:MAX_PROCESS_ERROR_TEXT] if text else fallback

__all__ = ["MAX_PROCESS_ERROR_TEXT", "process_error_text"]
