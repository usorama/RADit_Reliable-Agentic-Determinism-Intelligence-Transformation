# DAW Server - FastAPI Backend
# Multi-stage build for production deployment

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=2.0.1
RUN pip install poetry==$POETRY_VERSION
RUN poetry config virtualenvs.create false

# Copy dependency files first for caching
COPY packages/daw-agents/pyproject.toml packages/daw-agents/poetry.lock* /app/packages/daw-agents/
COPY apps/server/pyproject.toml apps/server/poetry.lock* /app/apps/server/

# Copy source code (needed for local dependency resolution)
COPY packages/daw-agents/ /app/packages/daw-agents/
COPY apps/server/ /app/apps/server/

# Install dependencies
WORKDIR /app/apps/server
RUN poetry install --no-interaction --no-ansi --only main

# Stage 2: Runtime
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app/packages/daw-agents/src /app/packages/daw-agents/src
COPY --from=builder /app/apps/server/src /app/apps/server/src

# Set Python path
ENV PYTHONPATH="/app/packages/daw-agents/src:/app/apps/server/src:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Run the server
CMD ["uvicorn", "daw_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
