# syntax=docker/dockerfile:1
# ── STAGE 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install --upgrade pip && \
    python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip 'setuptools>=84.1.0' && \
    /opt/venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    /opt/venv/bin/pip install -r requirements.txt && \
    /opt/venv/bin/python -c 'import torch; assert torch.version.cuda is None'

# ── STAGE 2: Production Runner ────────────────────────────────────────────────
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install runtime curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Security: Create non-root system user and group
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Create persistent storage directories with proper ownership
RUN mkdir -p chats uploads vector_store knowledge_base evals/results && \
    chown -R appuser:appgroup /app

# Copy application source code
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

# Expose ports: 8000 (FastAPI REST API), 8501 (Streamlit UI)
EXPOSE 8000 8501

# Healthcheck targeting FastAPI health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail http://localhost:8000/api/v1/health || exit 1

# Default execution: FastAPI Production Server
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
