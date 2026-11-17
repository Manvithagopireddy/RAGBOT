"""
retrieval_service.py — Retrieval and Diagnostics Service.

Provides unified semantic and keyword retrieval operations,
diagnostic tracing, and index statistics for both API routes
and the Streamlit UI.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from langchain_community.vectorstores import FAISS

from config.settings import (
    HYBRID_SEARCH_ENABLED,
    RERANKING_ENABLED,
    RETRIEVER_K,
)
from rag import retrieve_and_rerank
from src.bm25_retriever import BM25Retriever
from src.logger import get_logger
from src.retriever import RetrievalResult
from vectorstore import get_or_build_bm25_retriever, get_or_build_vector_store

logger = get_logger(__name__)


class RetrievalService:
    """
    Manages vector and hybrid retrieval across FAISS and BM25 indexes.
    """

    def __init__(
        self,
        faiss_store: Optional[FAISS] = None,
        bm25_retriever: Optional[BM25Retriever] = None,
    ):
        self._faiss = faiss_store
        self._bm25 = bm25_retriever

    @property
    def faiss_store(self) -> Optional[FAISS]:
        if self._faiss is None:
            self._faiss = get_or_build_vector_store()
        return self._faiss

    @property
    def bm25_retriever(self) -> Optional[BM25Retriever]:
        if self._bm25 is None:
            self._bm25 = get_or_build_bm25_retriever()
        return self._bm25

    def set_indexes(self, faiss_store: Optional[FAISS], bm25: Optional[BM25Retriever]):
        """Updates in-memory index references after new uploads or rebuilds."""
        self._faiss = faiss_store
        self._bm25 = bm25

    def retrieve(
        self,
        query: str,
        k: int = RETRIEVER_K,
        threshold: float = 0.0,
        hybrid: bool = HYBRID_SEARCH_ENABLED,
        rerank: bool = RERANKING_ENABLED,
    ) -> Tuple[List[RetrievalResult], Dict[str, Any]]:
        """
        Executes hybrid or dense retrieval with timing diagnostics.
        Returns:
            (results, diagnostics_dict)
        """
        start_time = time.perf_counter()
        db = self.faiss_store
        bm25 = self.bm25_retriever

        results = retrieve_and_rerank(
            query=query,
            db=db,
            bm25=bm25,
            k=k,
            threshold=threshold,
            hybrid=hybrid,
            rerank=rerank,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        diagnostics = {
            "query": query,
            "k_requested": k,
            "results_returned": len(results),
            "hybrid_enabled": hybrid and (bm25 is not None),
            "rerank_enabled": rerank,
            "latency_ms": round(elapsed_ms, 2),
            "sources": list(dict.fromkeys(r.source for r in results)),
            "top_similarity": round(results[0].similarity, 4) if results else 0.0,
        }
        return results, diagnostics

    def get_index_stats(self) -> Dict[str, Any]:
        """Returns statistics on active FAISS and BM25 indexes without forcing slow model loads."""
        from config.settings import BM25_INDEX_PATH, FAISS_INDEX_PATH

        faiss_active = (self._faiss is not None) or FAISS_INDEX_PATH.exists()
        bm25_active = (self._bm25 is not None) or BM25_INDEX_PATH.exists()

        faiss_doc_count = 0
        if self._faiss is not None and hasattr(self._faiss, "index"):
            faiss_doc_count = self._faiss.index.ntotal

        bm25_doc_count = 0
        if self._bm25 is not None and self._bm25.documents:
            bm25_doc_count = len(self._bm25.documents)

        return {
            "faiss_ready": bool(faiss_active),
            "bm25_ready": bool(bm25_active),
            "faiss_total_vectors": faiss_doc_count,
            "bm25_total_documents": bm25_doc_count,
        }

        return {
            "faiss_ready": faiss_active,
            "bm25_ready": bm25_active,
            "faiss_total_vectors": faiss_doc_count,
            "bm25_total_documents": bm25_doc_count,
        }


# Global singleton instance
retrieval_service = RetrievalService()
