"""DAW Server - FastAPI server for Deterministic Agentic Workbench.

This package provides the server infrastructure including:
- FastAPI application with CORS middleware
- Clerk authentication (auth/)
- API routes and WebSocket endpoints (api/)
- Celery background workers (workers/)
"""

from daw_server.main import app

__all__ = [
    "app",
]
