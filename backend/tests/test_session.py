"""SessionStore is the app's entire persistence layer; its window and eviction
rules are what keep a long demo bounded."""

from session import SessionStore


def test_record_trims_to_the_window_in_pairs():
    store = SessionStore(max_turns=4)
    for i in range(5):
        store.record("s", f"q{i}", f"a{i}")

    turns = store.history("s")
    assert len(turns) == 4
    # Trimming in pairs means a replayed transcript never opens mid-exchange.
    assert turns[0].role == "user"
    assert turns[0].content == "q3"
    assert turns[-1].content == "a4"


def test_sessions_evict_oldest_first():
    store = SessionStore(max_sessions=2)
    for name in ("first", "second", "third"):
        store.record(name, "q", "a")

    assert store.history("first") == []
    assert store.history("second") and store.history("third")


def test_history_returns_a_copy():
    store = SessionStore()
    store.record("s", "q", "a")

    history = store.history("s")
    history.clear()
    assert len(store.history("s")) == 2


def test_history_of_unknown_session_is_empty():
    assert SessionStore().history("nope") == []
