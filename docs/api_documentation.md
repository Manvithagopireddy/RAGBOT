# 📡 RAGBOT API Specification & Integration Guide

The RAGBOT API is built on **FastAPI** providing high-performance, asynchronous REST and Server-Sent Events (SSE) streaming endpoints.

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

Base URL: `http://localhost:8000/api/v1`

---

## 1. Authentication & Security

All private endpoints require a Bearer token in the `Authorization` header:

```http
Authorization: Bearer <jwt_token>
```

Tokens are obtained by logging in via `POST /api/v1/auth/login`.

---

## 2. Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/health` | Service health and component status | No |
| `POST` | `/api/v1/auth/register` | Register a new user account | No |
| `POST` | `/api/v1/auth/login` | Authenticate user and obtain JWT | No |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile | Yes |
| `POST` | `/api/v1/chat` | Send question and get complete response | Optional |
| `POST` | `/api/v1/chat/stream` | Send question and stream response via SSE | Optional |
| `POST` | `/api/v1/documents/upload` | Upload & index document (PDF, TXT, DOCX) | Yes |
| `GET` | `/api/v1/documents` | List uploaded documents for user | Yes |
| `DELETE` | `/api/v1/documents/{document_id}` | Delete document and remove from indexes | Yes |
| `POST` | `/api/v1/documents/{document_id}/reindex` | Re-index existing document | Yes |
| `GET` | `/api/v1/sessions` | List chat sessions for user | Yes |
| `GET` | `/api/v1/sessions/{session_id}` | Retrieve chat session with message history | Yes |
| `DELETE` | `/api/v1/sessions/{session_id}` | Delete chat session and associated messages | Yes |
| `POST` | `/api/v1/diagnostics/retrieve` | Inspect hybrid retrieval candidates & latency | Optional |

---

## 3. Detailed Endpoint Reference

### 3.1 Health Check
**`GET /api/v1/health`**

Returns the operational status of the API, vector store, and background services.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2026-11-17T22:00:00Z",
  "vector_store_loaded": true,
  "bm25_loaded": true,
  "total_documents": 14
}
```

---

### 3.2 Authentication

#### Register New User
**`POST /api/v1/auth/register`**

**Request Body**:
```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "StrongPassword123!"
}
```

**Response `201 Created`**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "johndoe",
  "email": "john@example.com",
  "created_at": "2026-11-17T22:01:00Z"
}
```

#### User Login
**`POST /api/v1/auth/login`**

**Request Body**:
```json
{
  "username": "johndoe",
  "password": "StrongPassword123!"
}
```

**Response `200 OK`**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### 3.3 Chat & Retrieval

#### Send Chat Message (Synchronous)
**`POST /api/v1/chat`**

**Request Body**:
```json
{
  "message": "What is the difference between supervised and reinforcement learning?",
  "session_id": "optional-session-uuid",
  "top_k": 4,
  "use_reranker": true,
  "hybrid_search": true,
  "temperature": 0.2
}
```

**Response `200 OK`**:
```json
{
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "answer": "Supervised learning trains models on labeled input-output pairs [Source: AI_Basics.pdf, p. 1], whereas reinforcement learning learns via reward signals from trial-and-error interactions [Source: AI_Basics.pdf, p. 3].",
  "citations": [
    {
      "source": "AI_Basics.pdf",
      "page": 1,
      "snippet": "In supervised learning, the algorithm is provided with labeled data...",
      "score": 0.892
    },
    {
      "source": "AI_Basics.pdf",
      "page": 3,
      "snippet": "Reinforcement learning agents take actions in an environment...",
      "score": 0.814
    }
  ],
  "confidence": 0.89,
  "latency_ms": 782.4
}
```

#### Stream Chat Message (Server-Sent Events)
**`POST /api/v1/chat/stream`**

Streams the answer tokens in real-time as they are synthesized by Gemini.

**Headers**:
- `Accept: text/event-stream`

**Event Stream Payloads**:
```http
data: {"type": "session", "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}

data: {"type": "content", "delta": "Supervised "}

data: {"type": "content", "delta": "learning trains on "}

data: {"type": "content", "delta": "labeled examples..."}

data: {"type": "citations", "citations": [{"source": "AI_Basics.pdf", "page": 1, "score": 0.892}]}

data: {"type": "done", "confidence": 0.89, "latency_ms": 782.4}
```

---

### 3.4 Documents Management

#### Upload & Ingest Document
**`POST /api/v1/documents/upload`**

Uploads and immediately chunks, embeds, and indexes a file.

**Content-Type**: `multipart/form-data`
- `file`: Binary file (PDF, TXT, DOCX, MD)

**Response `201 Created`**:
```json
{
  "document_id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
  "filename": "Transformers_Attention.pdf",
  "file_size": 2048576,
  "mime_type": "application/pdf",
  "chunk_count": 42,
  "status": "indexed",
  "uploaded_at": "2026-11-17T22:05:00Z"
}
```

#### List User Documents
**`GET /api/v1/documents`**

**Response `200 OK`**:
```json
{
  "total": 1,
  "documents": [
    {
      "id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
      "filename": "Transformers_Attention.pdf",
      "file_size": 2048576,
      "chunk_count": 42,
      "status": "indexed",
      "uploaded_at": "2026-11-17T22:05:00Z"
    }
  ]
}
```

#### Delete Document
**`DELETE /api/v1/documents/{document_id}`**

Deletes the document from SQLite and removes its chunks from the FAISS vector index and BM25 index.

**Response `200 OK`**:
```json
{
  "message": "Document successfully deleted",
  "document_id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a"
}
```

---

### 3.5 Retrieval Diagnostics

#### Inspect Retrieval Pipelines
**`POST /api/v1/diagnostics/retrieve`**

Allows developers to benchmark and inspect the raw output of BM25, FAISS, and Cross-Encoder reranking for any query without calling the LLM.

**Request Body**:
```json
{
  "query": "How does multi-head attention work?",
  "top_k": 4,
  "use_reranker": true
}
```

**Response `200 OK`**:
```json
{
  "query": "How does multi-head attention work?",
  "top_k": 4,
  "total_candidates": 8,
  "retrieval_latency_ms": 14.8,
  "rerank_latency_ms": 182.3,
  "results": [
    {
      "source": "Transformers_Attention.pdf",
      "page": 4,
      "bm25_score": 12.45,
      "vector_score": 0.812,
      "rrf_score": 0.032,
      "rerank_score": 0.941,
      "snippet": "Multi-head attention allows the model to jointly attend to information..."
    }
  ]
}
```

---

## 4. cURL Usage Examples

### 4.1 Authenticating and Storing Token
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Password123!"}' | jq -r .access_token)
```

### 4.2 Asking a Grounded Question with Citations
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the architecture of LangGraph?",
    "top_k": 4,
    "use_reranker": true
  }'
```

### 4.3 Streaming Answer over SSE
```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain reciprocal rank fusion.",
    "top_k": 4
  }'
```
