# utils/tokens.py

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def truncate_to_chars(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated + "…"
