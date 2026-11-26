"""
main.py — FastAPI Application Entrypoint.

Provides the versioned REST API for RAGBOT:
  - Versioned routes under /api/v1 (health, auth, chat, documents, sessions, diagnostics)
  - CORS middleware (restricted to configured origins only)
  - Security response headers (X-Content-Type-Options, X-Frame-Options, etc.)
  - Centralized exception handling — no stack traces exposed to clients
  - Swagger UI documentation at /docs and ReDoc at /redoc
"""
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.routes import auth, chat, diagnostics, documents, health, sessions
from config.settings import API_V1_PREFIX, CORS_ORIGINS
from src.logger import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security response headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response


class RequestBodyLimitMiddleware:
    """Bound incoming HTTP bodies even when Content-Length is absent."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = (25 if scope["path"].endswith("/documents/upload") else 2) * 1024 * 1024
        async def reject(code: int, detail: str):
            await JSONResponse(status_code=code, content={
                "success": False, "error": detail, "status_code": code,
            })(scope, receive, send)
        headers = dict(scope["headers"])
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                length = int(declared)
                if length < 0:
                    raise ValueError("negative length")
            except ValueError:
                await reject(400, "Invalid Content-Length.")
                return
            if length > limit:
                await reject(413, "Request payload exceeds allowed limit.")
                return
        total = 0
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > limit:
                await reject(413, "Request payload exceeds allowed limit.")
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Observability & Tracing Middleware (Phase 14):
    - Generates or propagates unique correlation ID (X-Request-ID).
    - Measures high-resolution request duration and attaches X-Process-Time header.
    - Emits structured operational log for every request with latency and client metadata.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", "")
        if not request_id or len(request_id) > 64 or not all(c.isascii() and (c.isalnum() or c in "-_") for c in request_id):
            request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

        # Log operational request metrics
        client_host = request.client.host if request.client else "unknown"
        logger.info(
            f"HTTP {request.method} {request.url.path} "
            f"status={response.status_code} latency={duration_ms:.2f}ms "
            f"request_id={request_id} client={client_host}"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for application startup and shutdown events."""
    logger.info("RAGBOT FastAPI Backend started successfully.")
    yield
    logger.info("RAGBOT FastAPI Backend shutting down.")


app = FastAPI(
    title="RAGBOT API",
    description="Enterprise Portfolio-Quality Retrieval-Augmented Generation Backend.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Security & Limit Middlewares ──────────────────────────────────────────────
app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(RequestObservabilityMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# ── CORS Middleware (restricted to configured origins) ────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)


# ── Centralized Exception Handlers ────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Centralized handler for all HTTPExceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
        },
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Centralized fallback handler for unexpected exceptions. Never exposes stack traces."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {type(exc).__name__}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "An unexpected server error occurred.",
            "status_code": 500,
        },
    )


# ── Route Registration ────────────────────────────────────────────────────────

app.include_router(health.router, prefix=API_V1_PREFIX)
app.include_router(auth.router, prefix=API_V1_PREFIX)
app.include_router(chat.router, prefix=API_V1_PREFIX)
app.include_router(documents.router, prefix=API_V1_PREFIX)
app.include_router(sessions.router, prefix=API_V1_PREFIX)
app.include_router(diagnostics.router, prefix=API_V1_PREFIX)


@app.get("/", tags=["Root"])
def root():
    """Root endpoint welcoming visitors and directing to Swagger docs."""
    return {
        "name": "RAGBOT API",
        "version": "2.0.0",
        "docs_url": "/docs",
        "health_url": f"{API_V1_PREFIX}/health",
        "status": "online",
    }
