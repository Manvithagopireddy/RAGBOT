import os
from unittest.mock import MagicMock, patch
import pytest
from chat_manager import ChatMemory
from rag import _get_client, execute_rag_pipeline


def test_get_client_missing_key():
    """Tests that _get_client raises a descriptive ValueError if GOOGLE_API_KEY is missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="GOOGLE_API_KEY is not set"):
            _get_client()


@patch("rag._get_client")
def test_execute_rag_pipeline_mocked(mock_get_client):
    """Tests end-to-end token streaming and fallback behavior with a mocked Gemini client."""
    # Setup mock client
    mock_client = MagicMock()
    mock_chunk_1 = MagicMock()
    mock_chunk_1.text = "LangGraph is designed "
    mock_chunk_1.candidates = []
    mock_chunk_2 = MagicMock()
    mock_chunk_2.text = "for cyclical agent workflows."
    mock_chunk_2.candidates = []

    mock_client.models.generate_content_stream.return_value = [mock_chunk_1, mock_chunk_2]
    mock_get_client.return_value = mock_client

    memory = ChatMemory()
    token_generator, citations, avg_similarity = execute_rag_pipeline(
        db=None,
        memory=memory,
        question="What is LangGraph?",
        web_search=False
    )

    tokens = list(token_generator)
    assert "".join(tokens) == "LangGraph is designed for cyclical agent workflows."
    assert citations == []
    assert avg_similarity == 0.0
