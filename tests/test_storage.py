from pathlib import Path
import numpy as np
import pytest
from storage import ChatStore


@pytest.fixture
def temp_store(tmp_path: Path):
    """Creates an isolated ChatStore instance using pytest's tmp_path fixture."""
    db_path = tmp_path / "test_chat.db"
    return ChatStore(db_path)


def test_session_lifecycle(temp_store):
    """Tests creating, retrieving, and deleting sessions."""
    # 1. Create session
    session_id = temp_store.create_session(title="Test Session", model="gemini-2.5-flash")
    assert session_id is not None
    assert isinstance(session_id, str)

    # 2. Retrieve session
    session = temp_store.get_session(session_id)
    assert session is not None
    assert session["title"] == "Test Session"
    assert session["model"] == "gemini-2.5-flash"

    # 3. List sessions
    all_sessions = temp_store.get_all_sessions()
    assert len(all_sessions) >= 1
    assert any(s["session_id"] == session_id for s in all_sessions)

    # 4. Delete session
    temp_store.delete_session(session_id)
    deleted = temp_store.get_session(session_id)
    assert deleted is None


def test_message_lifecycle_and_serialization(temp_store):
    """Tests adding messages, handling numpy types in citations, and updating feedback."""
    session_id = temp_store.create_session(title="Conversation Test")

    # Add user message
    user_msg_id = temp_store.add_message(
        session_id=session_id,
        role="user",
        content="What is FAISS?",
    )
    assert user_msg_id is not None

    # Add assistant message with numpy float score in citations
    citations = [
        {"id": 1, "source": "test.pdf", "page": np.int32(1), "score": np.float32(0.85)}
    ]
    asst_msg_id = temp_store.add_message(
        session_id=session_id,
        role="assistant",
        content="FAISS is a library for efficient similarity search.",
        citations=citations,
        confidence_score=85,
        confidence_desc="High Confidence",
    )
    assert asst_msg_id is not None

    # Retrieve messages
    messages = temp_store.get_messages(session_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert len(messages[1]["citations"]) == 1
    assert messages[1]["citations"][0]["score"] == pytest.approx(0.85, rel=1e-2)

    # Test feedback update
    temp_store.update_message_feedback(asst_msg_id, "thumbs_up")
    updated_messages = temp_store.get_messages(session_id)
    assert updated_messages[1]["feedback"] == "thumbs_up"


def test_search_sessions(temp_store):
    """Tests session content search functionality."""
    session_id = temp_store.create_session(title="Machine Learning Query")
    temp_store.add_message(
        session_id=session_id,
        role="user",
        content="Tell me about gradient boosting and neural networks.",
    )

    results = temp_store.search_sessions("gradient")
    assert len(results) > 0
    assert any(r["session_id"] == session_id for r in results)
