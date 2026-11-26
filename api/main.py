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


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces maximum request body sizes to prevent denial of service:
    - 25 MB for document upload routes
    - 2 MB for standard JSON payload endpoints
    """
    MAX_UPLOAD_BYTES = 25 * 1024 * 1024   # 25 MB
    MAX_DEFAULT_BYTES = 2 * 1024 * 1024   # 2 MB

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                limit = self.MAX_UPLOAD_BYTES if request.url.path.endswith("/documents/upload") else self.MAX_DEFAULT_BYTES
                if length > limit:
                    return JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "success": False,
                            "error": f"Request payload exceeds allowed limit of {limit // (1024 * 1024)}MB.",
                            "status_code": 413,
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)


class RequestObservabilityMiddleware:
    """
    Pure ASGI Observability Middleware (Phase 14):
    Zero deadlock risk with StreamingResponse or Server-Sent Events.
    Attaches X-Request-ID and X-Process-Time headers to every HTTP response.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = None
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                request_id = value.decode("utf-8", errors="ignore")
                break
        if not request_id:
            request_id = str(uuid.uuid4())

        start_time = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                headers.append((b"x-request-id", request_id.encode("utf-8")))
                headers.append((b"x-process-time", f"{duration_ms:.2f}ms".encode("utf-8")))
                message["headers"] = headers
                logger.info(
                    f"HTTP {scope.get('method')} {scope.get('path')} "
                    f"status={message.get('status')} latency={duration_ms:.2f}ms "
                    f"request_id={request_id}"
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)


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
app.add_middleware(RequestObservabilityMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestBodyLimitMiddleware)

# ── CORS Middleware (restricted to configured origins) ────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
