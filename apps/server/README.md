# DAW Server

FastAPI server for the Deterministic Agentic Workbench.

## Overview

This package provides the server infrastructure for DAW, extracted from `daw-agents` for better separation of concerns.

## Package Structure

```
apps/server/
├── src/daw_server/
│   ├── __init__.py       # Package entry point
│   ├── main.py           # FastAPI application
│   ├── api/              # API routes and WebSocket endpoints
│   │   ├── __init__.py
│   │   ├── routes.py     # REST API routes
│   │   ├── schemas.py    # Pydantic models for API
│   │   └── websocket.py  # WebSocket streaming infrastructure
│   ├── auth/             # Clerk authentication
│   │   ├── __init__.py
│   │   ├── clerk.py      # JWT verification
│   │   ├── dependencies.py # FastAPI dependencies
│   │   ├── exceptions.py # Auth-specific exceptions
│   │   └── middleware.py # Auth middleware
│   └── workers/          # Celery background tasks
│       ├── __init__.py
│       ├── celery_app.py # Celery configuration
│       └── tasks.py      # Task definitions
└── tests/                # Test suite
```

## Installation

```bash
cd apps/server
poetry install
```

## Running the Server

```bash
# Development
uvicorn daw_server.main:app --reload --port 8000

# Production
uvicorn daw_server.main:app --host 0.0.0.0 --port 8000
```

## Dependencies

- `daw-agents`: Core agent library (local path dependency)
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `celery`: Background task processing
- `redis`: Message broker and result backend
