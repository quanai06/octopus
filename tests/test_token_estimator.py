from octopus.context.token_estimator import estimate_tokens, get_token_status


def test_estimate_tokens_returns_int():
    result = estimate_tokens("hello world")

    assert isinstance(result, int)
    assert result > 0


def test_token_status_ok_below_warning():
    assert get_token_status(7_999) == "ok"


def test_token_status_warning():
    assert get_token_status(8_000) == "warning"


def test_token_status_exceeded():
    assert get_token_status(16_000) == "exceeded"
