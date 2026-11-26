"""Verify evaluation orchestration using deterministic test retrieval results."""
from langchain_core.documents import Document

from evals import run_evaluation as runner
from src.retriever import RetrievalResult


def test_evaluation_configuration_offline():
    result = RetrievalResult(document=Document(page_content="FAISS supports vector search.", metadata={"source": "guide.pdf"}), similarity=0.9, distance=0.1)
    dataset = [{"id": "q1", "question": "What does FAISS support?", "expected_sources": ["guide.pdf"], "ground_truth_answer": "vector search"}]
    report = runner.evaluate_configuration("fixture", dataset, lambda q, k: [result], k=1, generate_answers=False)
    assert report["queries_evaluated"] == 1
    assert report["mean_precision_at_k"] == 1.0
    assert report["mean_recall_at_k"] == 1.0
    assert report["mean_reciprocal_rank"] == 1.0
    assert report["mean_retrieval_latency_ms"] >= 0


def test_dataset_file_loading(tmp_path, monkeypatch):
    path = tmp_path / "dataset.jsonl"
    path.write_text('{"id":"q1","question":"test"}\n\n', encoding="utf-8")
    monkeypatch.setattr(runner, "DATASET_PATH", path)
    assert runner.load_dataset() == [{"id": "q1", "question": "test"}]
