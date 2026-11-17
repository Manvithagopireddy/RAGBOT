"""
schemas.py — Pydantic Schemas for API Requests and Responses.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "2.0.0"
    database_connected: bool = True
    faiss_ready: bool = False
    bm25_ready: bool = False
    total_vectors: int = 0
    total_documents: int = 0
    default_model: str = "gemini-2.5-flash"


# ── Auth & Users ──────────────────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)


class UserLoginRequest(BaseModel):
    username_or_email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    created_at: str


# ── Chat & Citations ──────────────────────────────────────────────────────────

class CitationItem(BaseModel):
    id: int
    source: str
    page: Optional[int] = None
    snippet: str
    score: Optional[float] = None
    url: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = None
    model: Optional[str] = "gemini-2.5-flash"
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    retriever_k: Optional[int] = Field(default=4, ge=1, le=20)
    persona: Optional[str] = ""
    web_search: Optional[bool] = False
    hybrid: Optional[bool] = True
    rerank: Optional[bool] = True


class ChatResponse(BaseModel):
    session_id: str
    user_message_id: str
    assistant_message_id: str
    content: str
    citations: List[Dict[str, Any]] = []
    confidence_score: Optional[int] = None
    confidence_desc: Optional[str] = None
    model: str


# ── Documents ─────────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    document_id: str
    user_id: str
    filename: str
    file_path: str
    file_type: str
    file_size: int
    chunk_count: int
    checksum: Optional[str] = None
    status: str
    created_at: str
    updated_at: str


class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentResponse


# ── Sessions & Messages ───────────────────────────────────────────────────────

class MessageItem(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    citations: Optional[List[Dict[str, Any]]] = []
    confidence_score: Optional[int] = None
    confidence_desc: Optional[str] = None
    feedback: Optional[str] = None
    pinned: int = 0
    created_at: str


class SessionCreateRequest(BaseModel):
    title: Optional[str] = "New Chat"
    model: Optional[str] = "gemini-2.5-flash"
    temperature: Optional[float] = 0.7
    retriever_k: Optional[int] = 4
    persona: Optional[str] = ""
    web_search: Optional[bool] = False


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    temperature: Optional[float] = None
    retriever_k: Optional[int] = None
    rag_enabled: Optional[bool] = None
    model: Optional[str] = None
    persona: Optional[str] = None
    web_search: Optional[bool] = None


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    model: str
    temperature: float
    retriever_k: int
    rag_enabled: int
    persona: Optional[str] = ""
    web_search: int = 0
    is_pinned: int = 0
    is_favorited: int = 0
    is_archived: int = 0


class SessionDetailResponse(SessionResponse):
    messages: List[MessageItem] = []


# ── Diagnostics ───────────────────────────────────────────────────────────────

class DiagnosticsRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: Optional[int] = Field(default=4, ge=1, le=20)
    threshold: Optional[float] = Field(default=0.0, ge=0.0, le=1.0)
    hybrid: Optional[bool] = True
    rerank: Optional[bool] = True


class DiagnosticsResponse(BaseModel):
    query: str
    results_count: int
    latency_ms: float
    diagnostics: Dict[str, Any]
    results: List[Dict[str, Any]]
