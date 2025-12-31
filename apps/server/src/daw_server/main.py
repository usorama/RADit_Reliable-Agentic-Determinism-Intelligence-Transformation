"""DAW Server - Deterministic Agentic Workbench FastAPI Application."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from daw_server.api.routes import create_router, create_trace_websocket_router
from daw_server.api.websocket import create_websocket_router
from daw_server.auth.clerk import ClerkConfig

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    """Health check endpoint."""
    return {"status": "healthy", "service": "daw-server"}
