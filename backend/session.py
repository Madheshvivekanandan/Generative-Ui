"""Per-session conversation memory.

Without this, "now compare that to expenses" is unanswerable -- the model has
no idea what "that" is. Each session keeps a short rolling transcript that is
replayed ahead of the current message.

In-memory and process-local on purpose: this is a POV, and a dict makes the
lifetime of the data obvious. Swapping in Redis means replacing this module
and nothing else.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from schemas import Turn

# How many turns to replay. Long enough for "that" and "the one before it" to
# resolve, short enough that the dataset in the system prompt still dominates
# the context.
MAX_TURNS = 12

# Sessions are evicted oldest-first so a long-running demo cannot grow without
# bound. Nothing here is durable; a restart is a fresh conversation.
MAX_SESSIONS = 200


class SessionStore:
    def __init__(self, max_turns: int = MAX_TURNS, max_sessions: int = MAX_SESSIONS) -> None:
        self._turns: OrderedDict[str, list[Turn]] = OrderedDict()
        self._max_turns = max_turns
        self._max_sessions = max_sessions
        self._lock = threading.Lock()

    def history(self, session_id: str) -> list[Turn]:
        """The transcript to replay, oldest first. A copy: callers may mutate."""
        with self._lock:
            turns = self._turns.get(session_id)
            if turns is None:
                return []
            self._turns.move_to_end(session_id)
            return list(turns)

    def record(self, session_id: str, user: str, assistant: str) -> None:
        """Append one exchange, trimming to the rolling window."""
        with self._lock:
            turns = self._turns.setdefault(session_id, [])
            turns.append(Turn(role="user", content=user))
            turns.append(Turn(role="assistant", content=assistant))
            # Trim in pairs so the transcript never starts on an assistant turn.
            if len(turns) > self._max_turns:
                del turns[: len(turns) - self._max_turns]

            self._turns.move_to_end(session_id)
            while len(self._turns) > self._max_sessions:
                self._turns.popitem(last=False)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._turns.pop(session_id, None)


store = SessionStore()
