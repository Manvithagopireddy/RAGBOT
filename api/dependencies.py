"""
dependencies.py — FastAPI Dependency Injection.

Provides database store instances, service singletons,
JWT user authentication, and request rate-limiting dependencies.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import CHAT_DB_PATH
from services.ingestion_service import IngestionService, ingestion_service
from services.rag_service import RAGService, rag_service
from services.retrieval_service import RetrievalService, retrieval_service
from src.security import decode_access_token, rate_limiter
from storage import ChatStore

security_scheme = HTTPBearer(auto_error=False)


def get_chat_store() -> ChatStore:
    """Provides ChatStore database connection."""
    return ChatStore(CHAT_DB_PATH)


def get_rag_service() -> RAGService:
    """Provides singleton RAGService."""
    return rag_service


def get_ingestion_service() -> IngestionService:
    """Provides singleton IngestionService."""
    return ingestion_service


def get_retrieval_service() -> RetrievalService:
    """Provides singleton RetrievalService."""
    return retrieval_service


def check_rate_limit(request: Request) -> None:
    """
    Applies sliding-window rate limiting per client IP address.
    Raises HTTP 429 Too Many Requests if rate limit is exceeded.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    allowed, wait_seconds = rate_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please wait {wait_seconds} seconds before retrying.",
            headers={"Retry-After": str(wait_seconds)},
        )


def _resolve_user_from_token(
    auth: Optional[HTTPAuthorizationCredentials],
    store: ChatStore,
    require_auth: bool,
) -> Dict[str, Any]:
    """
    Core token resolution — shared by optional and required auth paths.
    Never falls back to a privileged default user.
    """
    if auth and auth.credentials:
        payload = decode_access_token(auth.credentials)
        if payload and payload.get("sub"):
            user = store.get_user_by_id(payload["sub"])
            if user:
                return user
        # Token was present but invalid/expired — always 401 (never silent fallback)
        if require_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # For optional auth — return None-equivalent guest with zero privileges
        return {"user_id": None, "username": "anonymous", "role": "guest"}

    if require_auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user_id": None, "username": "anonymous", "role": "guest"}


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    store: ChatStore = Depends(get_chat_store),
) -> Dict[str, Any]:
    """
    Enforces JWT authentication. Raises HTTP 401 Unauthorized if token is missing,
    invalid, expired, or forged. Never falls back to a default admin user.
    """
    return _resolve_user_from_token(auth, store, require_auth=True)


def get_current_user_optional(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    store: ChatStore = Depends(get_chat_store),
) -> Dict[str, Any]:
    """
    Returns the authenticated user dict if a valid JWT bearer token is present;
    returns an anonymous guest dict (user_id=None) otherwise.
    NEVER grants admin or default_user privileges to unauthenticated callers.
    """
    return _resolve_user_from_token(auth, store, require_auth=False)

