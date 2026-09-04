"""clean_follow_ups is pure and guards the suggestion chips; no network, no key."""

from agent import MAX_FOLLOW_UP_CHARS, MAX_FOLLOW_UPS, clean_follow_ups


def test_clean_follow_ups_drops_echo_of_the_request():
    assert clean_follow_ups(["Show revenue", "Show expenses"], asked="  show REVENUE ") == [
        "Show expenses"
    ]


def test_clean_follow_ups_deduplicates_casefolded():
    cleaned = clean_follow_ups(["Compare Q3", "compare q3", "Compare Q4"], asked="x")
    assert cleaned == ["Compare Q3", "Compare Q4"]


def test_clean_follow_ups_normalizes_whitespace_and_drops_long_items():
    long_item = "y" * (MAX_FOLLOW_UP_CHARS + 1)
    cleaned = clean_follow_ups(["  spaced   out  ", long_item, ""], asked="x")
    assert cleaned == ["spaced out"]


def test_clean_follow_ups_caps_the_count():
    cleaned = clean_follow_ups([f"Item {i}" for i in range(10)], asked="x")
    assert len(cleaned) == MAX_FOLLOW_UPS
