"""
retrieval_service.py — Retrieval and Diagnostics Service with per-user isolation.

SECURITY: All retrieval operations filter results to chunks owned by the requesting
user (via document_id metadata cross-referenced with the user's document catalog).
This prevents cross-user data leakage through the shared FAISS/BM25 index.

The shared global index is used for the base knowledge base (public PDFs in
knowledge_base/). Private uploaded documents are filtered by user_id at retrieval time
using document_id metadata attached to each chunk during ingestion.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from langchain_community.vectorstores import FAISS

from config.settings import (
    BM25_INDEX_PATH,
    CHAT_DB_PATH,
    FAISS_INDEX_PATH,
    HYBRID_SEARCH_ENABLED,
    RERANKING_ENABLED,
    RETRIEVER_K,
)
from rag import retrieve_and_rerank
from src.bm25_retriever import BM25Retriever
from src.logger import get_logger
from src.retriever import RetrievalResult
from storage import ChatStore
from vectorstore import get_or_build_bm25_retriever, get_or_build_vector_store

logger = get_logger(__name__)


class RetrievalService:
    """
    Manages vector and hybrid retrieval across FAISS and BM25 indexes
    with mandatory per-user document isolation.
    """

    def __init__(
        self,
        faiss_store: Optional[FAISS] = None,
        bm25_retriever: Optional[BM25Retriever] = None,
        db_store: Optional[ChatStore] = None,
    ):
        self._faiss = faiss_store
        self._bm25 = bm25_retriever
        self._db_store = db_store

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

    def set_indexes(self, faiss_store: Optional[FAISS], bm25: Optional[BM25Retriever]) -> None:
        """Updates in-memory index references after new uploads or rebuilds."""
        self._faiss = faiss_store
        self._bm25 = bm25

    def _get_user_document_ids(self, user_id: Optional[str]) -> Optional[Set[str]]:
        """
        Returns the set of document_ids owned by user_id from the catalog,
        or None if no filtering should be applied (e.g., anonymous/knowledge-base queries).
        """
        if not user_id:
            return None
        try:
            store = self._db_store or ChatStore(CHAT_DB_PATH)
            docs = store.get_documents(user_id=user_id)
            return {doc["document_id"] for doc in docs}
        except Exception as exc:
            logger.error(f"Failed to load user document catalog for isolation filter: {exc}")
            # Fail closed: return empty set so user gets no results rather than leaking others'
            return set()

    def _filter_by_ownership(
        self,
        results: List[RetrievalResult],
        allowed_doc_ids: Optional[Set[str]],
    ) -> List[RetrievalResult]:
        """
        Filters retrieval results to only those whose document_id is in allowed_doc_ids.
        Chunks with no document_id metadata (public knowledge base) are always included.
        If allowed_doc_ids is None, all results pass through (no-auth path).
        """
        if allowed_doc_ids is None:
            return results

        filtered = []
        for r in results:
            doc_id = getattr(r, "document_id", None)
            if doc_id is None and hasattr(r, "document") and hasattr(r.document, "metadata"):
                doc_id = r.document.metadata.get("document_id")

            if doc_id is None:
                # No document_id = public knowledge-base chunk — always include
                filtered.append(r)
            elif doc_id in allowed_doc_ids:
                filtered.append(r)
            else:
                logger.debug(f"Filtered out chunk from doc_id={doc_id!r} (not owned by user)")
        return filtered

    def retrieve(
        self,
        query: str,
        k: int = RETRIEVER_K,
        threshold: float = 0.0,
        hybrid: bool = HYBRID_SEARCH_ENABLED,
        rerank: bool = RERANKING_ENABLED,
        user_id: Optional[str] = None,
    ) -> Tuple[List[RetrievalResult], Dict[str, Any]]:
        """
        Executes hybrid or dense retrieval with per-user isolation and timing diagnostics.

        SECURITY: Results are filtered to chunks belonging to user_id's documents or
        the public knowledge base. Documents belonging to other users are excluded.

        Returns:
            (results, diagnostics_dict)
        """
        start_time = time.perf_counter()
        db = self.faiss_store
        bm25 = self.bm25_retriever

        # Retrieve more candidates initially to compensate for ownership filtering
        fetch_k = max(k * 3, k + 10)
        raw_results = retrieve_and_rerank(
            query=query,
            db=db,
            bm25=bm25,
            k=fetch_k,
            threshold=threshold,
            hybrid=hybrid,
            rerank=False,  # Rerank after filtering to avoid ranking filtered-out docs
        )

        # Apply per-user ownership filter
        allowed_ids = self._get_user_document_ids(user_id)
        filtered_results = self._filter_by_ownership(raw_results, allowed_ids)

        # Apply reranking on the filtered set only
        if rerank and filtered_results:
            from src.reranker import rerank_chunks
            filtered_results = rerank_chunks(query, filtered_results, top_n=k)
        else:
            filtered_results = filtered_results[:k]

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        diagnostics = {
            "query": query,
            "k_requested": k,
            "candidates_fetched": len(raw_results),
            "results_after_isolation": len(filtered_results),
            "results_returned": len(filtered_results),
            "hybrid_enabled": hybrid and (bm25 is not None),
            "rerank_enabled": rerank,
            "user_isolation_applied": allowed_ids is not None,
            "latency_ms": round(elapsed_ms, 2),
            "sources": list(dict.fromkeys(r.source for r in filtered_results)),
            "top_similarity": round(filtered_results[0].similarity, 4) if filtered_results else 0.0,
        }
        return filtered_results, diagnostics

    def get_index_stats(self) -> Dict[str, Any]:
        """Returns statistics on active FAISS and BM25 indexes."""
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


# Global singleton instance
retrieval_service = RetrievalService()
