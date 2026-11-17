"""
tests/test_retriever.py  (Phase 2 — full replacement)
Tests for every fix made to src/retriever.py:
  • RetrievalResult dataclass properties
  • retrieve_relevant_chunks with threshold filtering
  • get_best_similarity
  • format_retrieved_context page numbering (0-indexed stored, 1-indexed displayed)
  • Empty / error edge cases
"""
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from src.retriever import (
    RetrievalResult,
    format_retrieved_context,
    get_best_similarity,
    retrieve_relevant_chunks,
)

# ── RetrievalResult ────────────────────────────────────────────────────────────

class TestRetrievalResult:
    def _make_result(self, source="doc.pdf", page=0, text="hello", similarity=0.9, distance=0.2):
        doc = Document(
            page_content=text,
            metadata={"source": source, "page": page},
        )
        return RetrievalResult(document=doc, similarity=similarity, distance=distance)

    def test_source_property(self):
        r = self._make_result(source="guide.pdf")
        assert r.source == "guide.pdf"

    def test_page_property_converts_0indexed_to_1indexed(self):
        """page stored as 0 → displayed as 1."""
        r = self._make_result(page=0)
        assert r.page == 1

    def test_page_property_page_5(self):
        """page stored as 4 → displayed as 5."""
        r = self._make_result(page=4)
        assert r.page == 5

    def test_text_property_strips_whitespace(self):
        r = self._make_result(text="  content  ")
        assert r.text == "content"

    def test_similarity_stored_correctly(self):
        r = self._make_result(similarity=0.75)
        assert r.similarity == pytest.approx(0.75)

    def test_distance_stored_correctly(self):
        r = self._make_result(distance=0.5)
        assert r.distance == pytest.approx(0.5)

    def test_missing_source_defaults(self):
        doc = Document(page_content="x", metadata={"page": 0})
        r = RetrievalResult(document=doc, similarity=0.5, distance=1.0)
        assert r.source == "Unknown"

    def test_missing_page_defaults(self):
        doc = Document(page_content="x", metadata={"source": "f.pdf"})
        r = RetrievalResult(document=doc, similarity=0.5, distance=1.0)
        # metadata.get("page", 0) → 0 + 1 = 1
        assert r.page == 1


# ── retrieve_relevant_chunks ──────────────────────────────────────────────────

class TestRetrieveRelevantChunks:
    def _make_faiss(self, raw_results):
        """Return a mock FAISS db with pre-set similarity_search_with_score output."""
        db = MagicMock()
        db.similarity_search_with_score.return_value = raw_results
        return db

    def test_empty_query_returns_empty_list(self):
        db = self._make_faiss([])
        results = retrieve_relevant_chunks(db, "", k=4)
        assert results == []
        db.similarity_search_with_score.assert_not_called()

    def test_whitespace_query_returns_empty_list(self):
        db = self._make_faiss([])
        results = retrieve_relevant_chunks(db, "   ", k=4)
        assert results == []

    def test_returns_retrieval_result_objects(self):
        doc = Document(page_content="FAISS rocks", metadata={"source": "db.pdf", "page": 0})
        db = self._make_faiss([(doc, 0.4)])   # distance=0.4 → similarity=0.8
        results = retrieve_relevant_chunks(db, "vector database", k=4)
        assert len(results) == 1
        assert isinstance(results[0], RetrievalResult)

    def test_distance_to_similarity_conversion(self):
        """L2 distance 0.4 → similarity 1 - 0.4/2 = 0.8."""
        doc = Document(page_content="x", metadata={"source": "f.pdf", "page": 0})
        db = self._make_faiss([(doc, 0.4)])
        results = retrieve_relevant_chunks(db, "query", k=4)
        assert results[0].similarity == pytest.approx(0.8)

    def test_distance_zero_gives_similarity_one(self):
        doc = Document(page_content="x", metadata={"source": "f.pdf", "page": 0})
        db = self._make_faiss([(doc, 0.0)])
        results = retrieve_relevant_chunks(db, "query", k=4)
        assert results[0].similarity == pytest.approx(1.0)

    def test_distance_two_gives_similarity_zero(self):
        """Maximum L2 distance (2.0) → similarity 0."""
        doc = Document(page_content="x", metadata={"source": "f.pdf", "page": 0})
        db = self._make_faiss([(doc, 2.0)])
        results = retrieve_relevant_chunks(db, "query", k=4)
        assert results[0].similarity == pytest.approx(0.0)

    def test_distance_above_two_clamped_to_zero(self):
        """Distances beyond 2 are clamped to similarity 0, never negative."""
        doc = Document(page_content="x", metadata={"source": "f.pdf", "page": 0})
        db = self._make_faiss([(doc, 3.0)])
        results = retrieve_relevant_chunks(db, "query", k=4)
        assert results[0].similarity == pytest.approx(0.0)

    def test_threshold_filters_low_similarity(self):
        """Chunks below the threshold are excluded."""
        docs = [
            (Document(page_content="good", metadata={"source": "a.pdf", "page": 0}), 0.2),  # sim=0.9
            (Document(page_content="bad",  metadata={"source": "b.pdf", "page": 0}), 1.6),  # sim=0.2
        ]
        db = self._make_faiss(docs)
        results = retrieve_relevant_chunks(db, "query", k=4, threshold=0.5)
        assert len(results) == 1
        assert results[0].text == "good"

    def test_threshold_zero_returns_all(self):
        """threshold=0 (default) returns all results."""
        docs = [
            (Document(page_content="a", metadata={"source": "f.pdf", "page": 0}), 1.9),
            (Document(page_content="b", metadata={"source": "f.pdf", "page": 1}), 0.1),
        ]
        db = self._make_faiss(docs)
        results = retrieve_relevant_chunks(db, "query", k=4, threshold=0.0)
        assert len(results) == 2

    def test_results_sorted_descending_by_similarity(self):
        """Results must be ordered best-first regardless of FAISS's raw order."""
        docs = [
            (Document(page_content="low",  metadata={"source": "f.pdf", "page": 0}), 1.6),  # sim=0.2
            (Document(page_content="high", metadata={"source": "f.pdf", "page": 1}), 0.2),  # sim=0.9
        ]
        db = self._make_faiss(docs)
        results = retrieve_relevant_chunks(db, "query", k=4)
        assert results[0].similarity > results[1].similarity
        assert results[0].text == "high"

    def test_faiss_exception_returns_empty_list(self):
        db = MagicMock()
        db.similarity_search_with_score.side_effect = RuntimeError("FAISS index corrupted")
        results = retrieve_relevant_chunks(db, "query", k=4)
        assert results == []


# ── get_best_similarity ────────────────────────────────────────────────────────

class TestGetBestSimilarity:
    def _result(self, similarity):
        doc = Document(page_content="x", metadata={"source": "f.pdf", "page": 0})
        return RetrievalResult(document=doc, similarity=similarity, distance=0.0)

    def test_empty_list_returns_zero(self):
        assert get_best_similarity([]) == pytest.approx(0.0)

    def test_single_result(self):
        assert get_best_similarity([self._result(0.75)]) == pytest.approx(0.75)

    def test_returns_highest(self):
        results = [self._result(0.5), self._result(0.9), self._result(0.3)]
        # Pre-sort as retrieve_relevant_chunks would
        results.sort(key=lambda r: r.similarity, reverse=True)
        assert get_best_similarity(results) == pytest.approx(0.9)


# ── format_retrieved_context ──────────────────────────────────────────────────

class TestFormatRetrievedContext:
    def _result(self, source, page_stored, text, similarity):
        """page_stored is 0-indexed (as stored in metadata)."""
        doc = Document(
            page_content=text,
            metadata={"source": source, "page": page_stored},
        )
        return RetrievalResult(document=doc, similarity=similarity, distance=0.0)

    def test_empty_results(self):
        ctx, citations, avg = format_retrieved_context([])
        assert ctx == ""
        assert citations == []
        assert avg == pytest.approx(0.0)

    def test_page_numbers_are_1_indexed_in_citations(self):
        """
        Page stored as 0 → displayed as 1 in citations.
        This was ambiguous before the Phase 2 fix.
        """
        results = [self._result("guide.pdf", page_stored=0, text="content", similarity=0.8)]
        _, citations, _ = format_retrieved_context(results)
        assert citations[0]["page"] == 1

    def test_page_stored_4_displayed_5(self):
        results = [self._result("guide.pdf", page_stored=4, text="content", similarity=0.8)]
        _, citations, _ = format_retrieved_context(results)
        assert citations[0]["page"] == 5

    def test_context_includes_source_and_page(self):
        results = [self._result("rag.pdf", page_stored=2, text="RAG overview", similarity=0.9)]
        ctx, _, _ = format_retrieved_context(results)
        assert "rag.pdf" in ctx
        assert "Page 3" in ctx   # 2 + 1
        assert "RAG overview" in ctx

    def test_citation_snippet_capped_at_200_chars(self):
        long_text = "A" * 500
        results = [self._result("f.pdf", page_stored=0, text=long_text, similarity=0.5)]
        _, citations, _ = format_retrieved_context(results)
        assert len(citations[0]["snippet"]) <= 204  # 200 + "…"

    def test_citation_snippet_no_ellipsis_when_short(self):
        short_text = "Short text."
        results = [self._result("f.pdf", page_stored=0, text=short_text, similarity=0.5)]
        _, citations, _ = format_retrieved_context(results)
        assert citations[0]["snippet"] == short_text

    def test_avg_similarity_correct(self):
        results = [
            self._result("a.pdf", 0, "aaa", 0.8),
            self._result("b.pdf", 0, "bbb", 0.6),
        ]
        _, _, avg = format_retrieved_context(results)
        assert avg == pytest.approx(0.7)

    def test_citation_ids_are_sequential_from_1(self):
        results = [
            self._result("a.pdf", 0, "aaa", 0.8),
            self._result("b.pdf", 0, "bbb", 0.6),
            self._result("c.pdf", 0, "ccc", 0.4),
        ]
        _, citations, _ = format_retrieved_context(results)
        assert [c["id"] for c in citations] == [1, 2, 3]

    def test_citation_score_is_plain_float(self):
        """Scores must be plain Python floats, not numpy types."""
        results = [self._result("f.pdf", 0, "text", 0.75)]
        _, citations, _ = format_retrieved_context(results)
        assert isinstance(citations[0]["score"], float)
        assert not hasattr(citations[0]["score"], "item")  # not a numpy scalar
