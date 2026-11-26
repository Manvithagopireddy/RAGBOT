"""
main.py — FastAPI Application Entrypoint.

Provides the versioned REST API for RAGBOT:
  - Versioned routes under /api/v1 (health, auth, chat, documents, sessions, diagnostics)
  - CORS middleware (restricted to configured origins only)
  - Security response headers (X-Content-Type-Options, X-Frame-Options, etc.)
  - Centralized exception handling — no stack traces exposed to clients
  - Swagger UI documentation at /docs and ReDoc at /redoc
"""
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

# ── Security Headers ──────────────────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── CORS Middleware (restricted to configured origins) ────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
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
