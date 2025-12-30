"""MCP Audit Logging for SOC 2/ISO 27001 Compliance (MCP-SEC-003).

This module implements comprehensive audit logging for MCP tool calls with:
- Full audit trail of every tool call with all required metadata
- SHA-256 hash-chaining for tamper resistance
- 7-year retention policy for SOC 2/ISO 27001 compliance
- Neo4j storage for persistent audit logs
- Helicone integration for observability

Every tool call is logged with:
- timestamp: When the call occurred (UTC)
- agent_id: Which agent made the call
- user_id: Which user initiated the workflow
- tool_name: Name of the tool being called
- action: Type of action (execute, query, etc.)
- parameters: Call parameters (sanitized)
- result_status: Success/failure/denied/error/timeout
- response_time_ms: How long the call took

Hash-Chaining:
Each audit entry includes a hash of its content plus the previous entry's hash,
creating an append-only chain that detects tampering. Any modification to a
historical entry breaks the chain.

References:
    - PRD FR-01.3.3: MCP Audit Logging requirements
    - SOC 2 Type II: Security event logging (CC7.2, CC7.3)
    - ISO 27001: A.12.4 Logging and monitoring

Example usage:
    config = AuditConfig()
    logger = AuditLogger(config=config, neo4j_connector=neo4j)

    # Log a tool call
    entry = await logger.log_tool_call(
        agent_id="executor",
        user_id="user_123",
        tool_name="write_file",
        action="execute",
        parameters={"path": "/tmp/test.txt"},
        success=True,
        response_time_ms=150,
    )

    # Query audit trail
    entries = await logger.query_audit_trail(
        agent_id="executor",
        start_time=datetime.now(UTC) - timedelta(hours=1),
    )

    # Verify chain integrity
    is_valid = verify_chain_integrity(entries)
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from daw_agents.memory.neo4j import Neo4jConnector
    from daw_agents.ops.helicone import HeliconeTracker

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class ResultStatus(str, Enum):
    """Status of a tool call result.

    SUCCESS: Tool call completed successfully
    FAILURE: Tool call failed (business logic error)
    ERROR: Tool call encountered an unexpected error
    DENIED: Tool call was denied due to insufficient permissions
    TIMEOUT: Tool call timed out
    """

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    DENIED = "denied"
    TIMEOUT = "timeout"


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------


class AuditConfig(BaseModel):
    """Configuration for MCP Audit Logging.

    Attributes:
        retention_days: Number of days to retain audit logs (default: 2555 = 7 years)
        hash_algorithm: Hash algorithm for chain integrity (default: sha256)
        enable_helicone: Whether to report to Helicone for observability
        max_parameter_length: Maximum length for parameter values in logs
        sanitize_sensitive_keys: Keys to redact from parameters
    """

    retention_days: int = Field(
        default=2555,  # 7 years = 365 * 7
        ge=1,
        description="Days to retain audit logs (SOC 2/ISO 27001 requires 7 years)",
    )
    hash_algorithm: str = Field(
        default="sha256",
        description="Hash algorithm for tamper resistance",
    )
    enable_helicone: bool = Field(
        default=False,
        description="Enable Helicone observability integration",
    )
    max_parameter_length: int = Field(
        default=10000,
        ge=100,
        description="Max length for parameter values (truncated if exceeded)",
    )
    sanitize_sensitive_keys: list[str] = Field(
        default_factory=lambda: [
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "credential",
            "auth",
        ],
        description="Parameter keys to redact for security",
    )


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------


class AuditEntry(BaseModel):
    """Audit log entry for a single tool call.

    Captures all required information per FR-01.3.3:
    - timestamp, agent_id, user_id, tool name, action, parameters,
      result status, response time

    Supports hash-chaining via entry_hash and previous_hash fields.

    Attributes:
        entry_id: Unique identifier for this entry
        timestamp: When the tool call occurred (UTC)
        agent_id: ID of the agent making the call
        user_id: ID of the user who initiated the workflow
        tool_name: Name of the tool being called
        action: Type of action (execute, query, etc.)
        parameters: Call parameters (sanitized)
        result_status: Result of the call
        response_time_ms: Call duration in milliseconds
        previous_hash: Hash of the previous entry (for chain integrity)
        entry_hash: Hash of this entry (computed on creation)
        error_details: Error message if call failed
        session_id: Optional session ID for tracing
        token_id: Optional token ID for auth tracing
        retention_until: When this entry can be deleted
    """

    entry_id: str = Field(description="Unique entry identifier")
    timestamp: datetime = Field(description="UTC timestamp of the call")
    agent_id: str = Field(description="Agent that made the call")
    user_id: str = Field(description="User who initiated the workflow")
    tool_name: str = Field(description="Name of the tool called")
    action: str = Field(description="Type of action (execute, query, etc.)")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Call parameters (sanitized)",
    )
    result_status: ResultStatus = Field(description="Result status of the call")
    response_time_ms: int = Field(ge=0, description="Call duration in milliseconds")

    # Hash chain fields
    previous_hash: str | None = Field(
        default=None,
        description="Hash of the previous entry for chain integrity",
    )
    entry_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of this entry",
    )

    # Optional metadata
    error_details: str | None = Field(
        default=None,
        description="Error message if call failed",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for tracing",
    )
    token_id: str | None = Field(
        default=None,
        description="Token ID for auth tracing",
    )
    retention_until: datetime | None = Field(
        default=None,
        description="When this entry can be deleted",
    )


# -----------------------------------------------------------------------------
# Hash Chain Functions
# -----------------------------------------------------------------------------


def compute_entry_hash(entry: AuditEntry, algorithm: str = "sha256") -> str:
    """Compute SHA-256 hash of an audit entry for chain integrity.

    The hash includes all critical fields to detect tampering:
    - entry_id, timestamp, agent_id, user_id, tool_name, action
    - parameters, result_status, response_time_ms
    - previous_hash (if present)

    Args:
        entry: The audit entry to hash
        algorithm: Hash algorithm (default: sha256)

    Returns:
        Hex-encoded hash string (64 characters for SHA-256)
    """
    # Create canonical representation for hashing
    hash_data = {
        "entry_id": entry.entry_id,
        "timestamp": entry.timestamp.isoformat(),
        "agent_id": entry.agent_id,
        "user_id": entry.user_id,
        "tool_name": entry.tool_name,
        "action": entry.action,
        "parameters": json.dumps(entry.parameters, sort_keys=True),
        "result_status": entry.result_status.value,
        "response_time_ms": entry.response_time_ms,
        "previous_hash": entry.previous_hash or "",
    }

    # Create deterministic JSON string
    canonical = json.dumps(hash_data, sort_keys=True)

    # Compute hash
    hasher = hashlib.new(algorithm)
    hasher.update(canonical.encode("utf-8"))
    return hasher.hexdigest()


def verify_chain_integrity(entries: list[AuditEntry]) -> bool:
    """Verify the integrity of an audit entry chain.

    Checks that:
    1. Each entry's stored hash matches its computed hash
    2. Each entry's previous_hash matches the prior entry's hash

    Args:
        entries: List of audit entries in chronological order

    Returns:
        True if the chain is valid, False if tampered
    """
    if not entries:
        return True

    for i, entry in enumerate(entries):
        # Verify this entry's hash matches computed hash
        # (We need to temporarily clear entry_hash for computation)
        stored_hash = entry.entry_hash
        if stored_hash is not None:
            expected_hash = compute_entry_hash(entry)
            # Note: We don't include entry_hash in the hash computation,
            # so we can compare directly
            if stored_hash != expected_hash:
                logger.warning(
                    "Hash mismatch for entry %s: stored=%s, computed=%s",
                    entry.entry_id,
                    stored_hash[:16],
                    expected_hash[:16],
                )
                return False

        # Verify chain linkage (skip first entry)
        if i > 0:
            previous_entry = entries[i - 1]
            if entry.previous_hash != previous_entry.entry_hash:
                logger.warning(
                    "Chain broken at entry %s: expected previous_hash=%s, got=%s",
                    entry.entry_id,
                    previous_entry.entry_hash[:16] if previous_entry.entry_hash else None,
                    entry.previous_hash[:16] if entry.previous_hash else None,
                )
                return False

    return True


# -----------------------------------------------------------------------------
# Audit Logger
# -----------------------------------------------------------------------------


class AuditLogger:
    """Logger for MCP tool call audit trail.

    Provides:
    - log_tool_call(): Log a tool call with all metadata
    - query_audit_trail(): Query historical audit entries
    - get_audit_statistics(): Get summary statistics
    - export_audit_trail(): Export audit trail in JSON/CSV
    - purge_expired_entries(): Remove entries past retention

    The logger maintains a hash chain for tamper resistance. Each entry
    includes a hash of its content plus the previous entry's hash.

    Supports Neo4j for persistent storage and Helicone for observability.

    Attributes:
        config: Audit configuration
        neo4j_connector: Optional Neo4j connector for persistence
        helicone_tracker: Optional Helicone tracker for observability
    """

    def __init__(
        self,
        config: AuditConfig,
        neo4j_connector: Neo4jConnector | None = None,
        helicone_tracker: HeliconeTracker | None = None,
    ) -> None:
        """Initialize the audit logger.

        Args:
            config: Audit configuration
            neo4j_connector: Optional Neo4j connector for persistent storage
            helicone_tracker: Optional Helicone tracker for observability
        """
        self.config = config
        self.neo4j_connector = neo4j_connector
        self.helicone_tracker = helicone_tracker

        # In-memory storage for entries (used when no Neo4j connector)
        self._entries: list[AuditEntry] = []

        # Lock for thread-safe hash chain operations
        self._chain_lock = asyncio.Lock()

        # Track last entry hash for chain continuation
        self._last_entry_hash: str | None = None

        logger.debug("Initialized AuditLogger with retention_days=%d", config.retention_days)

    def _sanitize_parameters(self, params: dict[str, Any]) -> dict[str, Any]:
        """Sanitize parameters by redacting sensitive values.

        Args:
            params: Raw parameters dictionary

        Returns:
            Sanitized parameters with sensitive values redacted
        """
        sanitized: dict[str, Any] = {}
        sensitive_keys = {k.lower() for k in self.config.sanitize_sensitive_keys}

        for key, value in params.items():
            key_lower = key.lower()

            # Check if key contains any sensitive substring
            is_sensitive = any(s in key_lower for s in sensitive_keys)

            if is_sensitive:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > self.config.max_parameter_length:
                sanitized[key] = value[: self.config.max_parameter_length] + "...[TRUNCATED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_parameters(value)
            else:
                sanitized[key] = value

        return sanitized

    async def log_tool_call(
        self,
        agent_id: str,
        user_id: str,
        tool_name: str,
        action: str,
        parameters: dict[str, Any],
        success: bool | None = None,
        denied: bool = False,
        response_time_ms: int = 0,
        error_details: str | None = None,
        session_id: str | None = None,
        token_id: str | None = None,
    ) -> AuditEntry:
        """Log a tool call to the audit trail.

        Creates an audit entry with all required metadata and maintains
        the hash chain for tamper resistance.

        Args:
            agent_id: ID of the agent making the call
            user_id: ID of the user who initiated the workflow
            tool_name: Name of the tool being called
            action: Type of action (execute, query, etc.)
            parameters: Call parameters (will be sanitized)
            success: True if call succeeded, False if failed
            denied: True if call was denied due to permissions
            response_time_ms: Call duration in milliseconds
            error_details: Error message if call failed
            session_id: Optional session ID for tracing
            token_id: Optional token ID for auth tracing

        Returns:
            The created audit entry with hash chain
        """
        # Determine result status
        if denied:
            result_status = ResultStatus.DENIED
        elif success is True:
            result_status = ResultStatus.SUCCESS
        elif success is False:
            result_status = ResultStatus.FAILURE
        else:
            result_status = ResultStatus.ERROR

        # Calculate retention deadline
        now = datetime.now(UTC)
        retention_until = now + timedelta(days=self.config.retention_days)

        # Create entry
        entry = AuditEntry(
            entry_id=f"audit_{uuid.uuid4().hex}",
            timestamp=now,
            agent_id=agent_id,
            user_id=user_id,
            tool_name=tool_name,
            action=action,
            parameters=self._sanitize_parameters(parameters),
            result_status=result_status,
            response_time_ms=response_time_ms,
            error_details=error_details,
            session_id=session_id,
            token_id=token_id,
            retention_until=retention_until,
        )

        # Thread-safe hash chain update
        async with self._chain_lock:
            # Set previous hash for chain continuity
            entry.previous_hash = self._last_entry_hash

            # Compute entry hash
            entry.entry_hash = compute_entry_hash(entry, self.config.hash_algorithm)

            # Update last hash for next entry
            self._last_entry_hash = entry.entry_hash

            # Store in memory
            self._entries.append(entry)

        # Persist to Neo4j if available
        if self.neo4j_connector is not None:
            await self._persist_to_neo4j(entry)

        # Report to Helicone if enabled
        if self.config.enable_helicone and self.helicone_tracker is not None:
            self._report_to_helicone(entry)

        logger.debug(
            "Logged tool call: %s/%s by %s (status=%s, time=%dms)",
            tool_name,
            action,
            agent_id,
            result_status.value,
            response_time_ms,
        )

        return entry

    async def _persist_to_neo4j(self, entry: AuditEntry) -> str | None:
        """Persist an audit entry to Neo4j.

        Args:
            entry: The audit entry to persist

        Returns:
            Neo4j node ID if successful, None otherwise
        """
        if self.neo4j_connector is None:
            return None

        try:
            properties = {
                "entry_id": entry.entry_id,
                "timestamp": entry.timestamp.isoformat(),
                "agent_id": entry.agent_id,
                "user_id": entry.user_id,
                "tool_name": entry.tool_name,
                "action": entry.action,
                "parameters": json.dumps(entry.parameters),
                "result_status": entry.result_status.value,
                "response_time_ms": entry.response_time_ms,
                "previous_hash": entry.previous_hash,
                "entry_hash": entry.entry_hash,
                "error_details": entry.error_details,
                "session_id": entry.session_id,
                "token_id": entry.token_id,
                "retention_until": (
                    entry.retention_until.isoformat() if entry.retention_until else None
                ),
            }

            node_id = await self.neo4j_connector.create_node(
                labels=["AuditEntry", "MCP"],
                properties=properties,
            )

            logger.debug("Persisted audit entry %s to Neo4j as %s", entry.entry_id, node_id)
            return node_id

        except Exception as e:
            logger.error("Failed to persist audit entry to Neo4j: %s", e)
            return None

    def _report_to_helicone(self, entry: AuditEntry) -> None:
        """Report audit entry to Helicone for observability.

        Args:
            entry: The audit entry to report
        """
        if self.helicone_tracker is None:
            return

        try:
            self.helicone_tracker.track_request(
                model="mcp-tool-call",
                task_type="audit",
                tokens_prompt=0,
                tokens_completion=0,
                cost_usd=0.0,
                latency_ms=entry.response_time_ms,
                metadata={
                    "entry_id": entry.entry_id,
                    "agent_id": entry.agent_id,
                    "tool_name": entry.tool_name,
                    "result_status": entry.result_status.value,
                },
            )
        except Exception as e:
            logger.warning("Failed to report to Helicone: %s", e)

    async def query_audit_trail(
        self,
        agent_id: str | None = None,
        user_id: str | None = None,
        tool_name: str | None = None,
        result_status: ResultStatus | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        session_id: str | None = None,
        limit: int | None = None,
    ) -> list[AuditEntry]:
        """Query the audit trail with filters.

        Args:
            agent_id: Filter by agent ID
            user_id: Filter by user ID
            tool_name: Filter by tool name
            result_status: Filter by result status
            start_time: Filter entries after this time
            end_time: Filter entries before this time
            session_id: Filter by session ID
            limit: Maximum number of entries to return

        Returns:
            List of matching audit entries in chronological order
        """
        # If Neo4j connector available, query from database
        if self.neo4j_connector is not None:
            return await self._query_from_neo4j(
                agent_id=agent_id,
                user_id=user_id,
                tool_name=tool_name,
                result_status=result_status,
                start_time=start_time,
                end_time=end_time,
                session_id=session_id,
                limit=limit,
            )

        # Otherwise, filter in-memory entries
        results = self._entries.copy()

        if agent_id is not None:
            results = [e for e in results if e.agent_id == agent_id]

        if user_id is not None:
            results = [e for e in results if e.user_id == user_id]

        if tool_name is not None:
            results = [e for e in results if e.tool_name == tool_name]

        if result_status is not None:
            results = [e for e in results if e.result_status == result_status]

        if start_time is not None:
            results = [e for e in results if e.timestamp >= start_time]

        if end_time is not None:
            results = [e for e in results if e.timestamp <= end_time]

        if session_id is not None:
            results = [e for e in results if e.session_id == session_id]

        # Sort by timestamp
        results.sort(key=lambda e: e.timestamp)

        # Apply limit
        if limit is not None:
            results = results[:limit]

        return results

    async def _query_from_neo4j(
        self,
        agent_id: str | None = None,
        user_id: str | None = None,
        tool_name: str | None = None,
        result_status: ResultStatus | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        session_id: str | None = None,
        limit: int | None = None,
    ) -> list[AuditEntry]:
        """Query audit trail from Neo4j.

        Args:
            (same as query_audit_trail)

        Returns:
            List of matching audit entries
        """
        if self.neo4j_connector is None:
            return []

        # Build Cypher query
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if agent_id is not None:
            conditions.append("n.agent_id = $agent_id")
            params["agent_id"] = agent_id

        if user_id is not None:
            conditions.append("n.user_id = $user_id")
            params["user_id"] = user_id

        if tool_name is not None:
            conditions.append("n.tool_name = $tool_name")
            params["tool_name"] = tool_name

        if result_status is not None:
            conditions.append("n.result_status = $result_status")
            params["result_status"] = result_status.value

        if start_time is not None:
            conditions.append("n.timestamp >= $start_time")
            params["start_time"] = start_time.isoformat()

        if end_time is not None:
            conditions.append("n.timestamp <= $end_time")
            params["end_time"] = end_time.isoformat()

        if session_id is not None:
            conditions.append("n.session_id = $session_id")
            params["session_id"] = session_id

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        limit_clause = f"LIMIT {limit}" if limit else ""

        cypher = f"""
            MATCH (n:AuditEntry)
            WHERE {where_clause}
            RETURN n
            ORDER BY n.timestamp
            {limit_clause}
        """

        try:
            records = await self.neo4j_connector.query(cypher, params)

            entries: list[AuditEntry] = []
            for record in records:
                node = record.get("n", {})
                entries.append(
                    AuditEntry(
                        entry_id=node.get("entry_id", ""),
                        timestamp=datetime.fromisoformat(node.get("timestamp", "")),
                        agent_id=node.get("agent_id", ""),
                        user_id=node.get("user_id", ""),
                        tool_name=node.get("tool_name", ""),
                        action=node.get("action", ""),
                        parameters=json.loads(node.get("parameters", "{}")),
                        result_status=ResultStatus(node.get("result_status", "error")),
                        response_time_ms=node.get("response_time_ms", 0),
                        previous_hash=node.get("previous_hash"),
                        entry_hash=node.get("entry_hash"),
                        error_details=node.get("error_details"),
                        session_id=node.get("session_id"),
                        token_id=node.get("token_id"),
                        retention_until=(
                            datetime.fromisoformat(node["retention_until"])
                            if node.get("retention_until")
                            else None
                        ),
                    )
                )

            return entries

        except Exception as e:
            logger.error("Failed to query audit trail from Neo4j: %s", e)
            return []

    async def get_audit_statistics(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get summary statistics for audit entries.

        Args:
            start_time: Filter entries after this time
            end_time: Filter entries before this time

        Returns:
            Dictionary with statistics:
            - total_entries: Total number of entries
            - success_count: Number of successful calls
            - failure_count: Number of failed calls
            - denied_count: Number of denied calls
            - error_count: Number of error calls
            - avg_response_time_ms: Average response time
            - by_agent: Breakdown by agent
            - by_tool: Breakdown by tool
        """
        entries = await self.query_audit_trail(
            start_time=start_time,
            end_time=end_time,
        )

        if not entries:
            return {
                "total_entries": 0,
                "success_count": 0,
                "failure_count": 0,
                "denied_count": 0,
                "error_count": 0,
                "avg_response_time_ms": 0.0,
                "by_agent": {},
                "by_tool": {},
            }

        success_count = sum(1 for e in entries if e.result_status == ResultStatus.SUCCESS)
        failure_count = sum(1 for e in entries if e.result_status == ResultStatus.FAILURE)
        denied_count = sum(1 for e in entries if e.result_status == ResultStatus.DENIED)
        error_count = sum(1 for e in entries if e.result_status == ResultStatus.ERROR)
        total_response_time = sum(e.response_time_ms for e in entries)

        # Breakdown by agent
        by_agent: dict[str, int] = {}
        for entry in entries:
            by_agent[entry.agent_id] = by_agent.get(entry.agent_id, 0) + 1

        # Breakdown by tool
        by_tool: dict[str, int] = {}
        for entry in entries:
            by_tool[entry.tool_name] = by_tool.get(entry.tool_name, 0) + 1

        return {
            "total_entries": len(entries),
            "success_count": success_count,
            "failure_count": failure_count,
            "denied_count": denied_count,
            "error_count": error_count,
            "avg_response_time_ms": total_response_time / len(entries),
            "by_agent": by_agent,
            "by_tool": by_tool,
        }

    async def export_audit_trail(
        self,
        format: str = "json",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> str:
        """Export audit trail in JSON or CSV format.

        Args:
            format: Export format ("json" or "csv")
            start_time: Filter entries after this time
            end_time: Filter entries before this time

        Returns:
            String containing the exported data
        """
        entries = await self.query_audit_trail(
            start_time=start_time,
            end_time=end_time,
        )

        if format.lower() == "json":
            return json.dumps(
                [e.model_dump(mode="json") for e in entries],
                indent=2,
                default=str,
            )

        elif format.lower() == "csv":
            output = io.StringIO()
            if entries:
                fieldnames = list(entries[0].model_dump().keys())
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for entry in entries:
                    row = entry.model_dump(mode="json")
                    # Convert complex types to strings
                    for key, value in row.items():
                        if isinstance(value, dict):
                            row[key] = json.dumps(value)
                        elif isinstance(value, datetime):
                            row[key] = value.isoformat()
                    writer.writerow(row)
            return output.getvalue()

        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def purge_expired_entries(self) -> int:
        """Purge audit entries past their retention period.

        Returns:
            Number of entries deleted
        """
        now = datetime.now(UTC)

        if self.neo4j_connector is not None:
            # Delete from Neo4j
            cypher = """
                MATCH (n:AuditEntry)
                WHERE n.retention_until IS NOT NULL
                  AND n.retention_until < $now
                DELETE n
                RETURN COUNT(*) as deleted_count
            """
            try:
                records = await self.neo4j_connector.query(
                    cypher,
                    {"now": now.isoformat()},
                )
                if records:
                    return int(records[0].get("deleted_count", 0))
            except Exception as e:
                logger.error("Failed to purge expired entries from Neo4j: %s", e)
                return 0

        # Purge from in-memory storage
        before_count = len(self._entries)
        self._entries = [
            e
            for e in self._entries
            if e.retention_until is None or e.retention_until >= now
        ]
        deleted_count = before_count - len(self._entries)

        logger.info("Purged %d expired audit entries", deleted_count)
        return deleted_count


# -----------------------------------------------------------------------------
# Module Exports
# -----------------------------------------------------------------------------

__all__ = [
    "AuditConfig",
    "AuditEntry",
    "AuditLogger",
    "ResultStatus",
    "compute_entry_hash",
    "verify_chain_integrity",
]
