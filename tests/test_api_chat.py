"""
test_api_chat.py — Tests for Synchronous Chat, SSE Streaming Chat, and Diagnostics Endpoints.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from services.rag_service import RAGService
from services.retrieval_service import RetrievalService
from src.retriever import RetrievalResult
from storage import ChatStore


@pytest.fixture
def chat_client(tmp_path):
    test_db = tmp_path / "test_chat_endpoints.db"
    test_store = ChatStore(test_db)
    test_rag = RAGService(db_store=test_store)
    test_retrieval = RetrievalService()

    from api.dependencies import get_chat_store, get_rag_service, get_retrieval_service
    app.dependency_overrides[get_chat_store] = lambda: test_store
    app.dependency_overrides[get_rag_service] = lambda: test_rag
    app.dependency_overrides[get_retrieval_service] = lambda: test_retrieval

    with TestClient(app) as test_client:
        yield test_client, test_rag, test_retrieval

    app.dependency_overrides.clear()


class TestChatEndpoints:
    def test_sync_chat_with_mocked_pipeline(self, chat_client, monkeypatch):
        client, rag, _ = chat_client

        # Mock execute_rag_pipeline to avoid external Gemini calls
        def fake_pipeline(**kwargs):
            def token_stream():
                yield "This is a "
                yield "mocked grounded response."
            citations = [{"id": 1, "source": "guide.pdf", "page": 1, "snippet": "A snippet", "score": 0.95}]
            avg_sim = 0.95
            return token_stream(), citations, avg_sim

        monkeypatch.setattr("services.rag_service.execute_rag_pipeline", fake_pipeline)

        res = client.post("/api/v1/chat", json={
            "message": "What is the architecture?",
            "model": "gemini-2.5-flash",
            "temperature": 0.7,
        })
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert "content" in data
        assert data["content"] == "This is a mocked grounded response."
        assert len(data["citations"]) == 1
        assert data["citations"][0]["source"] == "guide.pdf"
        assert data["confidence_score"] is not None

    def test_streaming_chat_with_mocked_pipeline(self, chat_client, monkeypatch):
        client, rag, _ = chat_client

        def fake_pipeline(**kwargs):
            def token_stream():
                yield "Streaming "
                yield "chunk 1 "
                yield "chunk 2"
            citations = [{"id": 1, "source": "overview.pdf", "page": 2, "snippet": "test snippet", "score": 0.88}]
            avg_sim = 0.88
            return token_stream(), citations, avg_sim

        monkeypatch.setattr("services.rag_service.execute_rag_pipeline", fake_pipeline)

        res = client.post("/api/v1/chat/stream", json={
            "message": "Explain streaming.",
        })
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        text_body = res.text
        assert "event: metadata" in text_body
        assert "event: citations" in text_body
        assert "event: token" in text_body
        assert "event: done" in text_body

    def test_diagnostics_endpoint(self, chat_client, monkeypatch):
        client, _, retrieval = chat_client

        # Mock retrieve on retrieval service
        mock_result = RetrievalResult(
            document=MagicMock(page_content="Diagnostic test chunk content", metadata={"source": "test.pdf", "page": 0}),
            similarity=0.91,
            distance=0.09,
        )
        monkeypatch.setattr(
            retrieval,
            "retrieve",
            lambda query, k, threshold, hybrid, rerank: ([mock_result], {"latency_ms": 12.5, "query": query}),
        )

        res = client.post("/api/v1/diagnostics/retrieve", json={
            "query": "vector indexing",
            "k": 2,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "vector indexing"
        assert data["results_count"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["source"] == "test.pdf"
        assert data["results"][0]["similarity"] == 0.91
