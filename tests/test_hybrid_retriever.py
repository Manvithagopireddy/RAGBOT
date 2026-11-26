"""
tests/test_hybrid_retriever.py
Unit tests for hybrid retrieval and Reciprocal Rank Fusion (RRF).
"""
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from src.hybrid_retriever import (
    _doc_key,
    reciprocal_rank_fusion,
    retrieve_hybrid,
    weighted_score_fusion,
)
from src.retriever import RetrievalResult


def _make_res(text: str, source: str = "doc.pdf", page: int = 0, similarity: float = 0.8) -> RetrievalResult:
    doc = Document(
        page_content=text,
        metadata={"source": source, "page": page, "chunk_id": f"{source}::p{page}::{text[:10]}"},
    )
    return RetrievalResult(document=doc, similarity=similarity, distance=1.0 - similarity)


class TestHybridRetriever:
    def test_doc_key_unique(self):
        r1 = _make_res("Content A", "file1.pdf", 0)
        r2 = _make_res("Content B", "file2.pdf", 0)
        assert _doc_key(r1.document) != _doc_key(r2.document)

    def test_rrf_fuses_dense_and_sparse(self):
        doc1 = _make_res("Common doc", "file1.pdf", 0, similarity=0.9)
        doc2 = _make_res("Dense only", "file2.pdf", 0, similarity=0.8)
        doc3 = _make_res("Sparse only", "file3.pdf", 0, similarity=0.85)

        dense = [doc1, doc2]
        sparse = [doc1, doc3]

        fused = reciprocal_rank_fusion(dense, sparse, rrf_k=60, top_k=3)
        assert len(fused) == 3
        # doc1 appears in both at rank 1, so it must have the highest fused score
        assert fused[0].document.page_content == "Common doc"
        assert fused[0].similarity > fused[1].similarity

    def test_weighted_score_fusion(self):
        doc1 = _make_res("Doc 1", "file1.pdf", 0, similarity=1.0)
        doc2 = _make_res("Doc 2", "file2.pdf", 0, similarity=0.5)

        dense = [doc1]
        sparse = [doc2]

        # alpha=0.5: doc1 has dense=1.0, sparse=0.0 -> 0.5. doc2 has dense=0.0, sparse=0.5 -> 0.25.
        fused = weighted_score_fusion(dense, sparse, alpha=0.5, top_k=2)
        assert len(fused) == 2
        assert fused[0].document.page_content == "Doc 1"
        assert fused[0].similarity == pytest.approx(0.5)
        assert fused[1].similarity == pytest.approx(0.25)

    def test_retrieve_hybrid_dense_fallback_when_sparse_empty(self):
        db = MagicMock()
        doc = Document(page_content="Semantic match", metadata={"source": "a.pdf", "page": 0})
        db.similarity_search_with_score.return_value = [(doc, 0.2)]

        results = retrieve_hybrid(db=db, bm25=None, query="test query", k=2)
        assert len(results) == 1
        assert results[0].text == "Semantic match"

    def test_retrieve_hybrid_sparse_fallback_when_dense_none(self):
        bm25 = MagicMock()
        doc = Document(page_content="Keyword match", metadata={"source": "b.pdf", "page": 0})
        bm25.retrieve_as_results.return_value = [
            RetrievalResult(document=doc, similarity=0.8, distance=0.2)
        ]

        results = retrieve_hybrid(db=None, bm25=bm25, query="keyword query", k=2)
        assert len(results) == 1
        assert results[0].text == "Keyword match"

    def test_retrieve_hybrid_empty_query(self):
        results = retrieve_hybrid(db=None, bm25=None, query="")
        assert results == []


    def test_fallback_identity_uses_entire_chunk(self):
        prefix = "same prefix " * 20
        a = Document(page_content=prefix + "a", metadata={"source": "a.pdf", "page": 0})
        b = Document(page_content=prefix + "b", metadata={"source": "a.pdf", "page": 0})
        assert _doc_key(a) != _doc_key(b)
        assert _doc_key(a) == _doc_key(a)

    def test_rrf_duplicate_does_not_inflate_score(self):
        a = _make_res("Repeated chunk")
        b = _make_res("Independent chunk")
        fused = reciprocal_rank_fusion([a, a], [b], top_k=2)
        assert len(fused) == 2
        assert fused[0].similarity == pytest.approx(fused[1].similarity)
