"""
tests/conftest.py — Shared pytest fixtures for the RAGBOT test suite.
"""
from pathlib import Path

import pytest

from storage import ChatStore


@pytest.fixture
def temp_chat_store(tmp_path: Path) -> ChatStore:
    """
    Returns a fully initialised ChatStore backed by a temporary SQLite
    database that is discarded after each test.
    """
    db_path = tmp_path / "test_chat.db"
    return ChatStore(db_path)


@pytest.fixture
def session_with_messages(temp_chat_store: ChatStore):
    """
    Returns a (chat_store, session_id) tuple pre-populated with two messages.
    """
    sid = temp_chat_store.create_session(title="Fixture Session")
    temp_chat_store.add_message(sid, "user", "Hello")
    temp_chat_store.add_message(sid, "assistant", "Hi there!", confidence_score=80)
    return temp_chat_store, sid
