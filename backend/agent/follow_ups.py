"""Cleaning for the model's suggested follow-up chips."""

from __future__ import annotations

from agent.config import MAX_FOLLOW_UP_CHARS, MAX_FOLLOW_UPS


def clean_follow_ups(raw: list[str], asked: str) -> list[str]:
    """Trim, de-duplicate and drop anything that just echoes the request.

    Unlike a block, a bad follow-up is not worth failing the turn over -- an
    empty list simply renders no chips.
    """
    seen: set[str] = {asked.strip().casefold()}
    cleaned: list[str] = []

    for item in raw:
        text = " ".join(item.split())
        key = text.casefold()
        if not text or len(text) > MAX_FOLLOW_UP_CHARS or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) == MAX_FOLLOW_UPS:
            break

    return cleaned
