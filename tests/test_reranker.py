"""
tests/test_reranker.py
Unit tests for neural and heuristic reranking with mocked models for fast, offline execution.
"""
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from src.reranker import rerank_chunks
from src.retriever import RetrievalResult


class TestReranker:
    def test_rerank_disabled_returns_original(self):
        doc1 = Document(page_content="Text 1", metadata={"source": "a.pdf", "page": 0})
        doc2 = Document(page_content="Text 2", metadata={"source": "b.pdf", "page": 0})
        results = [
            RetrievalResult(document=doc1, similarity=0.9, distance=0.1),
            RetrievalResult(document=doc2, similarity=0.7, distance=0.3),
        ]
        reranked = rerank_chunks("query", results, top_n=2, enabled=False)
        assert len(reranked) == 2
        assert reranked[0].text == "Text 1"

    def test_rerank_empty_results(self):
        reranked = rerank_chunks("query", [], top_n=2, enabled=True)
        assert reranked == []

    @patch("src.reranker._get_cross_encoder", return_value=None)
    def test_rerank_heuristic_boosts_exact_term_match(self, mock_get_ce):
        doc_irrelevant = Document(
            page_content="Unrelated general statement about clouds and weather.",
            metadata={"source": "weather.pdf", "page": 0},
        )
        doc_exact = Document(
            page_content="Model Context Protocol (MCP) defines client-server standard for AI tools.",
            metadata={"source": "mcp.pdf", "page": 0},
        )
        results = [
            RetrievalResult(document=doc_irrelevant, similarity=0.8, distance=0.2),
            RetrievalResult(document=doc_exact, similarity=0.7, distance=0.3),
        ]
        reranked = rerank_chunks(
            query="Model Context Protocol MCP client server",
            results=results,
            top_n=2,
            enabled=True,
        )
        assert reranked[0].text == doc_exact.page_content

    def test_rerank_with_mocked_cross_encoder(self):
        mock_ce = MagicMock()
        # Mock predict returns logits [0.1, 2.5]
        mock_ce.predict.return_value = [0.1, 2.5]

        doc1 = Document(page_content="Candidate 1", metadata={"source": "a.pdf", "page": 0})
        doc2 = Document(page_content="Candidate 2", metadata={"source": "b.pdf", "page": 0})
        results = [
            RetrievalResult(document=doc1, similarity=0.8, distance=0.2),
            RetrievalResult(document=doc2, similarity=0.6, distance=0.4),
        ]

        with patch("src.reranker._get_cross_encoder", return_value=mock_ce):
            reranked = rerank_chunks(
                query="test query",
                results=results,
                top_n=2,
                enabled=True,
            )

        assert len(reranked) == 2
        # Candidate 2 received logit 2.5 > 0.1 so candidate 2 must be ranked #1
        assert reranked[0].text == "Candidate 2"
