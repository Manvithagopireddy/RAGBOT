"""
tests/test_eval_metrics.py
Unit tests for evaluation metrics: Precision@K, Recall@K, MRR, Faithfulness, Answer Relevance.
"""
import pytest

from evals.metrics import (
    calculate_answer_relevance,
    calculate_faithfulness,
    calculate_precision_at_k,
    calculate_recall_at_k,
    calculate_reciprocal_rank,
)


class TestEvalMetrics:
    def test_precision_at_k(self):
        retrieved = ["docA.pdf", "docB.pdf", "docC.pdf", "docD.pdf"]
        expected = ["docA.pdf", "docC.pdf"]
        # In top-4, 2 of 4 are relevant -> 2/4 = 0.5
        p4 = calculate_precision_at_k(retrieved, expected, k=4)
        assert p4 == pytest.approx(0.5)

        # In top-2, 1 of 2 is relevant -> 1/2 = 0.5
        p2 = calculate_precision_at_k(retrieved, expected, k=2)
        assert p2 == pytest.approx(0.5)

        # In top-1, 1 of 1 is relevant -> 1/1 = 1.0
        p1 = calculate_precision_at_k(retrieved, expected, k=1)
        assert p1 == pytest.approx(1.0)

    def test_recall_at_k(self):
        retrieved = ["docA.pdf", "docB.pdf", "docC.pdf"]
        expected = ["docA.pdf", "docC.pdf", "docE.pdf"]
        # Retrieved 2 out of 3 expected -> 2/3
        r3 = calculate_recall_at_k(retrieved, expected, k=3)
        assert r3 == pytest.approx(2.0 / 3.0)

        # Top-1 retrieved docA -> 1/3
        r1 = calculate_recall_at_k(retrieved, expected, k=1)
        assert r1 == pytest.approx(1.0 / 3.0)

    def test_reciprocal_rank(self):
        # Relevant doc at rank 1 -> 1/1 = 1.0
        assert calculate_reciprocal_rank(["hit.pdf", "miss.pdf"], ["hit.pdf"]) == pytest.approx(1.0)
        # Relevant doc at rank 2 -> 1/2 = 0.5
        assert calculate_reciprocal_rank(["miss.pdf", "hit.pdf"], ["hit.pdf"]) == pytest.approx(0.5)
        # Relevant doc at rank 4 -> 1/4 = 0.25
        assert calculate_reciprocal_rank(["m1", "m2", "m3", "hit.pdf"], ["hit.pdf"]) == pytest.approx(0.25)
        # Not found -> 0.0
        assert calculate_reciprocal_rank(["m1", "m2"], ["hit.pdf"]) == pytest.approx(0.0)

    def test_faithfulness_grounded(self):
        context = "LangGraph is designed for cyclical agent workflows with state graphs and persistence checkpoints."
        answer = "LangGraph enables cyclical agent workflows using state graphs and checkpoints."
        score = calculate_faithfulness(answer, context)
        assert score >= 0.8

    def test_faithfulness_hallucinated(self):
        context = "LangGraph is designed for cyclical agent workflows."
        answer = "Cooking pasta requires boiling water and olive oil with parmesan cheese."
        score = calculate_faithfulness(answer, context)
        assert score == pytest.approx(0.0)

    def test_answer_relevance(self):
        question = "What is CrewAI and how does it organize multi-agent collaboration?"
        answer = "CrewAI orchestrates multi-agent collaboration through role-playing agents, tasks, and crews."
        gt = "CrewAI framework organizes autonomous agents with roles and goals."
        score = calculate_answer_relevance(answer, question, ground_truth=gt)
        assert score >= 0.4
