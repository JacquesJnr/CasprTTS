from quick_tts_mic.history import SessionHistory


def test_history_navigation_restores_draft() -> None:
    history = SessionHistory()
    history.add("first")
    history.add("second")

    assert history.previous("new draft") == "second"
    assert history.previous("second") == "first"
    assert history.next() == "second"
    assert history.next() == "new draft"


def test_history_is_bounded_and_deduplicates_adjacent_items() -> None:
    history = SessionHistory(limit=2)
    history.add("one")
    history.add("one")
    history.add("two")
    history.add("three")
    assert history.items == ("two", "three")

