# RAGBOT — Comprehensive Testing & Quality Verification Guide

This guide details how to execute the automated test suites, security scans, type checking, linting, and quantitative RAG evaluations for RAGBOT.

---

## 1. Prerequisites

Ensure your Python virtual environment and Node dependencies are configured:

```bash
# Backend virtual environment
python -m venv .venv
.\.venv\Scripts\activate      # Windows
source .venv/bin/activate       # Linux/macOS

# Install dependencies including test tools
pip install -r requirements.txt
pip install ruff mypy bandit pip-audit pytest-cov
```

---

## 2. Automated Test Suite

RAGBOT includes **209 automated unit and integration tests** covering API routes, security boundaries, vector retrieval, and prompt injection defenses:

```bash
# Run all tests with standard verbose output
pytest tests/ -v

# Run tests with code coverage report
pytest tests/ --cov=api --cov=services --cov=src --cov-report=term-missing

# Run only authentication and security tests
pytest tests/test_auth_security.py -v

# Run only cross-user data isolation tests
pytest tests/test_data_isolation.py -v

# Run adversarial prompt injection & upload security tests
pytest tests/test_prompt_injection.py -v

# Run complete end-to-end document lifecycle test
pytest tests/test_document_lifecycle.py -v
```

---

## 3. Static Security & Dependency Auditing

### Python AST Security Analysis (Bandit)
Scans Python abstract syntax trees for common security weaknesses (OWASP Top 10):
```bash
bandit -r api services src -ll
```
*Expected: 0 Medium, 0 High severity issues.*

### Python Dependency Vulnerability Scan (Pip-Audit)
Queries the PyPI Vulnerability Advisory database for known CVEs:
```bash
pip-audit -r requirements.txt
```
*Expected: "No known vulnerabilities found".*

### Frontend Dependency Vulnerability Scan (npm audit)
```bash
cd frontend
npm audit
```

---

## 4. Code Quality, Formatting & Static Typing

### Ruff Linter & Formatter
```bash
ruff check .
```

### MyPy Strict Static Type Analysis
```bash
mypy --explicit-package-bases api services src
```

### TypeScript Compiler Verification
```bash
cd frontend
npx tsc --noEmit
```

---

## 5. Quantitative RAG Benchmark Evaluation

RAGBOT includes an automated evaluation harness testing 14 benchmark technical questions across 4 pipeline architectures:
1. Pure dense FAISS baseline
2. Improved token-aware chunking
3. Hybrid BM25 + FAISS (Reciprocal Rank Fusion)
4. Hybrid + Cross-Encoder Reranker

To execute the quantitative evaluation benchmark:
```bash
python evals/run_evaluation.py
```
Results are exported to `evals/results/evaluation_results.json` measuring:
- **Precision@K** & **Recall@K**
- **Mean Reciprocal Rank (MRR)**
- **Context Faithfulness** & **Answer Relevance**
- **Retrieval Latency** & **End-to-End Latency**
