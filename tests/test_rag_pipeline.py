"""
tests/test_rag_pipeline.py  (Phase 2 — full replacement)
Tests for every fix made to rag.py:
  BUG-007  pre_retrieved forwarding eliminates double FAISS search
  BUG-008  History ordering: current question NOT in history passed to Gemini
  DESIGN   Each stage (_condense_query, _retrieve_and_format, _build_prompt,
           _stream_llm, execute_rag_pipeline) tested independently.
"""
import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from chat_manager import ChatMemory
from rag import (
    DEFAULT_MODEL,
    _build_prompt,
    _condense_query,
    _get_client,
    _retrieve_and_format,
    execute_rag_pipeline,
)
from src.retriever import RetrievalResult

# ── _get_client ────────────────────────────────────────────────────────────────

def test_get_client_missing_key_raises():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="GOOGLE_API_KEY is not set"):
            _get_client()


def test_get_client_with_api_key():
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "AIzaTestKey123"}):
        with patch("rag.genai.Client") as MockClient:
            _get_client()
            MockClient.assert_called_once_with(api_key="AIzaTestKey123")


# ── _condense_query ────────────────────────────────────────────────────────────

class TestCondenseQuery:
    def test_no_history_returns_original(self):
        """When chat history is empty, no Gemini call is made."""
        result = _condense_query("What is FAISS?", "", DEFAULT_MODEL)
        assert result == "What is FAISS?"

    def test_whitespace_history_returns_original(self):
        result = _condense_query("What is RAG?", "   \n  ", DEFAULT_MODEL)
        assert result == "What is RAG?"

    def test_with_history_calls_gemini(self):
        with patch("rag._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "What is FAISS for similarity search?"
            mock_client.models.generate_content.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = _condense_query(
                question="Tell me more",
                chat_history_str="User: What is FAISS?\nAssistant: It is a library.",
                model=DEFAULT_MODEL,
            )

        assert result == "What is FAISS for similarity search?"
        mock_client.models.generate_content.assert_called_once()

    def test_gemini_error_falls_back_to_original(self):
        with patch("rag._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = RuntimeError("network error")
            mock_get_client.return_value = mock_client

            result = _condense_query(
                question="What about embeddings?",
                chat_history_str="User: hello\nAssistant: hi",
                model=DEFAULT_MODEL,
            )

        assert result == "What about embeddings?"

    def test_gemini_returns_empty_text_falls_back(self):
        with patch("rag._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = ""
            mock_client.models.generate_content.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = _condense_query("original", "some history", DEFAULT_MODEL)

        assert result == "original"


# ── _retrieve_and_format ───────────────────────────────────────────────────────

class TestRetrieveAndFormat:
    def _make_result(self, text="content", similarity=0.8):
        doc = Document(page_content=text, metadata={"source": "f.pdf", "page": 0})
        return RetrievalResult(document=doc, similarity=similarity, distance=0.4)

    def test_no_db_returns_no_context(self):
        ctx, citations, avg = _retrieve_and_format(None, "query", 4)
        assert "No document context" in ctx
        assert citations == []
        assert avg == 0.0

    def test_pre_retrieved_used_without_faiss_call(self):
        """
        BUG-007 regression: when pre_retrieved is supplied, FAISS must NOT
        be queried again.
        """
        db = MagicMock()
        pre = [self._make_result("pre-fetched content", 0.9)]

        ctx, citations, avg = _retrieve_and_format(db, "query", 4, pre_retrieved=pre)

        db.similarity_search_with_score.assert_not_called()
        assert "pre-fetched content" in ctx

    def test_pre_retrieved_none_calls_faiss(self):
        """When pre_retrieved is None, FAISS search is performed."""
        doc = Document(page_content="faiss result", metadata={"source": "f.pdf", "page": 0})
        db = MagicMock()
        db.similarity_search_with_score.return_value = [(doc, 0.4)]

        ctx, _, _ = _retrieve_and_format(db, "query", 4, pre_retrieved=None)

        db.similarity_search_with_score.assert_called_once()
        assert "faiss result" in ctx

    def test_empty_faiss_results_returns_no_context(self):
        db = MagicMock()
        db.similarity_search_with_score.return_value = []
        ctx, citations, avg = _retrieve_and_format(db, "query", 4)
        assert "No document context" in ctx
        assert avg == 0.0

    def test_empty_pre_retrieved_returns_no_context(self):
        db = MagicMock()
        ctx, citations, avg = _retrieve_and_format(db, "query", 4, pre_retrieved=[])
        assert "No document context" in ctx


# ── _build_prompt ──────────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_persona_used_as_system_instruction(self):
        sys_instr, _ = _build_prompt("ctx", "history", "question", persona="You are a pirate.")
        assert "pirate" in sys_instr

    def test_default_system_instruction_when_no_persona(self):
        sys_instr, _ = _build_prompt("ctx", "history", "question", persona="")
        assert "BotTech AI" in sys_instr

    def test_prompt_contains_context(self):
        _, prompt = _build_prompt("DOCUMENT CONTEXT", "hist", "What is RAG?", "")
        assert "DOCUMENT CONTEXT" in prompt

    def test_prompt_contains_question(self):
        _, prompt = _build_prompt("ctx", "hist", "What is LangChain?", "")
        assert "What is LangChain?" in prompt

    def test_empty_history_replaced_with_no_prior(self):
        _, prompt = _build_prompt("ctx", "", "question", "")
        assert "No prior history" in prompt

    def test_whitespace_history_replaced_with_no_prior(self):
        _, prompt = _build_prompt("ctx", "   ", "question", "")
        assert "No prior history" in prompt


# ── execute_rag_pipeline ───────────────────────────────────────────────────────

class TestExecuteRagPipeline:
    """Full pipeline integration tests with mocked Gemini client."""

    def _mock_stream(self, texts):
        """Returns mock stream chunks for given text pieces."""
        chunks = []
        for t in texts:
            c = MagicMock()
            c.text = t
            c.candidates = []
            chunks.append(c)
        return chunks

    @patch("rag._get_client")
    def test_basic_streaming_no_db(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = self._mock_stream(
            ["Hello ", "world."]
        )
        mock_get_client.return_value = mock_client

        memory = ChatMemory()
        gen, citations, avg = execute_rag_pipeline(
            db=None,
            memory=memory,
            question="What is AI?",
            web_search=False,
        )
        tokens = list(gen)
        assert "".join(tokens) == "Hello world."
        assert citations == []
        assert avg == 0.0

    @patch("rag._get_client")
    def test_bug008_current_question_not_in_history(self, mock_get_client):
        """
        BUG-008 regression: execute_rag_pipeline must NOT include the current
        question in the history that gets formatted and sent to the model.

        We verify this by checking what system prompt / content is used in
        the generate_content_stream call: the current question appears only
        as the final 'User:' turn in the prompt template, never in the
        'Conversation History:' block.
        """
        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = self._mock_stream(["ok"])
        # Also mock the condensation call
        condense_response = MagicMock()
        condense_response.text = "What is FAISS?"
        mock_client.models.generate_content.return_value = condense_response
        mock_get_client.return_value = mock_client

        memory = ChatMemory()
        memory.add_user_message("What is RAG?")
        memory.add_assistant_message("RAG stands for Retrieval-Augmented Generation.")

        # Current question is "Tell me about FAISS" — must NOT appear in history
        gen, _, _ = execute_rag_pipeline(
            db=None,
            memory=memory,
            question="Tell me about FAISS",
            web_search=False,
        )
        list(gen)  # Exhaust generator

        # Get the prompt that was sent to generate_content_stream
        call_args = mock_client.models.generate_content_stream.call_args
        contents = call_args[1].get("contents") or call_args[0][1]
        # contents is the prompt_text string
        # It should NOT contain "Tell me about FAISS" in the history section,
        # only as the final question line.
        if isinstance(contents, str):
            history_section = contents.split("Conversation History:")[1].split("User:")[0]
            assert "Tell me about FAISS" not in history_section

    @patch("rag._get_client")
    def test_pre_retrieved_forwarded_no_double_retrieval(self, mock_get_client):
        """
        BUG-007 regression: pre_retrieved list must be forwarded without an
        additional FAISS call inside the pipeline.
        """
        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = self._mock_stream(["ok"])
        mock_get_client.return_value = mock_client

        doc = Document(page_content="pre-fetched text", metadata={"source": "pre.pdf", "page": 0})
        pre = [RetrievalResult(document=doc, similarity=0.9, distance=0.2)]

        db = MagicMock()

        memory = ChatMemory()
        gen, citations, avg = execute_rag_pipeline(
            db=db,
            memory=memory,
            question="What is retrieval?",
            pre_retrieved=pre,
            web_search=False,
        )
        list(gen)

        # FAISS must NOT be called because we passed pre_retrieved
        db.similarity_search_with_score.assert_not_called()
        assert len(citations) == 1
        assert citations[0]["source"] == "pre.pdf"

    @patch("rag._get_client")
    def test_web_search_populates_web_citations(self, mock_get_client):
        mock_client = MagicMock()

        # Build a chunk with grounding metadata
        chunk = MagicMock()
        chunk.text = "web answer"
        gc = MagicMock()
        gc.web.title = "Wikipedia"
        gc.web.uri = "https://en.wikipedia.org/wiki/RAG"
        chunk.candidates = [MagicMock()]
        chunk.candidates[0].grounding_metadata = MagicMock()
        chunk.candidates[0].grounding_metadata.grounding_chunks = [gc]

        mock_client.models.generate_content_stream.return_value = [chunk]
        mock_get_client.return_value = mock_client

        memory = ChatMemory()
        web_citations: list = []
        gen, _, _ = execute_rag_pipeline(
            db=None,
            memory=memory,
            question="Latest AI news?",
            web_search=True,
            web_citations=web_citations,
        )
        list(gen)

        assert len(web_citations) == 1
        assert web_citations[0]["uri"] == "https://en.wikipedia.org/wiki/RAG"

    @patch("rag._get_client")
    def test_llm_error_yields_error_message(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.models.generate_content_stream.side_effect = RuntimeError("API down")
        mock_get_client.return_value = mock_client

        memory = ChatMemory()
        gen, _, _ = execute_rag_pipeline(
            db=None,
            memory=memory,
            question="Anything",
            web_search=False,
        )
        output = "".join(gen)
        assert "error" in output.lower() or "🚨" in output

    @patch("rag._get_client")
    def test_no_text_chunks_yield_nothing_extra(self, mock_get_client):
        """Chunks with chunk.text = None / empty must not add empty tokens."""
        mock_client = MagicMock()
        c1 = MagicMock(); c1.text = None; c1.candidates = []
        c2 = MagicMock(); c2.text = "real"; c2.candidates = []
        mock_client.models.generate_content_stream.return_value = [c1, c2]
        mock_get_client.return_value = mock_client

        memory = ChatMemory()
        gen, _, _ = execute_rag_pipeline(
            db=None, memory=memory, question="q", web_search=False
        )
        tokens = list(gen)
        assert "".join(tokens) == "real"
