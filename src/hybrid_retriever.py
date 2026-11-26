"""
hybrid_retriever.py — Combines dense FAISS semantic retrieval and sparse BM25 keyword retrieval.

Implements:
  - Reciprocal Rank Fusion (RRF): RRF(d) = sum(1 / (RRF_K + rank))
  - Weighted Score Fusion: Score(d) = alpha * Dense + (1 - alpha) * Sparse
  - Configurable candidate pooling, deduplication, and threshold filtering.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Dict, List, Optional, Tuple

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from config.settings import HYBRID_ALPHA, RETRIEVER_K, RRF_K
from src.bm25_retriever import BM25Retriever
from src.logger import get_logger
from src.retriever import RetrievalResult, retrieve_relevant_chunks

logger = get_logger(__name__)


def _doc_key(doc: Document) -> str:
    """Returns a deterministic unique key for a Document chunk to deduplicate."""
    chunk_id = doc.metadata.get("chunk_id")
    if chunk_id:
        return str(chunk_id)
    source = doc.metadata.get("source", "unknown")
    page = doc.metadata.get("page", 0)
    digest = sha256(doc.page_content.strip().encode("utf-8")).hexdigest()
    return f"{source}::p{page}::{digest}"


def reciprocal_rank_fusion(
    dense_results: List[RetrievalResult],
    sparse_results: List[RetrievalResult],
    rrf_k: int = RRF_K,
    top_k: int = RETRIEVER_K,
) -> List[RetrievalResult]:
    """
    Fuses dense (FAISS) and sparse (BM25) rankings using Reciprocal Rank Fusion.

    Formula:
        RRF_score(d) = sum_{system} 1 / (rrf_k + rank(d))
    where rank is 1-indexed.
    """
    scores: Dict[str, float] = {}
    doc_map: Dict[str, Document] = {}
    dense_scores: Dict[str, float] = {}
    sparse_scores: Dict[str, float] = {}

    # Dense scoring
    for rank_0, res in enumerate(dense_results):
        key = _doc_key(res.document)
        if key in dense_scores:
            continue
        doc_map[key] = res.document
        dense_scores[key] = res.similarity
        scores[key] = scores.get(key, 0.0) + (1.0 / (rrf_k + (rank_0 + 1)))

    # Sparse scoring
    for rank_0, res in enumerate(sparse_results):
        key = _doc_key(res.document)
        if key in sparse_scores:
            continue
        doc_map[key] = res.document
        sparse_scores[key] = res.similarity
        scores[key] = scores.get(key, 0.0) + (1.0 / (rrf_k + (rank_0 + 1)))

    if not scores:
        return []

    # Theoretical maximum RRF score (rank 1 in both dense and sparse)
    max_theoretical_rrf = 2.0 / (rrf_k + 1)

    fused_results: List[RetrievalResult] = []
    for key, rrf_score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        doc = doc_map[key]
        normalized_sim = min(1.0, rrf_score / max_theoretical_rrf)
        fused_results.append(
            RetrievalResult(
                document=doc,
                similarity=float(normalized_sim),
                distance=float(1.0 - normalized_sim),
            )
        )

    return fused_results[:top_k]


def weighted_score_fusion(
    dense_results: List[RetrievalResult],
    sparse_results: List[RetrievalResult],
    alpha: float = HYBRID_ALPHA,
    top_k: int = RETRIEVER_K,
) -> List[RetrievalResult]:
    """
    Fuses results using a weighted linear combination of dense and sparse scores:
        Score(d) = alpha * Dense(d) + (1 - alpha) * Sparse(d)
    """
    doc_map: Dict[str, Document] = {}
    dense_map: Dict[str, float] = {}
    sparse_map: Dict[str, float] = {}

    for res in dense_results:
        key = _doc_key(res.document)
        doc_map[key] = res.document
        dense_map[key] = res.similarity

    for res in sparse_results:
        key = _doc_key(res.document)
        doc_map[key] = res.document
        sparse_map[key] = res.similarity

    fused: List[Tuple[Document, float]] = []
    for key, doc in doc_map.items():
        d_score = dense_map.get(key, 0.0)
        s_score = sparse_map.get(key, 0.0)
        combined = alpha * d_score + (1.0 - alpha) * s_score
        fused.append((doc, combined))

    fused.sort(key=lambda x: x[1], reverse=True)

    results = [
        RetrievalResult(
            document=doc,
            similarity=float(score),
            distance=float(max(0.0, 1.0 - score)),
        )
        for doc, score in fused[:top_k]
    ]
    return results


def retrieve_hybrid(
    db: Optional[FAISS],
    bm25: Optional[BM25Retriever],
    query: str,
    k: int = RETRIEVER_K,
    threshold: float = 0.0,
    fusion_method: str = "rrf",
    alpha: float = HYBRID_ALPHA,
) -> List[RetrievalResult]:
    """
    Performs hybrid retrieval combining FAISS dense vector search and BM25 sparse keyword search.
    If either DB or BM25 is unavailable, gracefully falls back to the available engine.
    """
    if not query or not query.strip():
        return []

    candidate_k = max(k * 2, 8)

    # 1. Dense retrieval
    dense_results: List[RetrievalResult] = []
    if db is not None:
        try:
            dense_results = retrieve_relevant_chunks(db, query, k=candidate_k, threshold=0.0)
        except Exception as e:
            logger.error(f"Dense retrieval error in hybrid search: {e}")

    # 2. Sparse retrieval
    sparse_results: List[RetrievalResult] = []
    if bm25 is not None:
        try:
            sparse_results = bm25.retrieve_as_results(query, k=candidate_k)
        except Exception as e:
            logger.error(f"Sparse retrieval error in hybrid search: {e}")

    # If only one is available, return that one directly
    if not sparse_results:
        return [r for r in dense_results if r.similarity >= threshold][:k]
    if not dense_results:
        return [r for r in sparse_results if r.similarity >= threshold][:k]

    # 3. Fusion
    if fusion_method == "weighted":
        fused = weighted_score_fusion(dense_results, sparse_results, alpha=alpha, top_k=k)
    else:
        fused = reciprocal_rank_fusion(dense_results, sparse_results, rrf_k=RRF_K, top_k=k)

    # 4. Threshold filtering
    filtered = [r for r in fused if r.similarity >= threshold]
    logger.info(
        f"Hybrid retrieval: {len(dense_results)} dense + {len(sparse_results)} sparse "
        f"→ {len(fused)} fused → {len(filtered)} above threshold ({threshold})"
    )
    return filtered[:k]
