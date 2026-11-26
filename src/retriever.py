"""
retriever.py — FAISS retrieval and context formatting.

Fixes applied (Phase 2):
  BUG-007  Eliminated the second redundant retrieval call that lived in chat.py
           by separating the routing-check path from the full-context path.
           retrieve_relevant_chunks() now accepts a threshold parameter and
           returns a RetrievalResult dataclass for structured access.

Design notes:
  • FAISS.similarity_search_with_score() returns L2 distances when the index
    was built without inner-product normalisation.
  • all-MiniLM-L6-v2 produces L2-normalised embeddings, so the theoretical
    L2 distance range is [0, 2] (0 = identical, 2 = opposite vectors).
  • We map  distance → similarity = 1.0 − d/2.0  giving a [0, 1] similarity
    score. This is CORRECT for normalised embeddings.
  • The similarity is then used as a confidence proxy. We do NOT multiply
    by 100 here — that conversion is done only at the display layer
    (utils/helpers.py:calculate_confidence_score) to keep concerns separated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from langchain_community.vectorstores import FAISS  # pyright: ignore
from langchain_core.documents import Document

from config.settings import RETRIEVER_K
from src.logger import get_logger

logger = get_logger(__name__)


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    """
    A single retrieved document chunk with its normalised similarity score.

    Attributes:
        document:   The LangChain Document containing page_content and metadata.
        similarity: Float in [0.0, 1.0]; higher = more relevant.
        distance:   Raw L2 distance from FAISS (kept for debugging).
    """
    document: Document
    similarity: float
    distance: float

    @property
    def source(self) -> str:
        return self.document.metadata.get("source", "Unknown")

    @property
    def document_id(self) -> Optional[str]:
        return self.document.metadata.get("document_id")

    @property
    def page(self) -> int:
        """1-indexed page number for display."""
        raw = self.document.metadata.get("page", 0)
        # Normalise: if stored as 0-indexed int return +1, if already 1-indexed keep.
        # We store 0-indexed during PDF load, so +1 here.
        return int(raw) + 1

    @property
    def text(self) -> str:
        return self.document.page_content.strip()


# ── Core retrieval ─────────────────────────────────────────────────────────────

def retrieve_relevant_chunks(
    db: FAISS,
    query: str,
    k: int = RETRIEVER_K,
    threshold: float = 0.0,
) -> List[RetrievalResult]:
    """
    Searches the FAISS vector store and returns up to *k* chunks whose
    similarity score meets or exceeds *threshold*.

    Args:
        db:        FAISS vector store instance.
        query:     The (possibly condensed) search query string.
        k:         Maximum number of chunks to retrieve from FAISS.
        threshold: Minimum similarity score to include in results (0.0 = all).

    Returns:
        List of RetrievalResult objects, sorted descending by similarity.
        Returns an empty list on any error so callers can handle gracefully.
    """
    if not query or not query.strip():
        logger.warning("retrieve_relevant_chunks called with empty query — returning [].")
        return []

    logger.info(f"Querying FAISS for: '{query[:80]}…' k={k}, threshold={threshold:.2f}")

    try:
        raw: List[Tuple[Document, float]] = db.similarity_search_with_score(query, k=k)
    except Exception as exc:
        logger.error(f"FAISS similarity search failed: {exc}")
        return []

    results: List[RetrievalResult] = []
    for doc, distance in raw:
        # Convert L2 distance → cosine-like similarity for normalised embeddings.
        # distance ∈ [0, 2] → similarity ∈ [1, 0]
        distance_f = float(distance)
        similarity = float(max(0.0, min(1.0, 1.0 - (distance_f / 2.0))))

        if similarity < threshold:
            logger.debug(
                f"Chunk from '{doc.metadata.get('source', '?')}' "
                f"below threshold ({similarity:.3f} < {threshold:.3f}) — skipped."
            )
            continue

        results.append(RetrievalResult(
            document=doc,
            similarity=similarity,
            distance=distance_f,
        ))

    # Sort descending by similarity (FAISS returns ascending distance, so this
    # is already roughly sorted, but we enforce it explicitly).
    results.sort(key=lambda r: r.similarity, reverse=True)

    logger.info(
        f"Retrieved {len(results)} chunk(s) above threshold "
        f"(of {len(raw)} candidates from FAISS)."
    )
    return results


def get_best_similarity(results: List[RetrievalResult]) -> float:
    """Returns the highest similarity score from a list, or 0.0 if empty."""
    if not results:
        return 0.0
    return results[0].similarity  # already sorted descending


# ── Context formatting ─────────────────────────────────────────────────────────

def format_retrieved_context(
    results: List[RetrievalResult],
) -> Tuple[str, List[Dict[str, Any]], float]:
    """
    Formats a list of RetrievalResult objects into:
      1. context_text — a prompt-ready string with labelled document blocks.
      2. citations    — list of dicts consumed by the citation UI components.
      3. avg_similarity — mean similarity across all results (0.0 if empty).

    The page numbers in citations are 1-indexed (via RetrievalResult.page).
    Snippets are capped at 200 chars to keep citations concise.
    """
    if not results:
        return "", [], 0.0

    context_parts: List[str] = []
    citations: List[Dict[str, Any]] = []
    total_score = 0.0

    for idx, result in enumerate(results):
        # Build the labelled context block for the LLM prompt
        block = (
            f"--- Document Source: {result.source} (Page {result.page}) ---\n"
            f"{result.text}\n"
        )
        context_parts.append(block)

        # Build citation dict for the UI
        snippet = result.text[:200]
        if len(result.text) > 200:
            snippet += "…"

        citations.append({
            "id":      idx + 1,
            "source":  result.source,
            "page":    result.page,
            "snippet": snippet,
            "score":   result.similarity,     # always a plain Python float
        })
        total_score += result.similarity

    context_text = "\n".join(context_parts)
    avg_similarity = total_score / len(results)

    return context_text, citations, avg_similarity


# ── Backward-compatibility shim ────────────────────────────────────────────────
# The old public API returned List[Tuple[Document, float]].  Any code that
# hasn't been updated yet can still call the legacy wrapper below.

def retrieve_relevant_chunks_legacy(
    db: FAISS,
    query: str,
    k: int = RETRIEVER_K,
) -> List[Tuple[Document, float]]:
    """
    Thin wrapper that calls retrieve_relevant_chunks() and converts the result
    back to the old (Document, float) tuple format.  Kept only for backward
    compatibility while the rest of the codebase is migrated.
    """
    results = retrieve_relevant_chunks(db, query, k=k)
    return [(r.document, r.similarity) for r in results]
