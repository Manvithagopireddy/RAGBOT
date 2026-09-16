from chat_manager import ChatMemory


def test_chat_memory_addition_and_clear():
    """Tests appending user and assistant messages and clearing state."""
    memory = ChatMemory()
    assert memory.get_messages() == []

    memory.add_user_message("Hello AI")
    memory.add_assistant_message("Hello! How can I help you today?")

    messages = memory.get_messages()
    assert len(messages) == 2
    assert messages[0] == {"role": "user", "content": "Hello AI"}
    assert messages[1] == {"role": "assistant", "content": "Hello! How can I help you today?"}

    memory.clear()
    assert memory.get_messages() == []


def test_format_chat_history():
    """Tests formatting history string for LLM prompt injection."""
    memory = ChatMemory()
    memory.add_user_message("What is RAG?")
    memory.add_assistant_message("Retrieval-Augmented Generation.")
    memory.add_user_message("How does FAISS fit in?")
    memory.add_assistant_message("FAISS is used as the vector index.")

    history_str = memory.format_chat_history(limit=2)
    assert "User: What is RAG?" in history_str
    assert "Assistant: Retrieval-Augmented Generation." in history_str
    assert "User: How does FAISS fit in?" in history_str
    assert "Assistant: FAISS is used as the vector index." in history_str


def test_format_chat_history_limit():
    """Tests that limit parameter truncates older messages appropriately."""
    memory = ChatMemory()
    for i in range(10):
        memory.add_user_message(f"Query {i}")
        memory.add_assistant_message(f"Answer {i}")

    # Limit of 2 interactions should return the last 4 messages
    formatted = memory.format_chat_history(limit=2)
    assert "Query 8" in formatted
    assert "Query 9" in formatted
    assert "Query 0" not in formatted
