"""Model selection, follow-up limits, and the lazily-built OpenAI client."""

from __future__ import annotations

import os

from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MAX_FOLLOW_UPS = 3
MAX_FOLLOW_UP_CHARS = 70

DEFAULT_FOLLOW_UPS = [
    "Show revenue as a line chart",
    "Expenses by category as a bar chart",
    "What was net cash flow in August?",
]

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Lazily build the OpenAI client so the app still boots without a key."""
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from the environment
    return _client
