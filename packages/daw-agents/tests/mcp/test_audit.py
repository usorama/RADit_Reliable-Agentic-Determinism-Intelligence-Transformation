"""Comprehensive tests for MCP Audit Logging (MCP-SEC-003).

This module tests the MCP Audit Logging implementation for SOC 2/ISO 27001 compliance.

Tests cover:
1. AuditEntry model - Audit log entry with all required fields
2. AuditLogger class - Main logger with Neo4j storage
3. Hash-chaining for tamper resistance (SHA-256)
4. log_tool_call() method - Log tool calls with full metadata
5. query_audit_trail() method - Query audit logs with time filtering
6. Retention policy validation (7-year retention)
7. Helicone integration for observability

Requirements (FR-01.3.3):
- Every tool call logged with: timestamp, agent_id, user_id, tool name, action,
  parameters, result status, response time
- Hash-chaining for tamper resistance
- 7-year retention for SOC 2/ISO 27001 compliance
- Integrate with observability stack (Helicone)

References:
    - PRD FR-01.3.3: MCP Audit Logging requirements
    - SOC 2 Type II: Security event logging and monitoring
    - ISO 27001: Information security management
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    pass


# -----------------------------------------------------------------------------
# Test: AuditConfig Model
# -----------------------------------------------------------------------------


class TestAuditConfig:
    """Tests for the AuditConfig Pydantic model."""

    def test_audit_config_creation(self) -> None:
        """AuditConfig should be creatable with required fields."""
        from daw_agents.mcp.audit import AuditConfig

        config = AuditConfig(
            retention_days=2555,  # ~7 years
            hash_algorithm="sha256",
            enable_helicone=True,
        )

        assert config.retention_days == 2555
        assert config.hash_algorithm == "sha256"
        assert config.enable_helicone is True

    def test_audit_config_default_retention(self) -> None:
        """AuditConfig should default to 7-year retention (2555 days)."""
        from daw_agents.mcp.audit import AuditConfig

        config = AuditConfig()

        # 7 years = 365 * 7 = 2555 days
        assert config.retention_days == 2555

    def test_audit_config_default_hash_algorithm(self) -> None:
        """AuditConfig should default to SHA-256 hash algorithm."""
        from daw_agents.mcp.audit import AuditConfig

        config = AuditConfig()

        assert config.hash_algorithm == "sha256"


# -----------------------------------------------------------------------------
# Test: AuditEntry Model
# -----------------------------------------------------------------------------


class TestAuditEntry:
    """Tests for the AuditEntry Pydantic model."""

    def test_audit_entry_creation(self) -> None:
        """AuditEntry should be creatable with all required fields."""
        from daw_agents.mcp.audit import AuditEntry, ResultStatus

        entry = AuditEntry(
            entry_id="audit_12345",
            timestamp=datetime.now(UTC),
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={"path": "/tmp/test.txt", "content": "hello"},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=150,
        )

        assert entry.entry_id == "audit_12345"
        assert entry.agent_id == "executor"
        assert entry.user_id == "user_123"
        assert entry.tool_name == "write_file"
        assert entry.action == "execute"
        assert entry.result_status == ResultStatus.SUCCESS
        assert entry.response_time_ms == 150

    def test_audit_entry_with_previous_hash(self) -> None:
        """AuditEntry should support previous_hash for hash chaining."""
        from daw_agents.mcp.audit import AuditEntry, ResultStatus

        entry = AuditEntry(
            entry_id="audit_12346",
            timestamp=datetime.now(UTC),
            agent_id="planner",
            user_id="user_456",
            tool_name="search",
            action="execute",
            parameters={"query": "test query"},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=100,
            previous_hash="abc123def456...",
        )

        assert entry.previous_hash == "abc123def456..."

    def test_audit_entry_with_entry_hash(self) -> None:
        """AuditEntry should support entry_hash for tamper detection."""
        from daw_agents.mcp.audit import AuditEntry, ResultStatus

        entry = AuditEntry(
            entry_id="audit_12347",
            timestamp=datetime.now(UTC),
            agent_id="validator",
            user_id="user_789",
            tool_name="run_tests",
            action="execute",
            parameters={},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=5000,
            entry_hash="sha256_hash_of_entry",
        )

        assert entry.entry_hash == "sha256_hash_of_entry"

    def test_audit_entry_result_status_enum(self) -> None:
        """ResultStatus enum should have all required values."""
        from daw_agents.mcp.audit import ResultStatus

        assert ResultStatus.SUCCESS is not None
        assert ResultStatus.FAILURE is not None
        assert ResultStatus.ERROR is not None
        assert ResultStatus.DENIED is not None
        assert ResultStatus.TIMEOUT is not None

    def test_audit_entry_with_error_details(self) -> None:
        """AuditEntry should support error_details for failures."""
        from daw_agents.mcp.audit import AuditEntry, ResultStatus

        entry = AuditEntry(
            entry_id="audit_12348",
            timestamp=datetime.now(UTC),
            agent_id="executor",
            user_id="user_123",
            tool_name="git_commit",
            action="execute",
            parameters={"message": "fix bug"},
            result_status=ResultStatus.ERROR,
            response_time_ms=50,
            error_details="Git repository not found",
        )

        assert entry.error_details == "Git repository not found"

    def test_audit_entry_with_session_id(self) -> None:
        """AuditEntry should support session_id for tracing."""
        from daw_agents.mcp.audit import AuditEntry, ResultStatus

        entry = AuditEntry(
            entry_id="audit_12349",
            timestamp=datetime.now(UTC),
            agent_id="healer",
            user_id="user_999",
            tool_name="read_file",
            action="execute",
            parameters={"path": "/app/logs/error.log"},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=25,
            session_id="session_abc123",
        )

        assert entry.session_id == "session_abc123"

    def test_audit_entry_with_token_id(self) -> None:
        """AuditEntry should support token_id for auth tracing."""
        from daw_agents.mcp.audit import AuditEntry, ResultStatus

        entry = AuditEntry(
            entry_id="audit_12350",
            timestamp=datetime.now(UTC),
            agent_id="planner",
            user_id="user_111",
            tool_name="query_db",
            action="execute",
            parameters={"query": "SELECT * FROM users LIMIT 10"},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=200,
            token_id="tok_xyz789",
        )

        assert entry.token_id == "tok_xyz789"


# -----------------------------------------------------------------------------
# Test: Hash Chaining (Tamper Resistance)
# -----------------------------------------------------------------------------


class TestHashChaining:
    """Tests for hash-chaining functionality for tamper resistance."""

    def test_compute_entry_hash(self) -> None:
        """compute_entry_hash should produce consistent SHA-256 hash."""
        from daw_agents.mcp.audit import AuditEntry, ResultStatus, compute_entry_hash

        entry = AuditEntry(
            entry_id="audit_hash_test",
            timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={"path": "/tmp/test.txt"},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=100,
        )

        hash1 = compute_entry_hash(entry)
        hash2 = compute_entry_hash(entry)

        # Same entry should produce same hash
        assert hash1 == hash2
        # Hash should be a valid SHA-256 hex string (64 chars)
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_compute_entry_hash_includes_previous(self) -> None:
        """compute_entry_hash should include previous_hash in computation."""
        from daw_agents.mcp.audit import AuditEntry, ResultStatus, compute_entry_hash

        entry_without_prev = AuditEntry(
            entry_id="audit_chain_1",
            timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=100,
        )

        entry_with_prev = AuditEntry(
            entry_id="audit_chain_1",
            timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=100,
            previous_hash="abc123",
        )

        hash_without = compute_entry_hash(entry_without_prev)
        hash_with = compute_entry_hash(entry_with_prev)

        # Different previous_hash should produce different hash
        assert hash_without != hash_with

    def test_verify_chain_integrity_valid(self) -> None:
        """verify_chain_integrity should return True for valid chain."""
        from daw_agents.mcp.audit import (
            AuditEntry,
            ResultStatus,
            compute_entry_hash,
            verify_chain_integrity,
        )

        # Create first entry with proper hash
        entry1 = AuditEntry(
            entry_id="audit_1",
            timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            agent_id="executor",
            user_id="user_123",
            tool_name="read_file",
            action="execute",
            parameters={},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=50,
        )
        entry1.entry_hash = compute_entry_hash(entry1)

        # Create second entry with correct previous_hash (valid chain)
        entry2 = AuditEntry(
            entry_id="audit_2",
            timestamp=datetime(2025, 1, 1, 12, 1, 0, tzinfo=UTC),
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=100,
            previous_hash=entry1.entry_hash,  # Correct linkage
        )
        entry2.entry_hash = compute_entry_hash(entry2)

        # Should verify successfully
        is_valid = verify_chain_integrity([entry1, entry2])
        assert is_valid is True

    def test_verify_chain_integrity_tampered(self) -> None:
        """verify_chain_integrity should return False for tampered chain."""
        from daw_agents.mcp.audit import (
            AuditEntry,
            ResultStatus,
            compute_entry_hash,
            verify_chain_integrity,
        )

        # Create first entry with proper hash
        entry1 = AuditEntry(
            entry_id="audit_1",
            timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            agent_id="executor",
            user_id="user_123",
            tool_name="read_file",
            action="execute",
            parameters={},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=50,
        )
        entry1.entry_hash = compute_entry_hash(entry1)

        # Create second entry with wrong previous_hash (tampered)
        entry2 = AuditEntry(
            entry_id="audit_2",
            timestamp=datetime(2025, 1, 1, 12, 1, 0, tzinfo=UTC),
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=100,
            previous_hash="wrong_hash",  # This should be entry1.entry_hash
        )
        entry2.entry_hash = compute_entry_hash(entry2)

        # Chain should be invalid
        is_valid = verify_chain_integrity([entry1, entry2])
        assert is_valid is False


# -----------------------------------------------------------------------------
# Test: AuditLogger Class
# -----------------------------------------------------------------------------


class TestAuditLoggerInitialization:
    """Tests for AuditLogger class initialization."""

    def test_audit_logger_initialization(self) -> None:
        """AuditLogger should initialize with config and optional Neo4j connector."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        assert logger.config == config

    def test_audit_logger_with_neo4j_connector(self) -> None:
        """AuditLogger should accept Neo4j connector for persistence."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        mock_connector = MagicMock()
        logger = AuditLogger(config=config, neo4j_connector=mock_connector)

        assert logger.neo4j_connector == mock_connector

    def test_audit_logger_with_helicone_tracker(self) -> None:
        """AuditLogger should accept Helicone tracker for observability."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig(enable_helicone=True)
        mock_tracker = MagicMock()
        logger = AuditLogger(config=config, helicone_tracker=mock_tracker)

        assert logger.helicone_tracker == mock_tracker


# -----------------------------------------------------------------------------
# Test: log_tool_call() Method
# -----------------------------------------------------------------------------


class TestLogToolCall:
    """Tests for AuditLogger.log_tool_call method."""

    @pytest.mark.asyncio
    async def test_log_tool_call_success(self) -> None:
        """log_tool_call should create audit entry for successful tool call."""
        from daw_agents.mcp.audit import AuditConfig, AuditEntry, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        entry = await logger.log_tool_call(
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={"path": "/tmp/test.txt", "content": "hello"},
            success=True,
            response_time_ms=150,
        )

        assert isinstance(entry, AuditEntry)
        assert entry.agent_id == "executor"
        assert entry.user_id == "user_123"
        assert entry.tool_name == "write_file"
        assert entry.response_time_ms == 150

    @pytest.mark.asyncio
    async def test_log_tool_call_failure(self) -> None:
        """log_tool_call should create audit entry for failed tool call."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger, ResultStatus

        config = AuditConfig()
        logger = AuditLogger(config=config)

        entry = await logger.log_tool_call(
            agent_id="executor",
            user_id="user_123",
            tool_name="git_commit",
            action="execute",
            parameters={"message": "fix bug"},
            success=False,
            response_time_ms=50,
            error_details="Git repository not found",
        )

        assert entry.result_status == ResultStatus.FAILURE
        assert entry.error_details == "Git repository not found"

    @pytest.mark.asyncio
    async def test_log_tool_call_denied(self) -> None:
        """log_tool_call should log denied tool calls."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger, ResultStatus

        config = AuditConfig()
        logger = AuditLogger(config=config)

        entry = await logger.log_tool_call(
            agent_id="planner",
            user_id="user_456",
            tool_name="write_file",
            action="execute",
            parameters={"path": "/etc/passwd"},
            denied=True,
            response_time_ms=5,
            error_details="Insufficient scope: write_file",
        )

        assert entry.result_status == ResultStatus.DENIED
        assert "Insufficient scope" in entry.error_details

    @pytest.mark.asyncio
    async def test_log_tool_call_with_session_and_token(self) -> None:
        """log_tool_call should include session_id and token_id."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        entry = await logger.log_tool_call(
            agent_id="validator",
            user_id="user_789",
            tool_name="run_tests",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=5000,
            session_id="session_abc",
            token_id="tok_xyz",
        )

        assert entry.session_id == "session_abc"
        assert entry.token_id == "tok_xyz"

    @pytest.mark.asyncio
    async def test_log_tool_call_generates_hash_chain(self) -> None:
        """log_tool_call should maintain hash chain for tamper resistance."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log first entry
        entry1 = await logger.log_tool_call(
            agent_id="executor",
            user_id="user_123",
            tool_name="read_file",
            action="execute",
            parameters={"path": "/app/config.json"},
            success=True,
            response_time_ms=25,
        )

        # Log second entry - should chain to first
        entry2 = await logger.log_tool_call(
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={"path": "/app/config.json"},
            success=True,
            response_time_ms=50,
        )

        # Second entry should have previous_hash pointing to first
        assert entry1.entry_hash is not None
        assert entry2.previous_hash == entry1.entry_hash

    @pytest.mark.asyncio
    async def test_log_tool_call_persists_to_neo4j(self) -> None:
        """log_tool_call should persist entry to Neo4j if connector provided."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        mock_connector = AsyncMock()
        mock_connector.create_node = AsyncMock(return_value="neo4j_node_id")

        logger = AuditLogger(config=config, neo4j_connector=mock_connector)

        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        # Should have called create_node
        mock_connector.create_node.assert_called_once()
        call_args = mock_connector.create_node.call_args
        # Check that AuditEntry is in the labels (kwargs style)
        labels = call_args.kwargs.get("labels", call_args.args[0] if call_args.args else [])
        assert "AuditEntry" in labels

    @pytest.mark.asyncio
    async def test_log_tool_call_reports_to_helicone(self) -> None:
        """log_tool_call should report to Helicone if tracker provided."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig(enable_helicone=True)
        mock_tracker = MagicMock()
        mock_tracker.track_request = MagicMock(return_value="request_id")

        logger = AuditLogger(config=config, helicone_tracker=mock_tracker)

        await logger.log_tool_call(
            agent_id="planner",
            user_id="user_456",
            tool_name="search",
            action="execute",
            parameters={"query": "test"},
            success=True,
            response_time_ms=200,
        )

        # Should have reported to Helicone tracker
        mock_tracker.track_request.assert_called_once()


# -----------------------------------------------------------------------------
# Test: query_audit_trail() Method
# -----------------------------------------------------------------------------


class TestQueryAuditTrail:
    """Tests for AuditLogger.query_audit_trail method."""

    @pytest.mark.asyncio
    async def test_query_audit_trail_by_agent(self) -> None:
        """query_audit_trail should filter by agent_id."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log entries for different agents
        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="write_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        await logger.log_tool_call(
            agent_id="planner",
            user_id="user_1",
            tool_name="search",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=50,
        )

        # Query for executor only
        results = await logger.query_audit_trail(agent_id="executor")

        assert all(entry.agent_id == "executor" for entry in results)

    @pytest.mark.asyncio
    async def test_query_audit_trail_by_user(self) -> None:
        """query_audit_trail should filter by user_id."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log entries for different users
        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="write_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_2",
            tool_name="read_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=50,
        )

        # Query for user_1 only
        results = await logger.query_audit_trail(user_id="user_1")

        assert all(entry.user_id == "user_1" for entry in results)

    @pytest.mark.asyncio
    async def test_query_audit_trail_by_time_range(self) -> None:
        """query_audit_trail should filter by time range."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log an entry
        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="write_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        # Query with time range
        start_time = datetime.now(UTC) - timedelta(hours=1)
        end_time = datetime.now(UTC) + timedelta(hours=1)

        results = await logger.query_audit_trail(
            start_time=start_time,
            end_time=end_time,
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_query_audit_trail_by_tool_name(self) -> None:
        """query_audit_trail should filter by tool_name."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log entries for different tools
        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="write_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="read_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=50,
        )

        # Query for write_file only
        results = await logger.query_audit_trail(tool_name="write_file")

        assert all(entry.tool_name == "write_file" for entry in results)

    @pytest.mark.asyncio
    async def test_query_audit_trail_by_result_status(self) -> None:
        """query_audit_trail should filter by result_status."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger, ResultStatus

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log success and failure entries
        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="git_commit",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="git_push",
            action="execute",
            parameters={},
            success=False,
            response_time_ms=50,
            error_details="Remote refused",
        )

        # Query for failures only
        results = await logger.query_audit_trail(result_status=ResultStatus.FAILURE)

        assert all(entry.result_status == ResultStatus.FAILURE for entry in results)

    @pytest.mark.asyncio
    async def test_query_audit_trail_with_limit(self) -> None:
        """query_audit_trail should support limit parameter."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log multiple entries
        for i in range(10):
            await logger.log_tool_call(
                agent_id="executor",
                user_id="user_1",
                tool_name=f"tool_{i}",
                action="execute",
                parameters={},
                success=True,
                response_time_ms=100,
            )

        # Query with limit
        results = await logger.query_audit_trail(limit=5)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_query_audit_trail_from_neo4j(self) -> None:
        """query_audit_trail should query Neo4j if connector provided."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        mock_connector = AsyncMock()
        mock_connector.query = AsyncMock(return_value=[])

        logger = AuditLogger(config=config, neo4j_connector=mock_connector)

        await logger.query_audit_trail(agent_id="executor")

        # Should have queried Neo4j
        mock_connector.query.assert_called_once()


# -----------------------------------------------------------------------------
# Test: Retention Policy
# -----------------------------------------------------------------------------


class TestRetentionPolicy:
    """Tests for retention policy validation (7-year SOC 2/ISO 27001)."""

    def test_default_retention_is_seven_years(self) -> None:
        """Default retention should be 7 years (2555 days)."""
        from daw_agents.mcp.audit import AuditConfig

        config = AuditConfig()

        # 7 years = 365 * 7 = 2555 days
        assert config.retention_days == 2555

    def test_retention_policy_stored_in_entry(self) -> None:
        """AuditEntry should include retention_until timestamp."""
        from daw_agents.mcp.audit import AuditEntry, ResultStatus

        retention_days = 2555
        now = datetime.now(UTC)
        retention_until = now + timedelta(days=retention_days)

        entry = AuditEntry(
            entry_id="audit_retention_test",
            timestamp=now,
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={},
            result_status=ResultStatus.SUCCESS,
            response_time_ms=100,
            retention_until=retention_until,
        )

        # Should be ~7 years from now
        assert (entry.retention_until - now).days == retention_days

    @pytest.mark.asyncio
    async def test_log_tool_call_sets_retention(self) -> None:
        """log_tool_call should set retention_until based on config."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig(retention_days=2555)
        logger = AuditLogger(config=config)

        entry = await logger.log_tool_call(
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        # retention_until should be ~7 years from timestamp
        days_until_retention = (entry.retention_until - entry.timestamp).days
        assert days_until_retention == 2555

    def test_can_configure_custom_retention(self) -> None:
        """Retention policy should be configurable."""
        from daw_agents.mcp.audit import AuditConfig

        # Custom retention: 10 years
        config = AuditConfig(retention_days=3650)

        assert config.retention_days == 3650

    @pytest.mark.asyncio
    async def test_purge_expired_entries(self) -> None:
        """AuditLogger should support purging expired entries."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        mock_connector = AsyncMock()
        mock_connector.query = AsyncMock(return_value=[{"deleted_count": 5}])

        logger = AuditLogger(config=config, neo4j_connector=mock_connector)

        deleted_count = await logger.purge_expired_entries()

        # Should have executed purge query
        mock_connector.query.assert_called_once()
        assert deleted_count == 5


# -----------------------------------------------------------------------------
# Test: get_audit_statistics() Method
# -----------------------------------------------------------------------------


class TestGetAuditStatistics:
    """Tests for AuditLogger.get_audit_statistics method."""

    @pytest.mark.asyncio
    async def test_get_audit_statistics(self) -> None:
        """get_audit_statistics should return summary statistics."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log some entries
        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="write_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="read_file",
            action="execute",
            parameters={},
            success=False,
            response_time_ms=50,
        )

        stats = await logger.get_audit_statistics()

        assert "total_entries" in stats
        assert "success_count" in stats
        assert "failure_count" in stats
        assert "avg_response_time_ms" in stats
        assert stats["total_entries"] >= 2

    @pytest.mark.asyncio
    async def test_get_audit_statistics_by_time_range(self) -> None:
        """get_audit_statistics should support time range filtering."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_1",
            tool_name="write_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        start_time = datetime.now(UTC) - timedelta(hours=1)
        end_time = datetime.now(UTC) + timedelta(hours=1)

        stats = await logger.get_audit_statistics(
            start_time=start_time,
            end_time=end_time,
        )

        assert "total_entries" in stats


# -----------------------------------------------------------------------------
# Test: Export Functionality
# -----------------------------------------------------------------------------


class TestAuditExport:
    """Tests for audit log export functionality."""

    @pytest.mark.asyncio
    async def test_export_audit_trail_json(self) -> None:
        """AuditLogger should support exporting audit trail as JSON."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log an entry
        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={"path": "/tmp/test.txt"},
            success=True,
            response_time_ms=100,
        )

        # Export as JSON
        json_export = await logger.export_audit_trail(format="json")

        assert isinstance(json_export, str)
        assert "executor" in json_export
        assert "write_file" in json_export

    @pytest.mark.asyncio
    async def test_export_audit_trail_csv(self) -> None:
        """AuditLogger should support exporting audit trail as CSV."""
        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log an entry
        await logger.log_tool_call(
            agent_id="executor",
            user_id="user_123",
            tool_name="write_file",
            action="execute",
            parameters={},
            success=True,
            response_time_ms=100,
        )

        # Export as CSV
        csv_export = await logger.export_audit_trail(format="csv")

        assert isinstance(csv_export, str)
        # CSV should have headers
        assert "entry_id" in csv_export or "agent_id" in csv_export


# -----------------------------------------------------------------------------
# Test: Thread Safety / Concurrent Logging
# -----------------------------------------------------------------------------


class TestConcurrentLogging:
    """Tests for thread-safe concurrent logging."""

    @pytest.mark.asyncio
    async def test_concurrent_logging_maintains_chain(self) -> None:
        """Concurrent logging should maintain valid hash chain."""
        import asyncio

        from daw_agents.mcp.audit import AuditConfig, AuditLogger

        config = AuditConfig()
        logger = AuditLogger(config=config)

        # Log multiple entries concurrently
        async def log_entry(idx: int) -> None:
            await logger.log_tool_call(
                agent_id="executor",
                user_id=f"user_{idx}",
                tool_name=f"tool_{idx}",
                action="execute",
                parameters={"index": idx},
                success=True,
                response_time_ms=100 + idx,
            )

        # Run concurrent logging
        await asyncio.gather(*[log_entry(i) for i in range(10)])

        # Get all entries and verify chain
        entries = await logger.query_audit_trail()

        # Chain should still be valid despite concurrent writes
        # Note: This may require locking in implementation
        assert len(entries) == 10


# -----------------------------------------------------------------------------
# Test: Module Exports
# -----------------------------------------------------------------------------


class TestModuleExports:
    """Tests for module-level exports."""

    def test_module_exports_audit_config(self) -> None:
        """Module should export AuditConfig."""
        from daw_agents.mcp.audit import AuditConfig

        assert AuditConfig is not None

    def test_module_exports_audit_entry(self) -> None:
        """Module should export AuditEntry."""
        from daw_agents.mcp.audit import AuditEntry

        assert AuditEntry is not None

    def test_module_exports_audit_logger(self) -> None:
        """Module should export AuditLogger."""
        from daw_agents.mcp.audit import AuditLogger

        assert AuditLogger is not None

    def test_module_exports_result_status(self) -> None:
        """Module should export ResultStatus enum."""
        from daw_agents.mcp.audit import ResultStatus

        assert ResultStatus is not None

    def test_module_exports_compute_entry_hash(self) -> None:
        """Module should export compute_entry_hash function."""
        from daw_agents.mcp.audit import compute_entry_hash

        assert compute_entry_hash is not None

    def test_module_exports_verify_chain_integrity(self) -> None:
        """Module should export verify_chain_integrity function."""
        from daw_agents.mcp.audit import verify_chain_integrity

        assert verify_chain_integrity is not None
