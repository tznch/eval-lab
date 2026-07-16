from shared.reporting.score_format import format_rate_pct, format_score, round_score


def test_round_score_three_decimals():
    assert round_score(0.123456) == 0.123
    assert round_score(0.1239) == 0.124
    assert round_score(None) is None


def test_format_rate_pct():
    assert format_rate_pct(0.967) == "96.700%"
