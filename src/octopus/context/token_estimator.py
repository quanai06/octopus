ENCODING = "cl100k_base"
TOKEN_WARNING = 8_000
TOKEN_HARD_LIMIT = 16_000


def estimate_tokens(text: str) -> int:
    try:
        import tiktoken

        encoding = tiktoken.get_encoding(ENCODING)
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def get_token_status(token_count: int) -> str:
    if token_count >= TOKEN_HARD_LIMIT:
        return "exceeded"
    if token_count >= TOKEN_WARNING:
        return "warning"
    return "ok"


def format_token_display(token_count: int) -> str:
    status = get_token_status(token_count)
    if status == "exceeded":
        return f"[red]{token_count:,} (exceeded {TOKEN_HARD_LIMIT:,})[/red]"
    if status == "warning":
        return f"[yellow]{token_count:,} (approaching limit)[/yellow]"
    return f"[green]{token_count:,}[/green]"
