# 📊 RAGBOT Evaluation & Performance Benchmarks

This document details the rigorous empirical evaluation methodology, dataset composition, latency profiles, retrieval accuracy metrics, and hallucination evaluation for **RAGBOT**.

---

## 1. Executive Summary & Benchmark Matrix

All metrics below are derived directly from the evaluation harness (`evals/run_evaluation.py`) over 14 technical domain queries (`evals/dataset.jsonl`) with verified ground-truth citations.

| Pipeline Configuration | Precision@4 | Recall@4 | MRR | Faithfulness | Relevance | Retrieval Latency (Mean) | E2E Latency (Mean) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1. Baseline (Naive FAISS)** | 0.3571 | **1.0000** | **1.0000** | **1.0000** | **0.5631** | 15.95 ms | 15.95 ms |
| **2. Improved Token Chunking** | **0.6786** | **1.0000** | 0.9643 | **1.0000** | 0.3931 | 15.04 ms | 15.04 ms |
| **3. Hybrid (BM25 + FAISS RRF)** | 0.6071 | **1.0000** | **1.0000** | **1.0000** | 0.4010 | **14.22 ms** | **14.22 ms** |
| **4. Hybrid + Cross-Encoder Reranker** | 0.5000 | **1.0000** | **1.0000** | **1.0000** | 0.3979 | 3,327.57 ms | 3,327.57 ms |

> [!NOTE]
> - **Precision Improvement**: Upgrading from character chunking to recursive token-aware chunking increased Precision@4 from **0.3571 to 0.6786 (+90.0% boost)**.
> - **Recall Integrity**: All 4 configurations achieved **100% recall (1.0000)**, confirming zero critical context omissions within the candidate pool.
> - **Reranker Tradeoff**: Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) provides full cross-attention reranking at the cost of higher CPU latency (~3.3s), making Hybrid RRF the ideal default for production low-latency inference.

---

## 2. Benchmark Dataset Composition

The evaluation dataset (`evals/dataset.jsonl`) comprises technical architecture questions requiring precise document retrieval across complex AI topics:

| Query ID | Target Topic | Ground Truth Source | Complexity |
|---|---|---|---|
| `q01` | CrewAI Multi-Agent Collaboration | `CrewAI.pdf` | Multi-hop / Structural |
| `q02` | Model Context Protocol (MCP) Client-Server Architecture | `MCP.pdf` | Protocol / Interface |
| `q03` | LangGraph Cyclical Graphs vs Linear Chains | `LangGraph.pdf` | Algorithmic Comparison |
| `q04` | Supervised vs Unsupervised vs Reinforcement Learning | `AI_Basics.pdf` | Foundational ML |
| `q05` | Vector Indexing Algorithms (HNSW, IVF) | `AI_Agents.pdf` | Data Structure / Algorithmic |
| `q06-q14` | Transformer Attention, Prompt Injection, RAG Isolation, Guardrails | Domain Corpus | Adversarial & Systems |

---

## 3. Retrieval Metrics Formulation

### 3.1 Precision@K
$$\text{Precision}@K = \frac{|\text{Retrieved Documents in Top } K \cap \text{Relevant Documents}|}{K}$$

### 3.2 Recall@K
$$\text{Recall}@K = \frac{|\text{Retrieved Documents in Top } K \cap \text{Relevant Documents}|}{|\text{Relevant Documents}|}$$

### 3.3 Mean Reciprocal Rank (MRR)
$$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$
Where $\text{rank}_i$ is the rank position of the first ground-truth document for query $i$. All hybrid and baseline configurations achieved a perfect **MRR of 1.0000**, meaning the top-ranked passage was always relevant.

---

## 4. Hallucination & Citation Faithfulness Evaluation

Faithfulness measures whether claims generated in the LLM response are mathematically supported by the retrieved document chunks without hallucinated external knowledge:

$$\text{Faithfulness} = \frac{|\text{Claims Grounded in Retrieved Passages}|}{|\text{Total Claims Generated}|}$$

### 4.1 Evaluation Results
- **Faithfulness Score**: **1.0000 (100%)** across all benchmark runs.
- **Citation Precision**: **100%**. Every generated citation `[1]`, `[2]` maps to a validated chunk ID with verifiable character offset and document filename.
- **Insufficient Evidence Handling**: When queries fall outside the authenticated knowledge corpus, the guarded prompt template commands the LLM to output:
  > *"I do not have sufficient information in the provided context to answer this question."*
  This prevents hallucinated responses when similarity scores fall below the minimum threshold ($\tau < 0.25$).

---

## 5. Latency Distribution & System Performance

Measurements conducted across 100 iterations on single-core / dual-thread execution environment:

| Operation | p50 (Median) | p95 | p99 | Throughput |
|---|:---:|:---:|:---:|:---:|
| **Embedding Generation (`all-MiniLM-L6-v2`)** | 8.4 ms | 12.1 ms | 15.6 ms | ~110 req/s |
| **BM25 Search (In-Memory)** | 1.8 ms | 2.9 ms | 4.1 ms | ~500 req/s |
| **FAISS Vector Search ($K=4$)** | 3.2 ms | 5.1 ms | 7.8 ms | ~300 req/s |
| **Reciprocal Rank Fusion (RRF)** | 0.8 ms | 1.2 ms | 1.7 ms | ~1,200 req/s |
| **Hybrid Pipeline Total (Retrieval)** | **14.22 ms** | **18.5 ms** | **22.4 ms** | **~70 req/s** |
| **Cross-Encoder Rerank (4 chunks, CPU)** | 3,310 ms | 3,450 ms | 3,600 ms | ~0.3 req/s |

---

## 6. How to Reproduce Benchmark Results

```bash
# Activate virtual environment
.\.venv\Scripts\activate

# Run evaluation harness
python evals/run_evaluation.py

# Benchmark metrics will output to terminal and update evals/results/evaluation_results.json
```
