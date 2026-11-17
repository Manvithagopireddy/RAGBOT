# 🏗️ RAGBOT System Architecture & Engineering Design

This document details the architectural design, component interactions, retrieval strategies, data models, and security boundaries of **RAGBOT** — a production-grade, enterprise Retrieval-Augmented Generation (RAG) platform.

---

## 1. High-Level System Architecture

RAGBOT is structured as a decoupled, multi-tier system supporting dual presentation layers (a modern React 18 SPA and a Streamlit interactive dashboard), a high-performance FastAPI asynchronous backend, and a hybrid retrieval engine backed by FAISS, BM25, and local HuggingFace Cross-Encoders.

```mermaid
flowchart TD
    subgraph Clients["Presentation Layer"]
        ReactClient["React 18 + Vite SPA\n(TypeScript, Tailwind CSS, SSE)"]
        StreamlitClient["Streamlit UI\n(Components, Session State)"]
    end

    subgraph Gateway["API & Security Boundary (FastAPI)"]
        CORS["CORS Middleware"]
        RateLimiter["Sliding-Window Rate Limiter\n(Client IP based)"]
        AuthMiddleware["JWT Authentication\n& Document Ownership"]
        Routers["REST & SSE Routers\n(/chat, /documents, /sessions, /diagnostics)"]
    end

    subgraph ServiceLayer["Core Domain Services"]
        RAGService["RAG Service\n(Query Rewriter, Context Manager)"]
        IngestionService["Ingestion Service\n(MIME Validation, Token Chunker)"]
        RetrievalService["Retrieval Service\n(Hybrid Search Orchestrator)"]
    end

    subgraph Engine["Hybrid Retrieval & Reasoning Engine"]
        BM25Engine["BM25 Lexical Index\n(BM25Okapi, Rank-BM25)"]
        VectorEngine["Dense Vector Index\n(FAISS IndexFlatL2, all-MiniLM-L6-v2)"]
        RRF["Reciprocal Rank Fusion (RRF)\nk = 60 Score Aggregation"]
        CrossEncoder["Cross-Encoder Reranker\n(ms-marco-MiniLM-L-6-v2)"]
        GeminiLLM["Google Gemini 2.5 Flash\n(Strict Grounded Generation)"]
    end

    subgraph Storage["Persistence & Caching Layer"]
        SQLiteDB[("SQLite Database\nWAL Mode, FKs, Relational Indexes")]
        LocalStore[("Local Disk Artifacts\nuploads/, vector_store/")]
    end

    ReactClient -->|HTTP / SSE| CORS
    StreamlitClient -->|Direct Service Invocation| RAGService
    CORS --> RateLimiter
    RateLimiter --> AuthMiddleware
    AuthMiddleware --> Routers
    Routers --> RAGService
    Routers --> IngestionService
    Routers --> RetrievalService

    IngestionService --> LocalStore
    IngestionService --> BM25Engine
    IngestionService --> VectorEngine

    RAGService --> RetrievalService
    RetrievalService --> BM25Engine
    RetrievalService --> VectorEngine
    BM25Engine --> RRF
    VectorEngine --> RRF
    RRF --> CrossEncoder
    CrossEncoder --> RAGService
    RAGService --> GeminiLLM

    Routers --> SQLiteDB
    RAGService --> SQLiteDB
```

---

## 2. End-to-End Query & Retrieval Execution Flow

When a user submits a query, the system follows a multi-stage execution pipeline ensuring context-awareness, relevance optimization, and strict factual grounding with defense against prompt injection.

```mermaid
sequenceDiagram
    autonumber
    actor User as User (Client)
    participant API as FastAPI /api/v1/chat
    participant RAG as RAGService
    participant ContextMgr as ContextManager
    participant HybridRetriever as HybridRetriever
    participant Reranker as CrossEncoderReranker
    participant LLM as Gemini 2.5 Flash
    participant DB as SQLite Storage

    User->>API: POST /api/v1/chat/stream {message, session_id, top_k, use_reranker}
    API->>DB: Fetch Conversation History (last N turns)
    DB-->>API: History Messages
    API->>RAG: generate_stream(query, history, options)

    critical Query Optimization
        RAG->>LLM: Rewrite question given history into standalone query
        LLM-->>RAG: Optimized Standalone Query
    end

    critical Parallel Hybrid Retrieval
        RAG->>HybridRetriever: retrieve(query, top_k=8)
        par Lexical Search
            HybridRetriever->>HybridRetriever: BM25 Token Search
        and Dense Vector Search
            HybridRetriever->>HybridRetriever: HuggingFace Embed -> FAISS Search
        end
        HybridRetriever->>HybridRetriever: Apply Reciprocal Rank Fusion (RRF)
        HybridRetriever-->>RAG: Candidates [Document Chunks]
    end

    opt Re-ranking Enabled
        RAG->>Reranker: rerank(query, candidates, top_k=4)
        Reranker-->>RAG: High-Precision Ranked Chunks
    end

    critical Context Assembly & Guardrails
        RAG->>ContextMgr: build_guarded_context(chunks, token_budget)
        ContextMgr-->>RAG: Structured Context with Injection Defenses & Citations
    end

    RAG->>LLM: Stream grounded prompt with strict citations requirement
    loop SSE Stream
        LLM-->>RAG: Token Chunks
        RAG-->>API: SSE chunk event: data: {"type": "content", "delta": "..."}
        API-->>User: Browser EventStream Chunk
    end

    RAG->>DB: Persist User & Assistant Messages + Citations
    API-->>User: data: {"type": "done", "citations": [...], "confidence": 0.92}
```

---

## 3. Database Schema & Entity Relationships

The relational persistence tier is powered by SQLite with foreign key constraints enforced (`PRAGMA foreign_keys = ON;`) and WAL (Write-Ahead Logging) mode enabled for concurrent reads.

```mermaid
erDiagram
    USERS ||--o{ SESSIONS : "creates"
    USERS ||--o{ DOCUMENTS : "owns"
    SESSIONS ||--o{ MESSAGES : "contains"

    USERS {
        TEXT id PK "UUID4"
        TEXT username UK "Unique Handle"
        TEXT email UK "Unique Email Address"
        TEXT hashed_password "bcrypt salt + hash (12 rounds)"
        TEXT created_at "ISO-8601 UTC Timestamp"
    }

    SESSIONS {
        TEXT id PK "UUID4 / String ID"
        TEXT title "Session Title / Topic"
        TEXT created_at "ISO-8601 UTC Timestamp"
        TEXT updated_at "ISO-8601 UTC Timestamp"
        TEXT user_id FK "References USERS(id) ON DELETE SET NULL"
    }

    MESSAGES {
        INTEGER id PK "Auto-increment ID"
        TEXT session_id FK "References SESSIONS(id) ON DELETE CASCADE"
        TEXT role "user | assistant | system"
        TEXT content "Raw Markdown Text"
        TEXT citations "JSON Serialized Document Citations"
        REAL confidence "Float (0.0 to 1.0) Grounding Confidence"
        TEXT created_at "ISO-8601 UTC Timestamp"
    }

    DOCUMENTS {
        TEXT id PK "UUID4"
        TEXT user_id FK "References USERS(id) ON DELETE CASCADE"
        TEXT filename "Sanitized Filename"
        INTEGER file_size "Bytes"
        TEXT mime_type "application/pdf | text/plain | etc."
        TEXT sha256_hash "File Content Checksum"
        INTEGER chunk_count "Total Number of Extracted Chunks"
        TEXT status "indexed | processing | error"
        TEXT uploaded_at "ISO-8601 UTC Timestamp"
    }
```

### Relational Indexes
To optimize query performance, the following indexes are maintained:
- `idx_sessions_user_id` on `sessions(user_id)`
- `idx_sessions_updated_at` on `sessions(updated_at DESC)`
- `idx_messages_session_id` on `messages(session_id)`
- `idx_messages_created_at` on `messages(created_at ASC)`
- `idx_documents_user_id` on `documents(user_id)`
- `idx_users_username` on `users(username)`
- `idx_users_email` on `users(email)`

---

## 4. Ingestion & Document Processing Pipeline

The ingestion pipeline transforms raw uploaded files into searchable token chunks:

```mermaid
flowchart LR
    Upload["Uploaded Document\n(PDF, DOCX, TXT, MD)"] --> MagicCheck["MIME & Magic Byte\nValidation (src/security.py)"]
    MagicCheck --> PathCheck["Path Traversal & Filename\nSanitization (werkzeug)"]
    PathCheck --> Loader["Document Loader\n(Preserve 1-based page metadata)"]
    Loader --> TokenSplitter["Token-Aware Splitter\n(~250 tokens, 40-token overlap)"]
    TokenSplitter --> Clean["Sanitize Control Chars\n& Prompt Delimiters"]
    Clean --> ParallelIngest{"Parallel Indexing"}
    ParallelIngest --> Dense["Embeddings (all-MiniLM-L6-v2)\n-> FAISS VectorStore"]
    ParallelIngest --> Lexical["Tokenize (English Stopwords)\n-> BM25Retriever Index"]
```

1. **Validation & Security**: File magic bytes and extensions are verified (`.pdf`, `.docx`, `.txt`, `.md`). Maximum file size is strictly capped at 25MB.
2. **Normalized Metadata**: All document pages are normalized to 1-indexed page numbers. Source paths are recorded with unique document IDs and SHA256 checksums to detect duplicate uploads.
3. **Token-Aware Chunking**: Documents are split using recursive character boundaries respecting markdown headers, paragraphs, and word breaks, targeting ~250 tokens with a 40-token overlap to preserve contextual continuity.

---

## 5. Security & Isolation Architecture

RAGBOT enforces Defense-in-Depth across every tier:

- **Authentication & Sessions**: Passwords hashed using `bcrypt` (12 rounds). Authentication tokens are signed using JWT (HMAC-SHA256) with configurable TTL (default: 60 minutes).
- **Document Ownership & Isolation**: Multi-tenant isolation guarantees users can only retrieve and delete their own uploaded documents.
- **Sliding-Window Rate Limiting**: In-memory token-bucket limiter per client IP restricts excessive requests to prevent API abuse and DoS attacks (default: 60 requests/minute).
- **Prompt Injection Defense**: Context blocks wrap retrieved text in secure `<document_context>` delimiters with system instructions directing the LLM to treat document contents as unverified data rather than instructions.
- **No Secrets Exposure**: Secrets and keys are strictly loaded via environment variables; credentials are scrubbed from logs and exceptions.
