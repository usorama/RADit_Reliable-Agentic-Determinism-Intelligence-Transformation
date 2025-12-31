"""DAW Server - Deterministic Agentic Workbench FastAPI Application."""

import logging
import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from daw_server.api.routes import create_router, create_trace_websocket_router
from daw_server.api.websocket import create_websocket_router
from daw_server.auth.clerk import ClerkConfig
from daw_server.logging_config import configure_logging
from daw_server.middleware import RequestIDMiddleware

# Configure logging before app creation
configure_logging()

logger = logging.getLogger(__name__)

# Load Clerk configuration from environment
clerk_config = ClerkConfig(
    secret_key=os.getenv("CLERK_SECRET_KEY", "sk_test_development"),
    publishable_key=os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "pk_test_development"),
    jwks_url=os.getenv(
        "CLERK_JWKS_URL",
        "https://clerk.development.local/.well-known/jwks.json",
    ),
    authorized_parties=os.getenv("CLERK_AUTHORIZED_PARTIES", "").split(",") or None,
)

app = FastAPI(
    title="DAW Server",
    description="Deterministic Agentic Workbench - AI Agent Orchestration Server",
    version="0.1.0",
)

# Rate limiter configuration
# Disable rate limiting in test mode to avoid test failures
TESTING = os.getenv("TESTING", "false").lower() == "true"
limiter = Limiter(
    key_func=get_remote_address,
    enabled=not TESTING,  # Disable rate limiting in test mode
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# CORS configuration from environment
# Default origins include local development and production domain
# Production: https://daw.ping-gadgets.com
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3001,http://localhost:3002,https://daw.ping-gadgets.com"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Add request ID middleware for log correlation
app.add_middleware(RequestIDMiddleware)

# Register API routes
api_router = create_router(clerk_config)
app.include_router(api_router, prefix="/api")

# Register WebSocket routes
ws_router = create_websocket_router()
app.include_router(ws_router, prefix="/ws")

# Register trace WebSocket routes
trace_router = create_trace_websocket_router(clerk_config)
app.include_router(trace_router, prefix="/ws")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint (legacy - use /health/live or /health/ready)."""
    return {"status": "healthy", "service": "daw-server"}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    """Liveness probe - is the server running?

    This endpoint returns immediately if the server process is alive.
    Used by Kubernetes liveness probes to determine if container needs restart.

    Returns:
        Simple status indicating server is alive
    """
    return {"status": "alive", "service": "daw-server"}


@app.get("/health/ready")
async def health_ready() -> dict[str, Any]:
    """Readiness probe - are all dependencies up and ready?

    This endpoint checks connectivity to all critical dependencies:
    - Neo4j (knowledge graph database)
    - Redis (optional - message broker and cache)

    Used by Kubernetes readiness probes to determine if pod should receive traffic.

    Returns:
        Status with individual dependency health checks
    """
    checks: dict[str, str] = {}
    all_healthy = True

    # Check Neo4j connectivity
    try:
        from daw_agents.memory.neo4j import Neo4jConfig, Neo4jConnector

        # Try to get existing instance or create new one with env config
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        if neo4j_password:
            config = Neo4jConfig(
                uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                user=os.getenv("NEO4J_USER", "neo4j"),
                password=neo4j_password,
                database=os.getenv("NEO4J_DATABASE", "neo4j"),
            )
            connector = Neo4jConnector.get_instance(config)
            is_connected = await connector.is_connected()
            if is_connected:
                checks["neo4j"] = "healthy"
            else:
                checks["neo4j"] = "unhealthy: connection failed"
                all_healthy = False
        else:
            checks["neo4j"] = "not_configured"
    except Exception as e:
        checks["neo4j"] = f"unhealthy: {str(e)}"
        all_healthy = False

    # Check Redis connectivity (optional)
    try:
        from daw_server.config.redis import RedisConfig

        redis_config = RedisConfig()
        # Basic configuration check - Redis is optional
        checks["redis"] = "configured" if redis_config.host else "not_configured"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
        # Redis is optional, don't mark as unhealthy

    status = "ready" if all_healthy else "degraded"

    return {
        "status": status,
        "service": "daw-server",
        "checks": checks,
    }
