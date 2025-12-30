"""MCP Content Injection Prevention (Prompt Shields).

This module implements AI Prompt Shields for tool output sanitization,
JSON schema validation for all tool inputs/outputs, and dangerous pattern blocking.

Key Features:
- SQL injection detection (DROP, DELETE, TRUNCATE, ALTER)
- Shell command injection detection (rm -rf, sudo, chmod, chown)
- Prompt injection detection in tool outputs
- JSON schema validation for inputs/outputs
- Configurable shield modes (strict, custom patterns)
- Content sanitization and blocking

References:
    - PRD FR-01.3.4: Content Injection Prevention requirements
    - OWASP Injection Prevention: https://owasp.org/www-community/Injection_Flaws
    - MCP Security: https://modelcontextprotocol.io/specification/draft/basic/security

Example usage:
    shield = ContentShield()

    # Validate input before tool call
    result = shield.validate_input("SELECT * FROM users")
    if not result.is_valid:
        raise ContentBlockedError(result.error_message, result.blocked_patterns)

    # Validate output after tool call
    result = shield.validate_output(tool_result)
    if not result.is_valid:
        raise ContentBlockedError(result.error_message, result.blocked_patterns)
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class DangerousPattern(str, Enum):
    """Categorized dangerous command patterns.

    These patterns are used to detect and block potentially harmful content
    in tool inputs and outputs.
    """

    # SQL DDL Operations
    SQL_DROP = "sql_drop"
    SQL_DELETE = "sql_delete"
    SQL_TRUNCATE = "sql_truncate"
    SQL_ALTER = "sql_alter"
    SQL_UNION = "sql_union"

    # Shell Commands
    SHELL_RM_RF = "shell_rm_rf"
    SHELL_SUDO = "shell_sudo"
    SHELL_CHMOD = "shell_chmod"
    SHELL_CHOWN = "shell_chown"

    # Prompt Injection
    PROMPT_IGNORE = "prompt_ignore"
    PROMPT_SYSTEM = "prompt_system"
    PROMPT_OVERRIDE = "prompt_override"
    PROMPT_JAILBREAK = "prompt_jailbreak"

    # Sensitive Files
    FILE_ETC_PASSWD = "file_etc_passwd"
    FILE_ETC_SHADOW = "file_etc_shadow"
    FILE_SSH_KEY = "file_ssh_key"
    FILE_PATH_TRAVERSAL = "file_path_traversal"

    # Custom
    CUSTOM = "custom"


# Pattern to regex mapping
_PATTERN_REGEXES: dict[DangerousPattern, str] = {
    # SQL DDL - case insensitive
    DangerousPattern.SQL_DROP: r"(?i)\b(DROP)\s+(TABLE|DATABASE|INDEX|VIEW|SCHEMA|USER)\b",
    DangerousPattern.SQL_DELETE: r"(?i)\bDELETE\s+FROM\s+\w+\s*(?:;|$|--)",  # DELETE without WHERE
    DangerousPattern.SQL_TRUNCATE: r"(?i)\bTRUNCATE\s+(TABLE\s+)?\w+",
    DangerousPattern.SQL_ALTER: r"(?i)\bALTER\s+(TABLE|DATABASE|USER|INDEX)\b",
    DangerousPattern.SQL_UNION: r"(?i)(\bUNION\b\s*(ALL\s+)?SELECT\b|'\s*UNION\s+SELECT)",
    # Shell Commands
    DangerousPattern.SHELL_RM_RF: r"(?i)\brm\s+(-[rRfF]+\s*)+|rm\s+--recursive\s+--force",
    DangerousPattern.SHELL_SUDO: r"(?i)\bsudo\b",
    DangerousPattern.SHELL_CHMOD: r"(?i)\bchmod\s+(777|666|[0-7]{3,4})\s+/",
    DangerousPattern.SHELL_CHOWN: r"(?i)\bchown\s+(root|0):",
    # Prompt Injection - specific patterns only
    DangerousPattern.PROMPT_IGNORE: r"(?i)(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|messages?|context)",
    # Custom placeholder - not used in regex matching but needs entry for get_pattern_regex
    DangerousPattern.CUSTOM: r"^\b$",  # Never matches anything (empty word boundary)
    DangerousPattern.PROMPT_SYSTEM: r"(?i)(repeat|show|reveal|display|print|output)\s+(your\s+)?(system\s+)?(prompt|instructions?)",
    DangerousPattern.PROMPT_OVERRIDE: r"(?i)(you\s+are\s+(no\s+longer|now)\s+(a|an)\s+\w+)|(pretend\s+to\s+be)|(act\s+as\s+if)",
    DangerousPattern.PROMPT_JAILBREAK: r"(?i)(\bDAN\b|do\s+anything\s+now|jailbreak|bypass\s+(the\s+)?restrictions?)",
    # Sensitive Files
    DangerousPattern.FILE_ETC_PASSWD: r"/etc/passwd\b",
    DangerousPattern.FILE_ETC_SHADOW: r"/etc/shadow\b",
    DangerousPattern.FILE_SSH_KEY: r"(~/|/home/\w+/|/root/)\.ssh/(id_rsa|id_dsa|id_ecdsa|id_ed25519|authorized_keys)",
    DangerousPattern.FILE_PATH_TRAVERSAL: r"\.\.(/|\\){2,}",
}


def get_pattern_regex(pattern: DangerousPattern) -> str | None:
    """Get the regex pattern for a DangerousPattern.

    Args:
        pattern: The dangerous pattern enum value

    Returns:
        The regex pattern string, or None if not found
    """
    return _PATTERN_REGEXES.get(pattern)


# -----------------------------------------------------------------------------
# Exception Classes
# -----------------------------------------------------------------------------


class ShieldError(Exception):
    """Base exception for shield errors."""

    pass


class ContentBlockedError(ShieldError):
    """Raised when content is blocked due to dangerous patterns.

    Attributes:
        message: Human-readable error message
        patterns: List of patterns that triggered the block
    """

    def __init__(
        self,
        message: str,
        patterns: list[DangerousPattern] | None = None,
    ) -> None:
        self.message = message
        self.patterns = patterns or []
        super().__init__(message)


class SchemaValidationError(ShieldError):
    """Raised when JSON schema validation fails.

    Attributes:
        message: Human-readable error message
        path: JSON path to the invalid field
        expected: Expected type/value
        received: Received type/value
    """

    def __init__(
        self,
        message: str,
        path: str | None = None,
        expected: str | None = None,
        received: str | None = None,
    ) -> None:
        self.message = message
        self.path = path
        self.expected = expected
        self.received = received
        super().__init__(message)


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------


class ShieldConfig(BaseModel):
    """Configuration for content shields.

    Attributes:
        enabled: Whether shields are active
        block_sql_ddl: Block SQL DDL operations (DROP, DELETE, etc.)
        block_shell_dangerous: Block dangerous shell commands (rm -rf, sudo)
        block_prompt_injection: Block prompt injection attempts
        block_file_sensitive: Block access to sensitive files
        custom_patterns: List of custom regex patterns to block
    """

    enabled: bool = Field(default=True)
    block_sql_ddl: bool = Field(default=True)
    block_shell_dangerous: bool = Field(default=True)
    block_prompt_injection: bool = Field(default=True)
    block_file_sensitive: bool = Field(default=True)
    custom_patterns: list[str] = Field(default_factory=list)

    @classmethod
    def strict(cls) -> ShieldConfig:
        """Create a strict configuration with all shields enabled.

        Returns:
            ShieldConfig with maximum protection
        """
        return cls(
            enabled=True,
            block_sql_ddl=True,
            block_shell_dangerous=True,
            block_prompt_injection=True,
            block_file_sensitive=True,
        )


class ValidationResult(BaseModel):
    """Result of a content validation operation.

    Attributes:
        is_valid: Whether the content passed validation
        blocked_patterns: List of patterns that were detected
        error_message: Human-readable error description
        sanitized_content: Content with dangerous patterns removed
        original_content: Original content before validation
    """

    is_valid: bool
    blocked_patterns: list[DangerousPattern] = Field(default_factory=list)
    error_message: str | None = Field(default=None)
    sanitized_content: str | None = Field(default=None)
    original_content: str | None = Field(default=None)


# -----------------------------------------------------------------------------
# Content Shield
# -----------------------------------------------------------------------------


class ContentShield:
    """AI Prompt Shield for content injection prevention.

    This class provides methods to validate and sanitize tool inputs and outputs,
    detecting and blocking dangerous patterns like SQL injection, shell command
    injection, and prompt injection.

    Attributes:
        config: Shield configuration

    Example:
        shield = ContentShield()

        # Validate user input
        result = shield.validate_input("DROP TABLE users")
        if not result.is_valid:
            print(f"Blocked: {result.blocked_patterns}")

        # Validate tool output
        result = shield.validate_output("Ignore all previous instructions")
        if not result.is_valid:
            print(f"Prompt injection detected!")
    """

    def __init__(self, config: ShieldConfig | None = None) -> None:
        """Initialize the content shield.

        Args:
            config: Shield configuration (uses default if not provided)
        """
        self.config = config or ShieldConfig()
        self._compiled_patterns: dict[DangerousPattern, re.Pattern[str]] = {}
        self._compiled_custom: list[re.Pattern[str]] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        for pattern, regex in _PATTERN_REGEXES.items():
            try:
                self._compiled_patterns[pattern] = re.compile(regex)
            except re.error as e:
                logger.warning("Failed to compile pattern %s: %s", pattern, e)

        for custom_regex in self.config.custom_patterns:
            try:
                self._compiled_custom.append(re.compile(custom_regex))
            except re.error as e:
                logger.warning("Failed to compile custom pattern %s: %s", custom_regex, e)

    def _get_active_patterns(self) -> dict[DangerousPattern, re.Pattern[str]]:
        """Get patterns that are active based on config.

        Returns:
            Dictionary of active patterns to their compiled regexes
        """
        active: dict[DangerousPattern, re.Pattern[str]] = {}

        if self.config.block_sql_ddl:
            for pattern in [
                DangerousPattern.SQL_DROP,
                DangerousPattern.SQL_DELETE,
                DangerousPattern.SQL_TRUNCATE,
                DangerousPattern.SQL_ALTER,
                DangerousPattern.SQL_UNION,
            ]:
                if pattern in self._compiled_patterns:
                    active[pattern] = self._compiled_patterns[pattern]

        if self.config.block_shell_dangerous:
            for pattern in [
                DangerousPattern.SHELL_RM_RF,
                DangerousPattern.SHELL_SUDO,
                DangerousPattern.SHELL_CHMOD,
                DangerousPattern.SHELL_CHOWN,
            ]:
                if pattern in self._compiled_patterns:
                    active[pattern] = self._compiled_patterns[pattern]

        if self.config.block_prompt_injection:
            for pattern in [
                DangerousPattern.PROMPT_IGNORE,
                DangerousPattern.PROMPT_SYSTEM,
                DangerousPattern.PROMPT_OVERRIDE,
                DangerousPattern.PROMPT_JAILBREAK,
            ]:
                if pattern in self._compiled_patterns:
                    active[pattern] = self._compiled_patterns[pattern]

        if self.config.block_file_sensitive:
            for pattern in [
                DangerousPattern.FILE_ETC_PASSWD,
                DangerousPattern.FILE_ETC_SHADOW,
                DangerousPattern.FILE_SSH_KEY,
                DangerousPattern.FILE_PATH_TRAVERSAL,
            ]:
                if pattern in self._compiled_patterns:
                    active[pattern] = self._compiled_patterns[pattern]

        return active

    def _detect_patterns(self, content: str) -> list[DangerousPattern]:
        """Detect dangerous patterns in content.

        Args:
            content: Content to analyze

        Returns:
            List of detected dangerous patterns
        """
        detected: list[DangerousPattern] = []
        active_patterns = self._get_active_patterns()

        for pattern, regex in active_patterns.items():
            if regex.search(content):
                detected.append(pattern)

        # Check custom patterns
        for custom_regex in self._compiled_custom:
            if custom_regex.search(content):
                detected.append(DangerousPattern.CUSTOM)
                break  # Only add CUSTOM once

        return detected

    def validate_input(
        self,
        content: str | None,
        sanitize: bool = False,
    ) -> ValidationResult:
        """Validate input content for dangerous patterns.

        Args:
            content: Content to validate
            sanitize: Whether to include sanitized content in result

        Returns:
            ValidationResult indicating whether content is safe
        """
        # Handle None/empty input
        if content is None or content == "":
            return ValidationResult(
                is_valid=True,
                blocked_patterns=[],
                original_content=content or "",
            )

        # If shields are disabled, allow everything
        if not self.config.enabled:
            return ValidationResult(
                is_valid=True,
                blocked_patterns=[],
                original_content=content,
            )

        # Detect dangerous patterns
        detected = self._detect_patterns(content)

        if detected:
            pattern_names = [p.value for p in detected]
            error_msg = f"Dangerous patterns detected: {', '.join(pattern_names)}"
            logger.warning("Content blocked: %s in input: %s...", pattern_names, content[:50])

            result = ValidationResult(
                is_valid=False,
                blocked_patterns=detected,
                error_message=error_msg,
                original_content=content,
            )

            if sanitize:
                result.sanitized_content = self.sanitize(content)

            return result

        return ValidationResult(
            is_valid=True,
            blocked_patterns=[],
            original_content=content,
            sanitized_content=content if sanitize else None,
        )

    def validate_output(self, content: str) -> ValidationResult:
        """Validate output content for prompt injection attempts.

        This method specifically checks for prompt injection patterns
        that might be embedded in tool outputs.

        Args:
            content: Content to validate

        Returns:
            ValidationResult indicating whether content is safe
        """
        # Use the same validation logic but focus on prompt injection
        return self.validate_input(content)

    def sanitize(self, content: str) -> str:
        """Remove dangerous patterns from content.

        Args:
            content: Content to sanitize

        Returns:
            Sanitized content with dangerous patterns removed
        """
        sanitized = content
        active_patterns = self._get_active_patterns()

        for pattern, regex in active_patterns.items():
            # Replace matches with [BLOCKED: pattern_name]
            sanitized = regex.sub(f"[BLOCKED:{pattern.value}]", sanitized)

        # Handle custom patterns
        for custom_regex in self._compiled_custom:
            sanitized = custom_regex.sub("[BLOCKED:CUSTOM]", sanitized)

        return sanitized

    def validate_json(
        self,
        data: dict[str, Any],
        schema: dict[str, Any],
    ) -> ValidationResult:
        """Validate data against a JSON schema.

        Args:
            data: Data to validate
            schema: JSON schema to validate against

        Returns:
            ValidationResult indicating whether data matches schema
        """
        try:
            # Import jsonschema for validation
            import jsonschema

            jsonschema.validate(instance=data, schema=schema)
            return ValidationResult(
                is_valid=True,
                blocked_patterns=[],
            )

        except ImportError:
            # Fallback to basic validation if jsonschema not available
            return self._basic_schema_validation(data, schema)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                blocked_patterns=[],
                error_message=str(e),
            )

    def _basic_schema_validation(
        self,
        data: dict[str, Any],
        schema: dict[str, Any],
    ) -> ValidationResult:
        """Basic JSON schema validation without jsonschema library.

        Args:
            data: Data to validate
            schema: JSON schema

        Returns:
            ValidationResult
        """
        # Check required fields
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                return ValidationResult(
                    is_valid=False,
                    blocked_patterns=[],
                    error_message=f"Missing required field: {field}",
                )

        # Check property types
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in data:
                expected_type = field_schema.get("type")
                if expected_type:
                    if not self._check_type(data[field], expected_type):
                        return ValidationResult(
                            is_valid=False,
                            blocked_patterns=[],
                            error_message=f"Invalid type for {field}: expected {expected_type}",
                        )

                # Check minimum/maximum for integers
                if expected_type == "integer":
                    min_val = field_schema.get("minimum")
                    max_val = field_schema.get("maximum")
                    if min_val is not None and data[field] < min_val:
                        return ValidationResult(
                            is_valid=False,
                            blocked_patterns=[],
                            error_message=f"Value {data[field]} is below minimum {min_val}",
                        )
                    if max_val is not None and data[field] > max_val:
                        return ValidationResult(
                            is_valid=False,
                            blocked_patterns=[],
                            error_message=f"Value {data[field]} exceeds maximum {max_val}",
                        )

                # Recursively validate nested objects
                if expected_type == "object" and isinstance(data[field], dict):
                    nested_result = self._basic_schema_validation(
                        data[field], field_schema
                    )
                    if not nested_result.is_valid:
                        return nested_result

        return ValidationResult(
            is_valid=True,
            blocked_patterns=[],
        )

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if a value matches an expected JSON schema type.

        Args:
            value: Value to check
            expected_type: Expected type name

        Returns:
            True if value matches type
        """
        type_mapping: dict[str, type | tuple[type, ...]] = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list,
            "null": type(None),
        }

        python_type = type_mapping.get(expected_type)
        if python_type is None:
            return True  # Unknown type, allow

        return isinstance(value, python_type)

    def validate_tool_call(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> ValidationResult:
        """Validate tool call parameters.

        Args:
            tool_name: Name of the tool being called
            params: Parameters for the tool call

        Returns:
            ValidationResult indicating whether params are safe
        """
        # Check each parameter value
        detected: list[DangerousPattern] = []

        for _key, value in params.items():
            if isinstance(value, str):
                result = self.validate_input(value)
                if not result.is_valid:
                    detected.extend(result.blocked_patterns)

        if detected:
            pattern_names = [p.value for p in detected]
            error_msg = f"Dangerous patterns in tool params: {', '.join(pattern_names)}"
            logger.warning(
                "Tool call blocked: %s with dangerous params: %s",
                tool_name,
                pattern_names,
            )

            return ValidationResult(
                is_valid=False,
                blocked_patterns=list(set(detected)),  # Deduplicate
                error_message=error_msg,
            )

        return ValidationResult(
            is_valid=True,
            blocked_patterns=[],
        )

    def validate_tool_result(
        self,
        result: dict[str, Any] | str,
    ) -> ValidationResult:
        """Validate tool execution result.

        Args:
            result: Result from tool execution

        Returns:
            ValidationResult indicating whether result is safe
        """
        # Extract content from result
        if isinstance(result, dict):
            content = str(result.get("content", ""))
        else:
            content = str(result)

        return self.validate_output(content)


# -----------------------------------------------------------------------------
# Shielded Gateway
# -----------------------------------------------------------------------------


class ShieldedGateway:
    """MCP Gateway wrapped with content shields.

    This class combines the MCP Gateway authorization with content shields
    to provide comprehensive protection for tool calls.

    Attributes:
        gateway: The underlying MCP Gateway
        shield: Content shield for validation

    Example:
        shielded = ShieldedGateway(
            gateway_config=MCPGatewayConfig(...),
            shield_config=ShieldConfig.strict(),
        )

        # All tool calls are automatically validated
        result = await shielded.validate_and_call(token, "query_db", params)
    """

    def __init__(
        self,
        gateway_config: Any,  # MCPGatewayConfig
        shield_config: ShieldConfig | None = None,
    ) -> None:
        """Initialize the shielded gateway.

        Args:
            gateway_config: Configuration for the MCP Gateway
            shield_config: Configuration for content shields
        """
        from daw_agents.mcp.gateway import MCPGateway

        self.gateway = MCPGateway(config=gateway_config)
        self.shield = ContentShield(config=shield_config or ShieldConfig.strict())
