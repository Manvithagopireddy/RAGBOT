"""
bm25_retriever.py — High-performance BM25 keyword retrieval for lexical search.

Features:
  - Tokenization with lowercasing, punctuation handling, and stopword-aware filtering.
  - BM25Okapi implementation via rank_bm25.
  - Serialization / deserialization of corpus and index to disk.
  - Structured RetrievalResult generation with normalized BM25 scores.
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import List, Optional, Tuple

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from config.settings import BM25_INDEX_PATH
from src.logger import get_logger
from src.retriever import RetrievalResult

logger = get_logger(__name__)


def tokenize(text: str) -> List[str]:
    """Tokenizes text for BM25: lowercase, strips punctuation, splits on whitespace/words."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [word for word in cleaned.split() if len(word) > 1]


class BM25Retriever:
    """Manages the BM25 index over a corpus of Document chunks."""

    def __init__(self, documents: Optional[List[Document]] = None):
        self.documents: List[Document] = documents or []
        self.corpus_tokens: List[List[str]] = [
            tokenize(doc.page_content) for doc in self.documents
        ]
        self.bm25: Optional[BM25Okapi] = (
            BM25Okapi(self.corpus_tokens) if self.corpus_tokens else None
        )

    def add_documents(self, documents: List[Document]):
        """Adds new documents and updates the BM25 index."""
        if not documents:
            return
        self.documents.extend(documents)
        new_tokens = [tokenize(doc.page_content) for doc in documents]
        self.corpus_tokens.extend(new_tokens)
        self.bm25 = BM25Okapi(self.corpus_tokens)
        logger.info(f"Updated BM25 index. Total documents: {len(self.documents)}")

    def retrieve(self, query: str, k: int = 4) -> List[Tuple[Document, float, int]]:
        """
        Retrieves top-k documents matching the query.
        Returns: List of tuples (Document, raw_bm25_score, rank_0_indexed)
        """
        if not self.bm25 or not self.documents:
            return []

        tokens = tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)
        # Pair documents with their scores and indices
        scored_docs = [
            (doc, float(score), idx)
            for idx, (doc, score) in enumerate(zip(self.documents, scores))
            if score > 0.0
        ]

        # Edge case: If BM25 IDF is zero/negative (e.g. single-document corpus where n=N),
        # fall back to token overlap scoring so exact keyword matches are never discarded.
        if not scored_docs and tokens:
            token_set = set(tokens)
            for idx, (doc, doc_toks) in enumerate(zip(self.documents, self.corpus_tokens)):
                matches = sum(1 for t in token_set if t in doc_toks)
                if matches > 0:
                    scored_docs.append((doc, float(matches), idx))

        # Sort descending by score
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        top_k = scored_docs[:k]

        return [(doc, score, rank) for rank, (doc, score, _) in enumerate(top_k)]

    def retrieve_as_results(self, query: str, k: int = 4) -> List[RetrievalResult]:
        """Returns BM25 search matches as standardized RetrievalResult objects."""
        top_k = self.retrieve(query, k=k)
        if not top_k:
            return []

        max_score = top_k[0][1] if top_k and top_k[0][1] > 0 else 1.0

        results = []
        for doc, score, _ in top_k:
            # Normalize BM25 score to [0.0, 1.0] relative to max returned score
            norm_score = max(0.0, min(1.0, score / max_score)) if max_score > 0 else 0.0
            results.append(
                RetrievalResult(
                    document=doc,
                    similarity=norm_score,
                    distance=max(0.0, 1.0 - norm_score),
                )
            )
        return results

    def save(self, filepath: Optional[Path] = None):
        """Saves documents and pre-tokenized corpus to disk."""
        target = filepath or BM25_INDEX_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as f:
            pickle.dump({"documents": self.documents, "corpus_tokens": self.corpus_tokens}, f)  # nosec
        logger.info(f"Saved BM25 index with {len(self.documents)} documents to {target}")

    @classmethod
    def load(cls, filepath: Optional[Path] = None) -> Optional[BM25Retriever]:
        """Loads BM25 index from disk."""
        target = filepath or BM25_INDEX_PATH
        if not target.exists():
            return None
        try:
            with open(target, "rb") as f:
                data = pickle.load(f)  # nosec
            retriever = cls()
            retriever.documents = data.get("documents", [])
            retriever.corpus_tokens = data.get("corpus_tokens", [])
            if retriever.corpus_tokens:
                retriever.bm25 = BM25Okapi(retriever.corpus_tokens)
            logger.info(f"Loaded BM25 index with {len(retriever.documents)} documents from {target}")
            return retriever
        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
            return None


def build_bm25_index(documents: List[Document], save_path: Optional[Path] = None) -> BM25Retriever:
    """Builds and optionally saves a BM25 index."""
    retriever = BM25Retriever(documents)
    retriever.save(save_path)
    return retriever
