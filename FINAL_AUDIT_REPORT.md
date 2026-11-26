# RAGBOT production readiness audit — 2026-11-26

Scope: targeted review of CI, Docker, API middleware, session routes, retrieval fusion, query rewriting, chat streaming and deployment configuration. This is not an independent full security audit.

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| CI optimization | Implemented, pending verification | pip cache, concurrency, job timeouts, scoped image caches |
| CPU inference | Implemented, pending verification | CPU torch index in CI and container; verify resolved packages and runtime |
| Backend functional review | Partial | CORS PATCH, zero temperature handling, query rewriting before isolated retrieval |
| RAG quality | Implemented targeted changes, pending evaluation | Stable full-content fallback identifiers, RRF duplicate handling, contextual retrieval |
| Frontend | Implemented targeted changes, pending browser testing | Mobile history/citation panels, accessible inputs, reduced motion, interrupted stream handling |
| Coverage | Unverified | New regression tests added; 95% target not claimed; inspect coverage.xml for latest run |
| Security | Partial | Required JWT secret, local-only backend and legacy service, separate legacy volumes, CORS tests and container ownership smoke checks |
| Docker | Implemented, pending validation | CPU environment, build caches, runtime HTTP checks via Nginx |
| Public deployment | Not deployed/verified | Hosting account, HTTPS, persistent volumes and actual Gemini API key required |
| Evaluation | Pending | Re-run existing evals against updated retrieval and report measured results |
| Production readiness | Not certified | Latest CI, runtime integration, security review, real document upload and real generation must pass |

## Validation commands
- `ruff check .`
- `mypy --explicit-package-bases api services src`
- `bandit -r api services src -ll`
- `pip-audit`
- `pytest tests/ --cov=. --cov-report=term-missing --cov-report=xml`
- `cd frontend && npm ci && npm run build`
- Docker workflow builds both images and runs `scripts/container_smoke.py` against a disposable stack.
- Re-run the evaluation using the instructions in docs/rag_evaluation.md.

## Deployment requirements
Set GOOGLE_API_KEY and a cryptographically random JWT_SECRET_KEY in an untracked .env. Run docker compose up --build -d. Configure HTTPS and access restrictions before exposing the frontend publicly. Legacy Streamlit is opt-in and uses separate storage. Never use the mock CI key in production.

No new coverage, performance, vulnerability or evaluation numbers are asserted here. Review PR #2 and its latest workflow results before merge. Public deployment and real-model testing require an authorized hosting environment and credentials.
