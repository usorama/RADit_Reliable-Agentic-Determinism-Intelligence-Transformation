"""Pytest configuration for integration tests.

This module provides fixtures for integration tests that require real
external services such as E2B sandbox and Neo4j VPS.

Fixtures:
- e2b_api_key: Loads E2B API key from .creds/e2b_api_key.txt or E2B_API_KEY env
- e2b_sandbox: Creates a real E2B sandbox with automatic cleanup
- neo4j_config: Neo4j VPS configuration
- neo4j_connector: Real Neo4j connector to Hostinger VPS
- cleanup_test_nodes: Track and cleanup test nodes after each test
- cleanup_test_label: Unique test label with automatic cleanup
- experience_logger_real: Real ExperienceLogger with VPS connection
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from daw_agents.evolution.experience_logger import ExperienceLogger
    from daw_agents.memory.neo4j import Neo4jConfig, Neo4jConnector
    from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig


logger = logging.getLogger(__name__)

# Get project root (4 levels up from this file: tests/integration/conftest.py)
# Project structure: RADit.../packages/daw-agents/tests/integration/conftest.py
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent

# Path to credentials files
E2B_API_KEY_FILE = PROJECT_ROOT / ".creds" / "e2b_api_key.txt"
NEO4J_VPS_CREDS_FILE = PROJECT_ROOT / ".creds" / "neo4j_vps.txt"

# Neo4j VPS connection defaults
VPS_URI = "bolt://72.60.204.156:7687"
VPS_USER = "neo4j"
VPS_PASSWORD = "daw_graph_2024"


def _parse_credentials_file(file_path: Path) -> str | None:
    """Parse a credentials file, ignoring comments and blank lines.

    Lines starting with # are treated as comments.
    Returns the first non-empty, non-comment line.

    Args:
        file_path: Path to the credentials file.

    Returns:
        The credential value or None if not found.
    """
    if not file_path.exists():
        return None

    try:
        content = file_path.read_text()
        for line in content.splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                return line
        return None
    except OSError:
        return None


def _load_e2b_api_key() -> str | None:
    """Load E2B API key from file or environment variable.

    Priority:
    1. E2B_API_KEY environment variable
    2. .creds/e2b_api_key.txt file (parses to ignore comments)

    Returns:
        API key string if found, None otherwise.
    """
    # Check environment variable first
    api_key = os.environ.get("E2B_API_KEY")
    if api_key:
        return api_key.strip()

    # Fall back to credentials file (parse to ignore comments)
    return _parse_credentials_file(E2B_API_KEY_FILE)


@pytest.fixture(scope="module")
def e2b_api_key() -> str:
    """Fixture that provides the E2B API key.

    Skips the test if no API key is available.

    Returns:
        E2B API key string.

    Raises:
        pytest.skip: If no API key is available.
    """
    api_key = _load_e2b_api_key()
    if not api_key:
        pytest.skip(
            "E2B API key not available. "
            f"Set E2B_API_KEY env var or create {E2B_API_KEY_FILE}"
        )
    return api_key


@pytest_asyncio.fixture
async def e2b_sandbox(e2b_api_key: str) -> AsyncIterator[E2BSandbox]:
    """Fixture that creates and manages a real E2B sandbox.

    Creates a sandbox at the start of the test and ensures cleanup
    even if the test fails.

    Args:
        e2b_api_key: E2B API key from the e2b_api_key fixture.

    Yields:
        A started E2BSandbox instance.
    """
    from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

    config = SandboxConfig(
        api_key=e2b_api_key,
        timeout=120,  # 2 minutes for integration tests
        template="base",
    )
    sandbox = E2BSandbox(config=config)

    try:
        await sandbox.start()
        yield sandbox
    finally:
        # Ensure cleanup even if test fails
        try:
            await sandbox.stop()
        except Exception:
            # Log but don't fail test on cleanup errors
            pass


@pytest.fixture
def e2b_config(e2b_api_key: str) -> SandboxConfig:
    """Fixture that provides a SandboxConfig without starting a sandbox.

    Useful for tests that need to test sandbox creation/destruction.

    Args:
        e2b_api_key: E2B API key from the e2b_api_key fixture.

    Returns:
        SandboxConfig instance.
    """
    from daw_agents.sandbox.e2b import SandboxConfig

    return SandboxConfig(
        api_key=e2b_api_key,
        timeout=120,
        template="base",
    )


# =============================================================================
# Neo4j VPS Integration Fixtures
# =============================================================================


def _load_neo4j_credentials() -> tuple[str, str, str]:
    """Load Neo4j VPS credentials from file or environment variables.

    Priority:
    1. Environment variables (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    2. .creds/neo4j_vps.txt file
    3. Default values

    Returns:
        Tuple of (uri, user, password).
    """
    uri = VPS_URI
    user = VPS_USER
    password = VPS_PASSWORD

    # Try to load from credentials file
    if NEO4J_VPS_CREDS_FILE.exists():
        try:
            content = NEO4J_VPS_CREDS_FILE.read_text()
            for line in content.strip().split("\n"):
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if line.startswith("NEO4J_URI="):
                    uri = line.split("=", 1)[1]
                elif line.startswith("NEO4J_USER="):
                    user = line.split("=", 1)[1]
                elif line.startswith("NEO4J_PASSWORD="):
                    password = line.split("=", 1)[1]
        except OSError as e:
            logger.warning("Failed to read Neo4j credentials file: %s", e)

    # Environment variables take precedence
    uri = os.environ.get("NEO4J_URI", uri)
    user = os.environ.get("NEO4J_USER", user)
    password = os.environ.get("NEO4J_PASSWORD", password)

    return uri, user, password


def _check_neo4j_connectivity() -> bool:
    """Synchronously check if Neo4j VPS is reachable.

    Uses a synchronous driver for the initial connectivity check
    to avoid async complications during pytest collection.

    Returns:
        True if VPS is reachable, False otherwise.
    """
    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.warning("neo4j package not installed")
        return False

    uri, user, password = _load_neo4j_credentials()

    try:
        # Use synchronous driver with short timeout
        driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=5.0,  # 5 second timeout
        )
        # Try to establish connection
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception as e:
        logger.warning("Neo4j VPS not reachable: %s", e)
        return False


# Determine if VPS is reachable at module load time
# This allows pytest.mark.skipif to work correctly
_VPS_REACHABLE: bool | None = None


def is_vps_reachable() -> bool:
    """Check if the Neo4j VPS is reachable (cached result).

    This function caches its result to avoid repeated connection
    attempts during test collection.
    """
    global _VPS_REACHABLE
    if _VPS_REACHABLE is None:
        _VPS_REACHABLE = _check_neo4j_connectivity()
    return _VPS_REACHABLE


# Skip marker for integration tests requiring Neo4j VPS
skip_if_vps_unreachable = pytest.mark.skipif(
    not is_vps_reachable(),
    reason="Neo4j VPS (72.60.204.156:7687) is not reachable",
)


@pytest.fixture(scope="session")
def neo4j_config() -> Neo4jConfig:
    """Create Neo4j config for VPS connection.

    Returns:
        Neo4jConfig configured for the Hostinger VPS.
    """
    from daw_agents.memory.neo4j import Neo4jConfig

    uri, user, password = _load_neo4j_credentials()
    return Neo4jConfig(
        uri=uri,
        user=user,
        password=password,
        database="neo4j",
        max_connection_pool_size=10,
    )


@pytest_asyncio.fixture
async def neo4j_connector(
    neo4j_config: Neo4jConfig,
) -> AsyncGenerator[Neo4jConnector, None]:
    """Create a real Neo4j connector to the VPS.

    This fixture resets the singleton before and after each test
    to ensure clean state.

    Yields:
        Neo4jConnector instance connected to the VPS.
    """
    from daw_agents.memory.neo4j import Neo4jConnector

    # Reset singleton before test
    Neo4jConnector._instance = None
    Neo4jConnector._driver = None
    Neo4jConnector._config = None

    connector = None
    try:
        connector = Neo4jConnector.get_instance(neo4j_config)
        yield connector
    finally:
        # Cleanup: close connection and reset singleton
        if connector is not None:
            try:
                await connector.close()
            except Exception:
                pass
        Neo4jConnector._instance = None
        Neo4jConnector._driver = None
        Neo4jConnector._config = None


@pytest.fixture
def test_run_id() -> str:
    """Generate a unique ID for this test run.

    Used to create unique node labels/properties that can be
    reliably cleaned up after each test.

    Returns:
        Short UUID string (8 characters).
    """
    return str(uuid.uuid4())[:8]


@pytest_asyncio.fixture
async def cleanup_test_nodes(
    neo4j_connector: Neo4jConnector,
) -> AsyncGenerator[list[str], None]:
    """Track and cleanup test nodes after each test.

    This fixture provides a list that tests can append node IDs to.
    After the test completes, all tracked nodes are deleted.

    Usage:
        async def test_something(cleanup_test_nodes, neo4j_connector):
            node_id = await neo4j_connector.create_node(...)
            cleanup_test_nodes.append(node_id)
            # Node will be deleted after test

    Yields:
        List to append node IDs for cleanup.
    """
    node_ids: list[str] = []
    yield node_ids

    # Cleanup: delete all tracked nodes
    if node_ids:
        for node_id in node_ids:
            try:
                # Delete node and all its relationships
                await neo4j_connector.query(
                    """
                    MATCH (n) WHERE elementId(n) = $id
                    DETACH DELETE n
                    """,
                    {"id": node_id},
                )
            except Exception as e:
                logger.warning("Failed to cleanup node %s: %s", node_id, e)


@pytest_asyncio.fixture
async def cleanup_test_label(
    neo4j_connector: Neo4jConnector,
    test_run_id: str,
) -> AsyncGenerator[str, None]:
    """Provide a unique test label and cleanup all nodes with that label.

    This is an alternative cleanup strategy that uses unique labels
    instead of tracking individual node IDs.

    Usage:
        async def test_something(cleanup_test_label, neo4j_connector):
            label = cleanup_test_label  # e.g., "TestNode_abc123"
            await neo4j_connector.create_node([label], {"name": "test"})
            # All nodes with this label will be deleted after test

    Yields:
        Unique label string for this test run.
    """
    label = f"TestNode_{test_run_id}"
    yield label

    # Cleanup: delete all nodes with this label
    try:
        await neo4j_connector.query(
            f"MATCH (n:{label}) DETACH DELETE n",
            {},
        )
    except Exception as e:
        logger.warning("Failed to cleanup test label %s: %s", label, e)


@pytest_asyncio.fixture
async def experience_logger_real(
    neo4j_connector: Neo4jConnector,
) -> AsyncGenerator[ExperienceLogger, None]:
    """Create a real ExperienceLogger with VPS connection.

    Yields:
        ExperienceLogger instance using real Neo4j connector.
    """
    from daw_agents.evolution.experience_logger import ExperienceLogger

    logger_instance = ExperienceLogger(neo4j_connector=neo4j_connector)
    yield logger_instance
    # No cleanup needed - cleanup_test_nodes or cleanup_test_label handles it
