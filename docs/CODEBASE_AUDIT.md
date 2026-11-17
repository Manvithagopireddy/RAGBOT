# RAGBOT — Phase 1 Codebase Audit

> **Auditor:** Antigravity AI (Senior AI Engineer + Full Stack Architect)
> **Date:** 2026-11-16
> **Repository:** https://github.com/Manvithagopireddy/RAGBOT
> **Scope:** Complete read-only inspection — no files modified during this audit

---

## Table of Contents

1. [Existing Architecture](#1-existing-architecture)
2. [File Map & Responsibility Summary](#2-file-map--responsibility-summary)
3. [Existing Working Features](#3-existing-working-features)
4. [Confirmed Bugs](#4-confirmed-bugs)
5. [Security Issues](#5-security-issues)
6. [Technical Debt](#6-technical-debt)
7. [Recommended Improvements](#7-recommended-improvements)
8. [Priority Matrix](#8-priority-matrix)
9. [Dependency Analysis](#9-dependency-analysis)
10. [CI/CD Analysis](#10-cicd-analysis)
11. [Test Coverage Analysis](#11-test-coverage-analysis)

---

## 1. Existing Architecture

### High-Level Data Flow

```
PDF/DOCX/TXT/CSV/PPTX files
        │
        ▼
  document_loader.py          ← Multi-format loader (PyPDF, python-docx, pptx, csv)
        │
        ▼
  text_splitter.py            ← RecursiveCharacterTextSplitter (chunk=800, overlap=150)
        │
        ▼
  embeddings.py               ← HuggingFace all-MiniLM-L6-v2 (singleton, CPU)
        │
        ▼
  vectorstore.py              ← FAISS index (build / load / get_or_build)
        │
════════════════════════════════════════════
              User Query (via Streamlit UI)
════════════════════════════════════════════
        │
        ▼
  components/chat.py          ← Routing decision (KB / Web / LLM)
        │
        ├─► retrieve_relevant_chunks()   src/retriever.py
        │          │
        │          ▼ similarity_search_with_score
        │     FAISS vector store
        │
        ▼
  rag.py (execute_rag_pipeline)
        │   condense_question → Gemini API (temp=0.0)
        │   build prompt (RAG_SYSTEM_PROMPT)
        │   stream tokens → Gemini 2.5 Flash
        │
        ▼
  components/chat.py          ← Stream tokens → Streamlit placeholder
        │   parse_related_questions()
        │   calculate_confidence_score()
        │
        ▼
  storage.py (ChatStore)      ← Persist to SQLite (sessions + messages)
        │
        ▼
  components/analytics.py     ← Render analytics from SQLite aggregate queries
```

### Technology Stack (Actual)

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Streamlit ≥1.30 | Glassmorphic CSS, custom JS |
| LLM | Google Gemini 2.5 Flash/Pro | Via `google-genai` SDK |
| RAG Framework | LangChain 0.1+ | FAISS, text splitting, doc loading |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace, local CPU |
| Vector DB | FAISS-CPU | Local pickle + `.faiss` index |
| Persistence | SQLite3 | Chat sessions, messages, analytics |
| Document Processing | PyPDF, python-docx, python-pptx | Multi-format |
| Container | Docker (python:3.11-slim) | Single-container, no volumes |
| CI | GitHub Actions | Syntax check + pytest |

---

## 2. File Map & Responsibility Summary

```
RAGBOT/
├── app.py                      Entry point: page config, state init, routing
├── rag.py                      Core RAG pipeline: Gemini client, streaming, web search
├── chat_manager.py             ChatMemory class: in-memory conversation history
├── storage.py                  ChatStore: SQLite CRUD for sessions + messages
├── vectorstore.py              FAISS build/load/get_or_build
├── requirements.txt            18 dependencies (no pinned versions)
├── Dockerfile                  python:3.11-slim, single stage
├── .env.example                Single GOOGLE_API_KEY variable
│
├── config/
│   ├── settings.py             Paths, model names, chunk sizes, thresholds
│   └── prompts.py              RAG_SYSTEM_PROMPT, CONDENSE_QUESTION_PROMPT, TOOL_COMPARISON_PROMPT
│
├── src/
│   ├── document_loader.py      load_pdf / txt / csv / docx / pptx / all_documents
│   ├── text_splitter.py        split_documents (RecursiveCharacterTextSplitter)
│   ├── embeddings.py           get_embeddings() — global singleton
│   ├── retriever.py            retrieve_relevant_chunks, format_retrieved_context
│   ├── file_handler.py         index_uploaded_file, get_file_size_label, get_file_icon
│   ├── llm.py                  get_llm() — UNUSED in production path
│   └── logger.py               Logging setup (stdout + file handler)
│
├── components/
│   ├── chat.py                 Main chat UI + streaming + routing
│   ├── sidebar.py              Session list, search, settings trigger
│   ├── analytics.py            Dashboard (Plotly charts from SQLite data)
│   ├── components.py           inject_custom_css, inject_all_js, UI helpers
│   ├── citations.py            render_citations, render_web_citations
│   ├── confidence.py           render_confidence_gauge
│   ├── home.py                 Welcome screen
│   ├── right_panel.py          Collapsible right panel
│   └── settings.py             Settings modal, persona presets
│
├── utils/
│   └── helpers.py              parse_related_questions, calculate_confidence_score
│
├── styles/
│   └── theme.css               40 KB custom glassmorphic CSS
│
├── knowledge_base/             14 synthetic AI-topic PDFs
├── tests/                      5 test files (pytest)
├── scripts/                    Mock PDF generator + pipeline tester
└── .github/workflows/ci.yml    CI pipeline
```

---

## 3. Existing Working Features

The following features are confirmed to exist in the codebase and appear functionally implemented:

### ✅ Core RAG Pipeline
- FAISS vector store build from local `knowledge_base/` PDFs
- Persistent load of existing FAISS index (avoids rebuild on restart)
- `all-MiniLM-L6-v2` embedding model (singleton, CPU-safe)
- `RecursiveCharacterTextSplitter` with chunk=800, overlap=150
- `retrieve_relevant_chunks` with L2→similarity score conversion
- `format_retrieved_context` returns context, citations, avg confidence

### ✅ Gemini LLM Integration
- `google-genai` SDK client (supports API keys and OAuth tokens)
- Streaming with `generate_content_stream`
- Multi-modal support (image_bytes + text in same prompt)
- Query condensation for follow-up questions (temp=0.0 non-streaming call)
- Web search grounding via `{"google_search": {}}` tool
- Fallback: web search failure → pure LLM

### ✅ Routing Logic
- 3-tier priority: KB (FAISS) → Web Search → Pure LLM
- Similarity threshold configurable (`SIMILARITY_SCORE_THRESHOLD = 0.4`)
- Source-type badge on each message: `📄 KB / 🌐 Web / 🧠 AI`

### ✅ Chat Interface (Streamlit)
- Multi-session persistent chat (SQLite)
- Session grouping: Today / Yesterday / Last 7 Days / Older
- Session search by title and content
- Session CRUD: create, rename, delete, pin, favorite, archive, duplicate
- Auto-title on first message
- Edit + regenerate any user message
- Regenerate any assistant response
- Thumbs up/down feedback per message
- Related questions / suggested follow-ups
- Right-side collapsible details panel

### ✅ File Upload & Indexing
- Supports PDF, TXT, CSV, DOCX, PPTX via chat input
- Image uploads (JPG, PNG, WEBP, GIF) → multimodal Gemini
- Files merged into session-scoped FAISS store via `merge_from()`
- Duplicate upload prevention (name-based)

### ✅ Analytics Dashboard
- Total sessions, messages, user queries
- Thumbs up/down counts
- Daily message volume (14-day trend)
- Daily confidence score trend
- Source-type distribution (KB / Web / AI)
- Model usage breakdown
- Feedback by source type
- Top 5 sessions by message count
- Sessions created per day

### ✅ SQLite Persistence (ChatStore)
- Full session lifecycle CRUD
- Message storage with citations (JSON), confidence score, description
- NumpyEncoder for safe JSON serialization of numpy float/int types
- Safe schema migration (`_safe_add_column`)
- Message pin/unpin
- Session archive/restore
- `get_sessions_grouped()` for sidebar date grouping

### ✅ UI / Styling
- Custom 40KB glassmorphic CSS (dark + light theme)
- Dynamic CSS variables injected at runtime (accent color, font size, density)
- Code block copy button (JavaScript)
- Keyboard shortcuts: `Ctrl+Shift+N` (new chat), `Ctrl+/` (focus input)
- Mobile/tablet responsive media queries

### ✅ Docker & CI
- Dockerfile present (single stage, python:3.11-slim)
- GitHub Actions CI: syntax validation + pytest on 3.11 and 3.12

---

## 4. Confirmed Bugs

### BUG-001 · CRITICAL — Broken Import in `file_handler.py`

**File:** `src/file_handler.py` — line 25

```python
from src.embeddings import load_embedding_model   # ← DOES NOT EXIST
```

**Reality:** The function in `src/embeddings.py` is named `get_embeddings()`, **not** `load_embedding_model()`.

**Impact:** Every file upload that triggers `index_uploaded_file()` will raise an `ImportError` and crash silently (the exception is caught by the outer `except Exception` block, returning `global_db` unchanged). Users who upload files will silently get **no indexing**; the spinner completes with no error shown.

**Fix:** Change line 25 of `file_handler.py` to:
```python
from src.embeddings import get_embeddings
```
And line 52 to:
```python
embeddings = get_embeddings()
```

---

### BUG-002 · HIGH — Duplicate Button Render in Same Column (`act_cols[3]`)

**File:** `components/chat.py` — lines 255–266

```python
with act_cols[3]:
    dislike_lbl = "💔 👎" if msg.get("feedback") == "down" else "👎"
    if st.button(dislike_lbl, key=f"dn_{idx}_{message_id[:8]}", ...):   # line 257

with act_cols[3]:                                                          # ← SAME column [3] reused!
    if st.button("🔗 Share", key=f"share_{idx}_{message_id[:8]}", ...):  # line 263
```

**Impact:** Both the dislike button and the share button are assigned to `act_cols[3]`. The share button silently overwrites the dislike button in the same column. The share button renders in the wrong position (overlapping or replacing dislike). The intended layout of 5 columns (Regen | — | Like | Dislike | Share) is broken.

**Fix:** Change the second `with act_cols[3]:` to `with act_cols[4]:`.

---

### BUG-003 · HIGH — `src/llm.py` Is Dead Code

**File:** `src/llm.py`

The `get_llm()` function initializes `ChatGoogleGenerativeAI` from `langchain-google-genai`. This module is **never imported or called** anywhere in the production codebase. The actual LLM calls go through `rag.py → _get_client()` using the `google-genai` SDK directly.

**Impact:** 
- `langchain-google-genai` is in `requirements.txt` adding install weight for no benefit.
- `get_llm()` passes `google_api_key=None` when the key is unset (logging a warning but proceeding), which would raise an authentication error at call time — a silent footgun for anyone who tries to use it.

---

### BUG-004 · HIGH — Unsafe File Save in `file_handler.py` (Path Traversal)

**File:** `src/file_handler.py` — line 31

```python
tmp_path = UPLOADS_DIR / f"upload_{uploaded_file.name}"
```

**Impact:** `uploaded_file.name` is user-controlled. A filename like `../../config/settings.py` or `../chats/chat_history.db` would resolve to a path outside `UPLOADS_DIR`, allowing an attacker to overwrite arbitrary project files.

**Fix:** Sanitize the filename before writing:
```python
from pathlib import PurePosixPath
safe_name = Path(uploaded_file.name).name  # strips all directory components
tmp_path = UPLOADS_DIR / f"upload_{safe_name}"
```

---

### BUG-005 · HIGH — `storage.py` `get_sessions_grouped()` Uses `datetime.utcnow()` for Comparisons But No Timezone Awareness

**File:** `storage.py` — lines 559, 573

```python
now_utc = datetime.utcnow()
...
delta = now_utc - updated   # updated is parsed from ISO string stored without timezone
```

If the SQLite `created_at`/`updated_at` strings include a timezone offset (e.g., from `datetime.now(timezone.utc).isoformat()`), `datetime.fromisoformat()` will return a timezone-aware datetime and the subtraction with `datetime.utcnow()` (naive) will raise `TypeError: can't subtract offset-naive and offset-aware datetimes`.

Currently stored times use `datetime.utcnow().isoformat()` (naive), so it works. This is a ticking time bomb: any change to use timezone-aware timestamps will break all grouping logic.

---

### BUG-006 · MEDIUM — `chat.py` Direct Access to Internal `ChatStore._connect()` 

**File:** `components/chat.py` — lines 481–486

```python
with chat_store._connect() as conn:
    conn.execute(
        "UPDATE messages SET confidence_desc = ? WHERE message_id = ?",
        (f"source:{source_type}", msg_id)
    )
    conn.commit()
```

**Impact:** This violates encapsulation by directly accessing the private `_connect()` method of `ChatStore`. This duplicates the connection-management logic spread across two different layers, bypasses `ChatStore`'s internal transaction patterns, and creates a maintenance hazard. Additionally, `confidence_desc` is already set via `add_message()` just 10 lines above, then immediately overwritten — the first write is wasted.

---

### BUG-007 · MEDIUM — Double Retrieval of Chunks per Query

**File:** `components/chat.py` — lines 371–377 and `rag.py` — line 109

```python
# In chat.py (routing decision):
results = retrieve_relevant_chunks(db, user_query, k=retriever_k)  # ← 1st retrieval

# In rag.py (pipeline):
retrieved_results = retrieve_relevant_chunks(db, standalone_query, k=retriever_k)  # ← 2nd retrieval
```

**Impact:** The retrieval step (embedding query + FAISS search) is performed **twice** per KB query. For large FAISS indexes, this doubles latency. The first retrieval uses `user_query`; the second uses `standalone_query` (condensed). The routing decision is based on the original query similarity, while actual context is from the condensed query — these can differ significantly, causing inconsistent source-type routing.

---

### BUG-008 · MEDIUM — `app.py` Re-Instantiates `ChatMemory()` as a Default Every Render

**File:** `app.py` — lines 102–103

```python
_defaults = {
    "memory": ChatMemory(),  # ← new object created on every full script re-run
    ...
}
for key, default in _defaults.items():
    if key not in st.session_state:   # ← only applied if key not set
        st.session_state[key] = default
```

While the guard `if key not in st.session_state` prevents overwriting existing state, Python evaluates the **entire dict literal** `_defaults = { ... }` on every Streamlit re-run, instantiating a new `ChatMemory()` and other objects even when they aren't needed. This is minor overhead but represents an anti-pattern.

**Fix:** Use `st.session_state.setdefault(key, factory())` with lazy evaluation, or check before creating:
```python
if "memory" not in st.session_state:
    st.session_state.memory = ChatMemory()
```

---

### BUG-009 · MEDIUM — Stale FAISS Index After Upload (Session Isolation Broken)

**File:** `src/file_handler.py` — lines 55–62

```python
if global_db is not None:
    global_db.merge_from(upload_db)   # mutates the shared global_db in-place
    return global_db
```

**Impact:** `global_db` is `st.session_state.db`, shared across all browser sessions in a multi-user Streamlit deployment. When one user uploads a file, the FAISS index is mutated globally, **affecting all other users** in the same process. In a single-user deployment this is fine, but it is a correctness and privacy issue in any shared deployment.

---

### BUG-010 · MEDIUM — `confidence_desc` Stored Incorrectly for Web and AI Answers

**File:** `components/chat.py` — lines 477–479

```python
confidence_desc=conf_desc if source_type == "📄 Knowledge Base" else "",
```

Then overwritten at line 484:
```python
(f"source:{source_type}", msg_id)
```

**Impact:** For Web Search and AI General sources, `add_message()` is called with `confidence_desc=""`, then immediately overwritten to `"source:🌐 Web Search"` or `"source:🧠 AI General Knowledge"`. The `add_message` DB write is **wasted** for every non-KB message. Worse, if the second UPDATE fails silently, the stored value will be `""` instead of the source tag, breaking analytics queries that filter by `confidence_desc LIKE 'source:%'`.

---

### BUG-011 · LOW — README Documents Non-Existent Files

**File:** `README.md` — lines 105–110

The README documents these files inside `src/`:
- `src/memory.py` — **does not exist** (actual file: `chat_manager.py` at root)
- `src/rag_pipeline.py` — **does not exist** (actual file: `rag.py` at root)
- `src/utils.py` — **does not exist** (actual file: `utils/helpers.py`)
- `src/vector_store.py` — **does not exist** (actual file: `vectorstore.py` at root)

Also lists a `ui/` folder structure that doesn't exist — the actual folder is `components/`.

---

### BUG-012 · LOW — `similarity_threshold` Uses Two Different Sources

**File:** `app.py` line 115, `components/chat.py` line 360

```python
# app.py default:
"similarity_threshold": 0.4,

# chat.py reads:
similarity_threshold = st.session_state.get("similarity_threshold", 0.4)
```

This is set in `app.py` defaults but never exposed in the UI for user modification. The settings modal (`components/settings.py`) appears to have many settings but no control for this threshold. Users cannot change this value at runtime.

---

## 5. Security Issues

### SEC-001 · CRITICAL — JavaScript XSS via Unsanitized Content Injection

**File:** `components/chat.py` — lines 220, 279, 282, 289, 292

```python
escaped = content.replace("\\", "\\\\").replace("`", "\\`").replace("'", "\\'")
...
<button onclick="navigator.clipboard.writeText(`{escaped}`)...
```

**Impact:** The escaping is **insufficient for HTML context**. The variable `escaped` is inserted directly into an HTML `onclick` attribute. The escaping only handles backtick, backslash, and single-quote — but not:
- `"` (double quotes) — can break out of HTML attributes
- `<` / `>` — can inject HTML tags 
- Newlines — can break the JavaScript expression
- Unicode special characters

If the LLM or a document produces a response containing `"` or `</button>` or `<script>`, the injected HTML will be malformed and could be exploited in a shared deployment.

**Fix:** Use Python `html.escape()` for HTML contexts, and proper JSON encoding for JS string literals:
```python
import json
js_safe = json.dumps(content)  # produces a properly quoted JS string literal
```

---

### SEC-002 · HIGH — Uploaded Files Saved Without Size Limit or Type Validation

**File:** `src/file_handler.py` — lines 30–34

```python
suffix = Path(uploaded_file.name).suffix.lower() or ".pdf"
tmp_path = UPLOADS_DIR / f"upload_{uploaded_file.name}"
with open(tmp_path, "wb") as f:
    f.write(uploaded_file.read())
```

**Issues:**
1. No maximum file size check — a 1 GB file would be fully read into memory and written to disk.
2. No MIME type validation — only the filename extension is considered. A `.pdf` file containing executable code (or a file renamed to `.pdf`) passes validation.
3. Files are written to `UPLOADS_DIR` permanently — no cleanup mechanism exists. Disk usage grows indefinitely.

---

### SEC-003 · HIGH — API Key Logging Warning Exposes Sensitive Information Path

**File:** `src/llm.py` — line 15

```python
logger.warning("GOOGLE_API_KEY not set in .env. Attempting to run with system-wide environment variables.")
```

The logger writes to both stdout **and** to `logs/app.log` (a file on disk). This is benign here since it only logs the absence of a key, but the entire `get_llm()` function passes `google_api_key=api_key` even when `api_key` is None — meaning if LangChain logs connection details, the key could appear in logs.

---

### SEC-004 · MEDIUM — `allow_dangerous_deserialization=True` for FAISS Load

**File:** `vectorstore.py` — line 58

```python
db = FAISS.load_local(..., allow_dangerous_deserialization=True)
```

This flag allows arbitrary Python pickle deserialization. If the `vector_store/index.pkl` file is replaced by a malicious actor (e.g., via path traversal in BUG-004), it could achieve Remote Code Execution. The risk is acceptable for a single-user local deployment but must be documented.

---

### SEC-005 · MEDIUM — No Content Security Policy Headers

The Streamlit app injects arbitrary HTML/JavaScript via `unsafe_allow_html=True` throughout the codebase (27 occurrences). There is no Content Security Policy (CSP) in place. Combined with SEC-001, this creates a viable XSS attack surface.

---

### SEC-006 · LOW — `.env.example` Is the Entire Secret Configuration

**File:** `.env.example`

The `.env.example` contains only one secret variable. For production deployment this is acceptable. However, there is no documentation or enforcement preventing developers from committing an actual `.env` file. The `.gitignore` does include `.env`.

---

## 6. Technical Debt

### TD-001 — No Version Pinning in `requirements.txt`

```
streamlit>=1.30.0           # any version ≥ 1.30 — breaking changes possible
langchain>=0.1.0            # major version drift risk
google-genai>=1.0.0         # SDK breaking changes in minor versions
```

**Impact:** `pip install -r requirements.txt` will install the latest compatible versions. If `streamlit 2.x` or `langchain 0.3.x` ships breaking API changes, the CI will silently install them and tests may fail in unexpected ways.

**Fix:** Pin versions with `==` or use `pip freeze > requirements-lock.txt`.

---

### TD-002 — Global Mutable Singleton for Embeddings

**File:** `src/embeddings.py` — line 8

```python
_embeddings_instance = None  # module-level global
```

This global singleton pattern breaks test isolation. Any test that calls `get_embeddings()` permanently mutates the module state. Tests must mock at the module level.

---

### TD-003 — `src/llm.py` Is Dead Code

The entire `src/llm.py` module uses `langchain-google-genai` (`ChatGoogleGenerativeAI`) but is never called in the production path. The production path uses `google-genai` directly in `rag.py`. This creates confusion: two different Gemini client libraries exist in requirements.

---

### TD-004 — `config/settings.py` Creates Directories at Import Time

```python
KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
...
```

Side effects at module import time make testing harder (directory creation during test collection), and the `logs/` directory is created by `src/logger.py` at import time too. These should be lazy or deferred.

---

### TD-005 — `components/components.py` Has 4 Dead Stub Functions

```python
def inject_keyboard_shortcuts():  # never called
    pass

def inject_voice_input_js():      # never called
    pass

def inject_code_block_enhancer(): # never called
    pass
```

These are documented as "backward compatibility" stubs but add dead code confusion.

---

### TD-006 — `TOOL_COMPARISON_PROMPT` Is Defined But Never Used

**File:** `config/prompts.py` — lines 45–55

`TOOL_COMPARISON_PROMPT` exists in `prompts.py` but is never imported or called anywhere in the codebase. This suggests a comparison feature was planned but not implemented.

---

### TD-007 — No `__init__.py` Files in `components/`, `config/`, `src/`, `utils/`

None of the module directories have `__init__.py` files. While Python 3 supports implicit namespace packages, the absence makes the package structure less explicit and can cause issues with certain tools and test runners.

---

### TD-008 — `chat.py` Has 565 Lines — Needs Decomposition

`components/chat.py` at 565 lines handles: routing decisions, streaming, state management, DB persistence, file indexing, edit mode, regeneration, and message rendering. This is too many responsibilities for one file.

---

### TD-009 — `storage.py` Uses `datetime.utcnow()` (Deprecated in Python 3.12)

`datetime.utcnow()` is deprecated as of Python 3.12. The recommended replacement is `datetime.now(timezone.utc)`.

---

### TD-010 — Docker Image Has No Volume for Persistence

**File:** `Dockerfile`

The SQLite database (`chats/chat_history.db`) and FAISS index (`vector_store/`) are inside the container filesystem. When the container restarts, all chat history and the FAISS index are lost. There is no `VOLUME` directive in the Dockerfile.

---

### TD-011 — `scripts/test_pipeline.py` Calls Real Gemini API

**File:** `scripts/test_pipeline.py`

This script makes live API calls to Gemini without mocking. It is not suitable for use in CI (and indeed is not run in CI) but is documented as an optional test. It could be accidentally run and consume API quota.

---

### TD-012 — No `conftest.py` for pytest

There is no `conftest.py` in the `tests/` directory. Shared fixtures (like `temp_path`-based ChatStore instances) are duplicated across test files.

---

## 7. Recommended Improvements

### R-001 — Fix BUG-001 (Broken Import) ← Prerequisite for file uploads
Fix `load_embedding_model` → `get_embeddings` in `file_handler.py`.

### R-002 — Fix BUG-002 (Duplicate Column) ← UI correctness  
Change second `act_cols[3]` to `act_cols[4]` for the Share button.

### R-003 — Fix SEC-001 (XSS in Clipboard JS) ← Security  
Replace manual string escaping with `json.dumps()` for JS context.

### R-004 — Fix BUG-004 / SEC-002 (Path Traversal + No File Size Limit)
Add `Path(uploaded_file.name).name` sanitization and a 50 MB size cap.

### R-005 — Eliminate Double Retrieval (BUG-007)
Pass retrieved results from routing decision into `execute_rag_pipeline()` to avoid duplicate FAISS search.

### R-006 — Refactor `confidence_desc` Storage (BUG-010)
Add a `source_type` column to the `messages` table, store source there, and remove the `UPDATE` hack after `add_message`.

### R-007 — Migrate to `datetime.now(timezone.utc)` (TD-009)
Replace all `datetime.utcnow()` calls for Python 3.12+ compliance.

### R-008 — Add Docker Volumes for Persistence (TD-010)
Add `VOLUME ["/app/chats", "/app/vector_store"]` to Dockerfile and document `docker run -v` flags.

### R-009 — Pin Dependencies (TD-001)
Run `pip freeze` and generate a `requirements-lock.txt` with pinned versions.

### R-010 — Remove Dead Code
- Delete `src/llm.py` (dead) or document it as an alternative path.
- Remove `langchain-google-genai` from requirements if `llm.py` is removed.
- Remove stub functions from `components/components.py`.
- Remove `TOOL_COMPARISON_PROMPT` or implement the comparison feature.

### R-011 — Add `conftest.py` with Shared Fixtures
Create `tests/conftest.py` with a reusable `temp_chat_store` fixture.

### R-012 — Decompose `chat.py`
Split into: `chat_input.py`, `chat_message_renderer.py`, `chat_routing.py`.

### R-013 — Add `__init__.py` to All Package Directories

### R-014 — Implement File Cleanup for Uploads
Add a cleanup routine to remove files from `UPLOADS_DIR` after session ends or on restart.

### R-015 — Add Integration Tests for RAG Pipeline
Add tests with mocked FAISS DB to test the routing decision logic in `chat.py`.

### R-016 — Improve CI Pipeline
Add: linting (ruff/flake8), type checking (mypy), dependency vulnerability scan (pip-audit), and test coverage reporting.

### R-017 — Add `docs/` Folder
Create architecture diagrams, API documentation, and contribution guidelines.

---

## 8. Priority Matrix

| ID | Issue | Priority | Effort | Impact |
|---|---|---|---|---|
| BUG-001 | Broken import `load_embedding_model` | 🔴 Critical | XS (1 line) | File uploads broken |
| SEC-001 | XSS via JS string injection | 🔴 Critical | S (1 file) | Security vulnerability |
| BUG-004 / SEC-002 | Path traversal + no size limit | 🔴 Critical | S (5 lines) | File system attack |
| BUG-002 | Duplicate `act_cols[3]` column | 🔴 High | XS (1 line) | UI Share button broken |
| BUG-007 | Double FAISS retrieval | 🟠 High | M (refactor) | 2× latency for KB queries |
| BUG-010 | Wasted + potentially missing DB write | 🟠 High | M (refactor) | Analytics inaccurate |
| BUG-003 / TD-003 | Dead `src/llm.py` module | 🟠 High | XS (delete) | Confusion + dead dep |
| BUG-006 | Calling private `_connect()` from chat.py | 🟡 Medium | S | Encapsulation break |
| BUG-005 | UTC timezone naive/aware mismatch | 🟡 Medium | S | Python 3.12 breakage risk |
| BUG-008 | Eager `ChatMemory()` in defaults dict | 🟡 Medium | XS | Minor perf, anti-pattern |
| BUG-009 | Shared mutable FAISS in multi-user | 🟡 Medium | M | Privacy in production |
| SEC-004 | Pickle deserialization risk | 🟡 Medium | — | Document risk |
| TD-001 | Unpinned dependencies | 🟡 Medium | S | Build reproducibility |
| TD-010 | No Docker volumes | 🟡 Medium | XS | Data loss on restart |
| TD-009 | `datetime.utcnow()` deprecated | 🟡 Medium | S | Python 3.12+ warnings |
| TD-002 | Global singleton embeddings | 🟡 Medium | S | Test isolation |
| BUG-012 | No UI for similarity threshold | 🟢 Low | S | UX limitation |
| BUG-011 | README documents wrong file names | 🟢 Low | S | Documentation |
| TD-004 | Side-effects at import time | 🟢 Low | M | Test setup |
| TD-008 | `chat.py` too large (565 lines) | 🟢 Low | L | Maintainability |

---

## 9. Dependency Analysis

```
streamlit>=1.30.0           ✅ Required — UI framework
langchain>=0.1.0            ✅ Required — FAISS integration, text splitting, doc loading
langchain-google-genai>=0.0.6  ⚠️ DEAD — only used by src/llm.py which is never called
langchain-community>=0.0.10 ✅ Required — FAISS, PyPDFLoader
langchain-huggingface>=1.0.0 ✅ Required — HuggingFaceEmbeddings
faiss-cpu>=1.7.4            ✅ Required — vector index
sentence-transformers>=3.0.0 ✅ Required — all-MiniLM-L6-v2
pypdf>=3.17.0               ✅ Required — PDF loading via PyPDFLoader
python-dotenv>=1.0.0        ✅ Required — .env loading
google-genai>=1.0.0         ✅ Required — Gemini streaming API
tiktoken>=0.5.1             ⚠️ UNUSED — not imported anywhere in the codebase
numpy>=1.24.0               ✅ Required — NumpyEncoder in storage.py
pandas>=2.0.0               ✅ Required — analytics data processing
reportlab>=4.0.0            ⚠️ POSSIBLY UNUSED — not imported in core code (may be in scripts)
python-docx>=1.1.0          ✅ Required — DOCX loading
python-pptx>=0.6.21         ✅ Required — PPTX loading
plotly>=5.18.0              ✅ Required — analytics charts
pytest>=7.4.0               ✅ Required — test framework
```

**Unused/questionable dependencies:** `langchain-google-genai`, `tiktoken`, `reportlab`

---

## 10. CI/CD Analysis

**File:** `.github/workflows/ci.yml`

| Check | Status | Notes |
|---|---|---|
| Python syntax validation | ✅ Present | `python -m compileall` |
| Test execution | ✅ Present | `pytest tests/ -v` |
| Multi-version matrix | ✅ Present | 3.11 + 3.12 |
| Dependency caching | ✅ Present | `cache: "pip"` |
| Linting (ruff/flake8) | ❌ Missing | No style enforcement |
| Type checking (mypy) | ❌ Missing | No static type validation |
| Security scan (pip-audit) | ❌ Missing | No vulnerability scan |
| Coverage reporting | ❌ Missing | No `--cov` flags |
| Docker build test | ❌ Missing | Image never tested in CI |
| Integration tests | ❌ Missing | Only unit tests exist |
| Artifact caching | ❌ Missing | FAISS index rebuilt each CI run |

**Critical CI gap:** The CI runs `pytest tests/` but `test_rag_pipeline.py` imports `from rag import _get_client, execute_rag_pipeline` — if `google-genai` is not installed in the CI environment (or the import fails for any reason), the CI step will fail. Currently the `requirements.txt` install step includes it, so this passes.

**BUG-001 would cause CI to pass** because `index_uploaded_file` is not tested — the test suite has no test for `file_handler.py`. The broken import only manifests at runtime when a user uploads a file.

---

## 11. Test Coverage Analysis

| Test File | Module Tested | Coverage Level |
|---|---|---|
| `test_chat_manager.py` | `chat_manager.py` | ✅ Good (add, clear, format, limit) |
| `test_storage.py` | `storage.py` | ✅ Good (session lifecycle, messages, search) |
| `test_retriever.py` | `src/retriever.py` | ✅ Good (empty, with docs, avg confidence) |
| `test_text_splitter.py` | `src/text_splitter.py` | ✅ Good (small, large, empty) |
| `test_rag_pipeline.py` | `rag.py` | ⚠️ Minimal (missing key, mock stream only) |
| **Not tested** | `src/file_handler.py` | ❌ 0% — BUG-001 lives here undetected |
| **Not tested** | `src/document_loader.py` | ❌ 0% |
| **Not tested** | `src/embeddings.py` | ❌ 0% |
| **Not tested** | `vectorstore.py` | ❌ 0% |
| **Not tested** | `utils/helpers.py` | ❌ 0% |
| **Not tested** | `components/` (all 9 files) | ❌ 0% |
| **Not tested** | `config/settings.py` | ❌ 0% |
| **Not tested** | `config/prompts.py` | ❌ 0% |

**Overall estimated coverage: ~15–20%**

Key missing test scenarios:
- `parse_related_questions()` with malformed `<related>` blocks
- `calculate_confidence_score()` with edge values (0.0, 1.0, 0.44, 0.65, 0.85)
- `index_uploaded_file()` — currently broken (BUG-001) and untested
- `get_or_build_vector_store()` with existing / missing index
- `format_chat_export_markdown()` and `format_chat_export_json()`
- Routing logic in `_handle_user_query()` (KB vs Web vs LLM decision)

---

## Summary

> **The existing RAGBOT project has a solid architectural foundation** — the RAG pipeline design, SQLite persistence layer, multi-session management, and streaming UI are all well-structured. The core RAG flow works correctly for the happy path.
>
> **The most urgent issue is BUG-001**: file uploads are silently broken due to a one-line function name mismatch. This is the single highest-priority fix before any new feature work.
>
> **SEC-001 (XSS)** must be addressed before any public deployment.
>
> **BUG-002 (Share button column)** and **BUG-004 (path traversal)** are quick fixes with significant correctness and security impact.
>
> The project is **ready for Phase 2 (bug fixes and hardening)** after the Phase 1 audit is reviewed and approved.
