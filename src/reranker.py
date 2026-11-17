"""
reranker.py — Neural Cross-Encoder and heuristic reranking for retrieved chunks.

Features:
  - Cross-Encoder reranking via sentence_transformers.CrossEncoder
    (defaults to 'cross-encoder/ms-marco-MiniLM-L-6-v2').
  - Singleton model caching with CPU execution safety.
  - Graceful fallback to heuristic term-coverage / dense-score reranking if neural model unavailable.
  - Configurable top-N reranked results.
"""
from __future__ import annotations

import math
from typing import List

from config.settings import RERANK_TOP_K, RERANKER_MODEL_NAME, RERANKING_ENABLED
from src.logger import get_logger
from src.retriever import RetrievalResult

logger = get_logger(__name__)

_reranker_instance = None
_reranker_failed = False


def _get_cross_encoder():
    """Initializes and caches the CrossEncoder model singleton."""
    global _reranker_instance, _reranker_failed
    if _reranker_failed:
        return None
    if _reranker_instance is None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading CrossEncoder reranker: {RERANKER_MODEL_NAME}...")
            _reranker_instance = CrossEncoder(RERANKER_MODEL_NAME, max_length=512, device="cpu")
            logger.info("CrossEncoder reranker loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load CrossEncoder model ({e}). Using heuristic reranker fallback.")
            _reranker_failed = True
            return None
    return _reranker_instance


def _sigmoid(x: float) -> float:
    """Standard sigmoid to map raw cross-encoder logits into [0.0, 1.0]."""
    return 1.0 / (1.0 + math.exp(-max(-15.0, min(15.0, x))))


def rerank_chunks(
    query: str,
    results: List[RetrievalResult],
    top_n: int = RERANK_TOP_K,
    enabled: bool = RERANKING_ENABLED,
) -> List[RetrievalResult]:
    """
    Reranks candidate RetrievalResult chunks against the query using a Cross-Encoder.
    Falls back to heuristic term-overlap / dense-score reranking if the neural model is disabled or unavailable.
    """
    if not results or not enabled:
        return results[:top_n]

    cross_encoder = _get_cross_encoder()

    if cross_encoder is not None:
        try:
            pairs = [(query, r.document.page_content) for r in results]
            scores = cross_encoder.predict(pairs)

            reranked = []
            for r, raw_score in zip(results, scores):
                norm_score = float(_sigmoid(float(raw_score)))
                reranked.append(
                    RetrievalResult(
                        document=r.document,
                        similarity=norm_score,
                        distance=max(0.0, 1.0 - norm_score),
                    )
                )

            reranked.sort(key=lambda x: x.similarity, reverse=True)
            logger.info(f"CrossEncoder reranked {len(results)} chunks → top {min(top_n, len(reranked))}")
            return reranked[:top_n]
        except Exception as e:
            logger.error(f"Error during CrossEncoder reranking: {e}. Falling back to heuristic reranking.")

    # Heuristic fallback: boost by query term overlap and original similarity
    query_terms = set(query.lower().split())
    scored = []
    for r in results:
        content_lower = r.document.page_content.lower()
        overlap = sum(1 for term in query_terms if term in content_lower) / max(len(query_terms), 1)
        combined_score = 0.6 * r.similarity + 0.4 * overlap
        scored.append(
            RetrievalResult(
                document=r.document,
                similarity=float(combined_score),
                distance=float(max(0.0, 1.0 - combined_score)),
            )
        )

    scored.sort(key=lambda x: x.similarity, reverse=True)
    return scored[:top_n]
