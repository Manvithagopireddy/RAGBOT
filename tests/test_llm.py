"""
tests/test_llm.py — Unit tests for LLM initialization and configuration.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.llm import get_llm


class TestLLMInitialization:
    def test_get_llm_with_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyFakeTestKeyForUnitTests12345")
        with patch("src.llm.ChatGoogleGenerativeAI") as mock_chat:
            mock_instance = MagicMock()
            mock_chat.return_value = mock_instance

            llm = get_llm(temperature=0.3, max_tokens=1024)
            assert llm == mock_instance
            mock_chat.assert_called_once()
            kwargs = mock_chat.call_args[1]
            assert kwargs["temperature"] == 0.3
            assert kwargs["max_output_tokens"] == 1024
            assert kwargs["google_api_key"] == "AIzaSyFakeTestKeyForUnitTests12345"
            assert kwargs["streaming"] is True

    def test_get_llm_warning_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with patch("src.llm.ChatGoogleGenerativeAI") as mock_chat:
            mock_chat.return_value = MagicMock()
            llm = get_llm()
            assert llm is not None

    def test_get_llm_raises_on_failure(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "dummy_key")
        with patch("src.llm.ChatGoogleGenerativeAI", side_effect=RuntimeError("Init error")):
            with pytest.raises(RuntimeError, match="Init error"):
                get_llm()
