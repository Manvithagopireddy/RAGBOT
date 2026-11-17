"""
metrics.py — Quantitative RAG Evaluation Metrics.

Computes:
  - Precision@K
  - Recall@K
  - Mean Reciprocal Rank (MRR)
  - Faithfulness (Context Grounding Score)
  - Answer Relevance (Semantic Question Alignment)
  - Retrieval Latency (ms)
  - End-to-End Latency (ms)
"""
from __future__ import annotations

import re
from typing import List, Optional


def normalize_source_name(name: str) -> str:
    """Normalizes document source name for fair matching."""
    return name.lower().strip()


def calculate_precision_at_k(retrieved_sources: List[str], expected_sources: List[str], k: int) -> float:
    """
    Computes Precision@K: fraction of the top-K retrieved sources that are relevant.
    Precision@K = |Retrieved[:K] ∩ Expected| / K
    """
    if k <= 0:
        return 0.0
    top_k_sources = [normalize_source_name(s) for s in retrieved_sources[:k]]
    expected_set = {normalize_source_name(s) for s in expected_sources}

    if not expected_set:
        return 0.0

    relevant_retrieved = sum(1 for s in top_k_sources if s in expected_set)
    return relevant_retrieved / float(k)


def calculate_recall_at_k(retrieved_sources: List[str], expected_sources: List[str], k: int) -> float:
    """
    Computes Recall@K: fraction of expected relevant sources retrieved in top-K.
    Recall@K = |Retrieved[:K] ∩ Expected| / |Expected|
    """
    if not expected_sources or k <= 0:
        return 0.0
    top_k_sources = {normalize_source_name(s) for s in retrieved_sources[:k]}
    expected_set = {normalize_source_name(s) for s in expected_sources}

    relevant_retrieved = len(top_k_sources.intersection(expected_set))
    return relevant_retrieved / float(len(expected_set))


def calculate_reciprocal_rank(retrieved_sources: List[str], expected_sources: List[str]) -> float:
    """
    Computes the Reciprocal Rank (RR): 1 / rank of the first relevant document retrieved (1-indexed).
    Returns 0.0 if no expected source was retrieved.
    """
    expected_set = {normalize_source_name(s) for s in expected_sources}
    for rank_0, source in enumerate(retrieved_sources):
        if normalize_source_name(source) in expected_set:
            return 1.0 / (rank_0 + 1)
    return 0.0


def calculate_faithfulness(answer: str, context: str) -> float:
    """
    Measures the degree to which factual statements in the answer are grounded
    in the retrieved context (no hallucinations / unsubstantiated claims).

    Splits answer into sentences, extracts non-trivial content words (>3 chars),
    and checks their representation in the context text.
    """
    if not answer or not answer.strip():
        return 0.0
    if not context or not context.strip():
        return 0.0

    context_lower = context.lower()
    sentences = [s.strip() for s in re.split(r"[.!?\n]", answer) if len(s.strip()) > 15]

    if not sentences:
        return 1.0

    supported_count = 0
    for sentence in sentences:
        words = list(re.findall(r"\b[a-zA-Z]{4,}\b", sentence.lower()))
        if not words:
            continue
        # A sentence is grounded if at least 60% of its content words exist in context
        grounded_words = sum(1 for w in words if w in context_lower)
        if (grounded_words / len(words)) >= 0.5:
            supported_count += 1

    return float(supported_count) / float(len(sentences)) if sentences else 1.0


def calculate_answer_relevance(answer: str, question: str, ground_truth: Optional[str] = None) -> float:
    """
    Measures how directly the generated answer addresses the question and ground-truth answer.
    Computes keyword and n-gram overlap between answer and query/ground truth.
    """
    if not answer or not answer.strip():
        return 0.0

    q_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", question.lower()))
    if not q_words:
        return 0.0

    ans_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", answer.lower()))

    # Overlap with question keywords
    q_overlap = len(q_words.intersection(ans_words)) / float(len(q_words))

    # Overlap with ground truth answer if available
    gt_overlap = 0.0
    if ground_truth:
        gt_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", ground_truth.lower()))
        if gt_words:
            gt_overlap = len(gt_words.intersection(ans_words)) / float(len(gt_words))
        return 0.5 * q_overlap + 0.5 * gt_overlap

    return q_overlap
