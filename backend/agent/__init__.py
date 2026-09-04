"""The agent package: free-text in, a stream of A2UI v0.9 events out.

Split one module per concern -- config, prompt, events, follow-up cleaning,
block emission, fallbacks, and the streaming runner -- and re-exported here so
callers keep writing `import agent` / `from agent import run`.
"""

from agent.config import (
    DEFAULT_FOLLOW_UPS,
    MAX_FOLLOW_UP_CHARS,
    MAX_FOLLOW_UPS,
    MODEL,
    get_client,
)
from agent.events import Event
from agent.fallbacks import FALLBACK_COPY, fallback
from agent.follow_ups import clean_follow_ups
from agent.prompts import SYSTEM_PROMPT
from agent.runner import run

__all__ = [
    "DEFAULT_FOLLOW_UPS",
    "Event",
    "FALLBACK_COPY",
    "MAX_FOLLOW_UP_CHARS",
    "MAX_FOLLOW_UPS",
    "MODEL",
    "SYSTEM_PROMPT",
    "clean_follow_ups",
    "fallback",
    "get_client",
    "run",
]
