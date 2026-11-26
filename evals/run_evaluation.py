"""
run_evaluation.py — Comprehensive RAG Architecture Evaluation Runner.

Compares 4 Pipeline Configurations:
  1. FAISS baseline (character-based recursive splitting, pure dense vector retrieval)
  2. Improved chunking (token-aware splitting, pure dense vector retrieval)
  3. Hybrid BM25 + FAISS retrieval (Reciprocal Rank Fusion)
  4. Hybrid retrieval with reranking (Hybrid + Reranker)

Metrics Evaluated:
  - Precision@K
  - Recall@K
  - Mean Reciprocal Rank (MRR)
  - Faithfulness
  - Answer Relevance
  - Retrieval Latency (ms)
  - End-to-End Latency (ms)

Results are saved to: evals/results/evaluation_results.json
"""
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from typing import Any, Dict, List

from langchain_community.vectorstores import FAISS

from config.settings import (
    BASE_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEFAULT_MODEL,
    KNOWLEDGE_BASE_DIR,
    TOKEN_CHUNK_OVERLAP,
    TOKEN_CHUNK_SIZE,
)
from evals.metrics import (
    calculate_answer_relevance,
    calculate_faithfulness,
    calculate_precision_at_k,
    calculate_recall_at_k,
    calculate_reciprocal_rank,
)
from src.bm25_retriever import BM25Retriever
from src.context_manager import construct_guarded_context
from src.document_loader import load_all_documents
from src.embeddings import get_embeddings
from src.hybrid_retriever import retrieve_hybrid
from src.logger import get_logger
from src.reranker import rerank_chunks
from src.retriever import RetrievalResult, retrieve_relevant_chunks
from src.text_splitter import split_documents

logger = get_logger(__name__)

DATASET_PATH = BASE_DIR / "evals" / "dataset.jsonl"
RESULTS_DIR = BASE_DIR / "evals" / "results"
RESULTS_FILE = RESULTS_DIR / "evaluation_results.json"


def load_dataset() -> List[Dict[str, Any]]:
    """Loads evaluation dataset from jsonl file."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATASET_PATH}")
    items = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line.strip()))
    logger.info(f"Loaded {len(items)} evaluation queries from {DATASET_PATH}")
    return items


def setup_indices() -> Dict[str, Any]:
    """Builds test corpora and indices for the 4 benchmark configurations."""
    raw_docs = load_all_documents(KNOWLEDGE_BASE_DIR)
    if not raw_docs:
        raise ValueError(f"No documents found in {KNOWLEDGE_BASE_DIR}. Please check knowledge base.")

    embeddings = get_embeddings()

    # 1. Baseline chunks (character-based)
    baseline_chunks = split_documents(
        raw_docs, method="character", chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    baseline_faiss = FAISS.from_documents(baseline_chunks, embeddings)

    # 2. Improved chunks (token-aware)
    improved_chunks = split_documents(
        raw_docs, method="token", chunk_size=TOKEN_CHUNK_SIZE, chunk_overlap=TOKEN_CHUNK_OVERLAP
    )
    improved_faiss = FAISS.from_documents(improved_chunks, embeddings)

    # 3. BM25 index over improved chunks
    bm25_index = BM25Retriever(improved_chunks)

    return {
        "baseline_faiss": baseline_faiss,
        "improved_faiss": improved_faiss,
        "bm25_index": bm25_index,
    }


def evaluate_configuration(
    name: str,
    dataset: List[Dict[str, Any]],
    retrieve_fn,
    k: int = 4,
    generate_answers: bool = True,
) -> Dict[str, Any]:
    """Runs evaluation on a specific configuration across all dataset questions."""
    logger.info(f"=== Evaluating Configuration: {name} (K={k}) ===")

    total_precision = 0.0
    total_recall = 0.0
    total_mrr = 0.0
    total_faithfulness = 0.0
    total_relevance = 0.0
    total_retrieval_ms = 0.0
    total_e2e_ms = 0.0

    query_details = []

    for item in dataset:
        qid = item["id"]
        question = item["question"]
        expected_sources = item.get("expected_sources", [])
        gt_answer = item.get("ground_truth_answer", "")

        # ── 1. Retrieval Latency Benchmark ────────────────────────────────────
        t_start = time.perf_counter()
        results: List[RetrievalResult] = retrieve_fn(question, k=k)
        retrieval_time_ms = (time.perf_counter() - t_start) * 1000.0

        retrieved_sources = [r.source for r in results]

        # ── 2. Retrieval Metrics ──────────────────────────────────────────────
        p_at_k = calculate_precision_at_k(retrieved_sources, expected_sources, k=k)
        r_at_k = calculate_recall_at_k(retrieved_sources, expected_sources, k=k)
        rr = calculate_reciprocal_rank(retrieved_sources, expected_sources)

        total_precision += p_at_k
        total_recall += r_at_k
        total_mrr += rr
        total_retrieval_ms += retrieval_time_ms

        # ── 3. Context Construction & Generation ──────────────────────────────
        context_text, citations, _ = construct_guarded_context(results)

        e2e_time_ms = retrieval_time_ms
        answer = ""
        answer_mode = "extractive"

        if generate_answers and os.environ.get("GOOGLE_API_KEY"):
            try:
                from rag import _build_prompt, _get_client
                client = _get_client()
                t_e2e_start = time.perf_counter()
                _, prompt = _build_prompt(context_text, "", question)
                resp = client.models.generate_content(
                    model=DEFAULT_MODEL,
                    contents=prompt,
                )
                e2e_time_ms = (time.perf_counter() - t_e2e_start) * 1000.0 + retrieval_time_ms
                answer = resp.text or ""
                answer_mode = "live_gemini"
            except Exception as e:
                logger.warning(f"Live Gemini generation skipped for query {qid}: {e}")
                # Extractive grounded answer fallback for offline evaluation
                answer = (results[0].text if results else "No context available.")
        else:
            # Extractive grounded baseline when offline
            answer = (results[0].text if results else "No context available.")

        # ── 4. Generation Metrics ─────────────────────────────────────────────
        faithfulness = calculate_faithfulness(answer, context_text)
        relevance = calculate_answer_relevance(answer, question, ground_truth=gt_answer)

        total_faithfulness += faithfulness
        total_relevance += relevance
        total_e2e_ms += e2e_time_ms

        query_details.append({
            "id": qid,
            "question": question,
            "expected_sources": expected_sources,
            "retrieved_sources": retrieved_sources,
            "precision_at_k": round(p_at_k, 4),
            "recall_at_k": round(r_at_k, 4),
            "reciprocal_rank": round(rr, 4),
            "answer_mode": answer_mode,
            "faithfulness": round(faithfulness, 4),
            "relevance": round(relevance, 4),
            "retrieval_latency_ms": round(retrieval_time_ms, 2),
            "e2e_latency_ms": round(e2e_time_ms, 2),
        })

    num_q = max(len(dataset), 1)

    summary = {
        "configuration": name,
        "k": k,
        "queries_evaluated": len(dataset),
        "mean_precision_at_k": round(total_precision / num_q, 4),
        "mean_recall_at_k": round(total_recall / num_q, 4),
        "mean_reciprocal_rank": round(total_mrr / num_q, 4),
        "mean_faithfulness": round(total_faithfulness / num_q, 4),
        "mean_answer_relevance": round(total_relevance / num_q, 4),
        "mean_retrieval_latency_ms": round(total_retrieval_ms / num_q, 2),
        "mean_e2e_latency_ms": round(total_e2e_ms / num_q, 2),
        "query_details": query_details,
    }

    return summary


def run_full_evaluation(k: int = 4, generate_answers: bool = True) -> Dict[str, Any]:
    """Runs evaluation across all 4 configurations and writes results to JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    dataset = load_dataset()
    indices = setup_indices()

    baseline_faiss = indices["baseline_faiss"]
    improved_faiss = indices["improved_faiss"]
    bm25_index = indices["bm25_index"]

    configurations = [
        (
            "1. FAISS Baseline",
            lambda q, k: retrieve_relevant_chunks(baseline_faiss, q, k=k),
        ),
        (
            "2. Improved Chunking",
            lambda q, k: retrieve_relevant_chunks(improved_faiss, q, k=k),
        ),
        (
            "3. Hybrid BM25 + FAISS",
            lambda q, k: retrieve_hybrid(improved_faiss, bm25_index, q, k=k),
        ),
        (
            "4. Hybrid + Reranking",
            lambda q, k: rerank_chunks(
                q,
                retrieve_hybrid(improved_faiss, bm25_index, q, k=max(k * 2, 8)),
                top_n=k,
                enabled=True,
            ),
        ),
    ]

    all_results = {}
    comparison_table = []

    for name, retrieve_fn in configurations:
        config_summary = evaluate_configuration(name, dataset, retrieve_fn, k=k, generate_answers=generate_answers)
        all_results[name] = config_summary
        comparison_table.append({
            "Configuration": name,
            "Precision@K": config_summary["mean_precision_at_k"],
            "Recall@K": config_summary["mean_recall_at_k"],
            "MRR": config_summary["mean_reciprocal_rank"],
            "Faithfulness": config_summary["mean_faithfulness"],
            "Relevance": config_summary["mean_answer_relevance"],
            "Latency (ms)": config_summary["mean_retrieval_latency_ms"],
        })

    output_payload = {
        "live_generation_requested": generate_answers,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "k": k,
        "configurations": all_results,
        "comparison_table": comparison_table,
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    logger.info(f"Evaluation results successfully saved to {RESULTS_FILE}")

    # Print summary table to stdout
    print("\n" + "=" * 90)
    print(f"{'RAG ARCHITECTURE EVALUATION RESULTS':^90}")
    print("=" * 90)
    header = f"{'Configuration':<28} | {'P@K':<6} | {'R@K':<6} | {'MRR':<6} | {'Faith':<6} | {'Relev':<6} | {'Latency':<8}"
    print(header)
    print("-" * 90)
    for row in comparison_table:
        print(
            f"{row['Configuration']:<28} | {row['Precision@K']:<6.4f} | {row['Recall@K']:<6.4f} | "
            f"{row['MRR']:<6.4f} | {row['Faithfulness']:<6.4f} | {row['Relevance']:<6.4f} | {row['Latency (ms)']:<8.2f} ms"
        )
    print("=" * 90 + "\n")

    return output_payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG retrieval evaluation")
    parser.add_argument("--offline", action="store_true", help="Use extractive answers, not Gemini")
    args = parser.parse_args()
    run_full_evaluation(generate_answers=not args.offline)
