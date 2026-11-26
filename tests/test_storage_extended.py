"""Exercise persisted legacy session and message operations on a disposable database."""
import pytest

from storage import ChatStore


@pytest.fixture
def store(tmp_path):
    return ChatStore(tmp_path / "extended.db")


def test_session_flags_search_and_copy(store):
    session = store.create_session(title="Research notes")
    store.add_message(session, "user", "Unique phrase for search")
    for toggle in (store.toggle_session_pin, store.toggle_session_favorite, store.toggle_session_archive):
        assert toggle(session) is True
        assert toggle(session) is False
        assert toggle("missing") is False
    assert store.toggle_session_archive(session)
    assert store.get_archived_sessions()[0]["session_id"] == session
    assert store.search_sessions("unique phrase")[0]["session_id"] == session
    assert store.search_sessions("no match") == []
    copy = store.duplicate_session(session)
    assert copy and copy != session
    assert store.get_session(copy)["title"] == "Research notes (Copy)"
    assert store.get_messages(copy)[0]["content"] == "Unique phrase for search"
    assert store.duplicate_session("missing") is None
    store.clear_all_sessions()
    assert store.get_all_sessions() == []
    assert store.get_messages(session) == []


def test_message_lifecycle(store):
    session = store.create_session()
    assert store.get_session_last_message(session) is None
    first = store.add_message(session, "user", "Question")
    second = store.add_message(session, "assistant", "Answer", confidence_score=80)
    assert store.get_message_count(session) == 2
    store.update_message_feedback(second, "up")
    assert store.toggle_pin_message(second)
    assert store.get_pinned_messages(session)[0]["message_id"] == second
    assert not store.toggle_pin_message(second)
    assert not store.toggle_pin_message("missing")
    store.append_message_content(second, " extended")
    assert store.get_session_last_message(session)["content"] == "Answer extended"
    store.update_message_content(second, "Revised")
    store.save_message_source_type(second, "Knowledge Base")
    messages = store.get_messages(session)
    assert messages[1]["content"] == "Revised"
    assert messages[1]["feedback"] == "up"
    assert messages[1]["confidence_desc"] == "source:Knowledge Base"
    store.delete_messages_from(session, messages[1]["created_at"])
    assert [m["message_id"] for m in store.get_messages(session)] == [first]
    store.clear_messages(session)
    assert store.get_message_count(session) == 0
