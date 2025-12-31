"""Pytest configuration and fixtures for DAW Server tests."""

import os

# Set TESTING environment variable before importing app modules
# This disables rate limiting during tests
os.environ["TESTING"] = "true"

# Do NOT set DEV_BYPASS_AUTH here - tests should test real auth behavior
# Tests that need auth bypass should mock it explicitly

import pytest
from fastapi.testclient import TestClient

from daw_server.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)
