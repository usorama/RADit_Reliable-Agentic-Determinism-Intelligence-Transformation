"""E2B Sandbox Wrapper for secure code execution.

This module provides a wrapper around the E2B SDK for executing code
in secure, isolated cloud sandboxes. It enforces strict timeout,
resource limits, and network allowlist capabilities.

Key Features:
- Sandbox initialization with API key
- Command execution with output capture
- File operations (write/read)
- Timeout handling
- Sandbox lifecycle management (create/kill)
- Graceful error handling and cleanup
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from e2b import AsyncSandbox  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class SandboxError(Exception):
    """Base exception for sandbox-related errors."""


class SandboxNotStartedError(SandboxError):
    """Raised when trying to use a sandbox that hasn't been started."""


class SandboxTimeoutError(SandboxError):
    """Raised when a sandbox operation times out."""


# -----------------------------------------------------------------------------
# Configuration Models
# -----------------------------------------------------------------------------


class SandboxConfig(BaseModel):
    """Configuration for E2B sandbox.

    Attributes:
        api_key: E2B API key for authentication.
        timeout: Sandbox timeout in seconds (default 300s, max 86400s for Pro).
        template: Sandbox template name or ID (default "base").
        cpu_limit: CPU limit (number of cores).
        memory_limit_mb: Memory limit in megabytes.
        network_allowlist: List of allowed network domains.
    """

    api_key: str = Field(..., description="E2B API key for authentication")
    timeout: int = Field(default=300, ge=1, le=86400, description="Sandbox timeout in seconds")
    template: str = Field(default="base", description="Sandbox template name")
    cpu_limit: int | None = Field(default=None, description="CPU core limit")
    memory_limit_mb: int | None = Field(default=None, description="Memory limit in MB")
    network_allowlist: list[str] = Field(
        default_factory=list, description="Allowed network domains"
    )


class CommandResult(BaseModel):
    """Result of a command execution in the sandbox.

    Attributes:
        stdout: Standard output from the command.
        stderr: Standard error from the command.
        exit_code: Exit code of the command (None if command didn't complete).
        error: Error message if the command failed to execute.
    """

    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    exit_code: int | None = Field(default=None, description="Exit code")
    error: str | None = Field(default=None, description="Execution error message")

    @property
    def success(self) -> bool:
        """Check if the command executed successfully."""
        return self.error is None and self.exit_code == 0


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def load_api_key_from_file(file_path: str | Path) -> str:
    """Load E2B API key from a file.

    Args:
        file_path: Path to the file containing the API key.

    Returns:
        The API key string with whitespace stripped.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    path = Path(file_path)
    return path.read_text().strip()


# -----------------------------------------------------------------------------
# E2B Sandbox Wrapper
# -----------------------------------------------------------------------------


class E2BSandbox:
    """Wrapper for E2B sandbox providing secure code execution.

    This class wraps the E2B SDK to provide a simplified interface for:
    - Creating and managing sandbox instances
    - Executing commands with timeout handling
    - File operations
    - Automatic cleanup on completion or error

    Usage:
        ```python
        config = SandboxConfig(api_key="your_key")
        async with E2BSandbox(config=config) as sandbox:
            result = await sandbox.run_command("echo 'Hello, World!'")
            print(result.stdout)
        ```
    """

    def __init__(self, config: SandboxConfig) -> None:
        """Initialize the E2B sandbox wrapper.

        Args:
            config: SandboxConfig with API key and options.
        """
        self.config = config
        self._sandbox: AsyncSandbox | None = None

    @classmethod
    def from_env(cls) -> E2BSandbox:
        """Create an E2BSandbox using API key from environment.

        Returns:
            E2BSandbox instance configured from E2B_API_KEY env var.

        Raises:
            ValueError: If E2B_API_KEY is not set.
        """
        api_key = os.environ.get("E2B_API_KEY")
        if not api_key:
            raise ValueError("E2B_API_KEY environment variable is not set")
        config = SandboxConfig(api_key=api_key)
        return cls(config=config)

    @property
    def sandbox_id(self) -> str | None:
        """Get the sandbox ID if running."""
        if self._sandbox is None:
            return None
        sandbox_id: str = self._sandbox.sandbox_id
        return sandbox_id

    @property
    def is_running(self) -> bool:
        """Check if the sandbox is currently running."""
        if self._sandbox is None:
            return False
        running: bool = self._sandbox.is_running()
        return running

    async def start(self) -> None:
        """Start a new sandbox instance.

        Creates a new E2B sandbox using the configured template and timeout.
        """
        from e2b import AsyncSandbox

        logger.info(
            "Starting E2B sandbox",
            extra={
                "template": self.config.template,
                "timeout": self.config.timeout,
            },
        )

        self._sandbox = await AsyncSandbox.create(
            template=self.config.template,
            timeout=self.config.timeout,
            api_key=self.config.api_key,
        )

        logger.info(
            "E2B sandbox started",
            extra={"sandbox_id": self._sandbox.sandbox_id},
        )

    async def stop(self) -> bool:
        """Stop and terminate the sandbox.

        Returns:
            True if the sandbox was killed, False if not found.
        """
        if self._sandbox is None:
            return False

        logger.info(
            "Stopping E2B sandbox",
            extra={"sandbox_id": self._sandbox.sandbox_id},
        )

        killed: bool = await self._sandbox.kill()

        logger.info("E2B sandbox stopped")
        return killed

    def _ensure_started(self) -> None:
        """Ensure the sandbox has been started.

        Raises:
            SandboxNotStartedError: If the sandbox hasn't been started.
        """
        if self._sandbox is None:
            raise SandboxNotStartedError(
                "Sandbox has not been started. Call start() or use as context manager."
            )

    async def run_command(
        self,
        cmd: str,
        *,
        timeout: float = 60,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> CommandResult:
        """Execute a command in the sandbox.

        Args:
            cmd: The command to execute.
            timeout: Command timeout in seconds (default 60).
            envs: Environment variables for the command.
            cwd: Working directory for the command.

        Returns:
            CommandResult with stdout, stderr, exit_code, and error.
        """
        self._ensure_started()
        assert self._sandbox is not None  # Type narrowing for mypy

        try:
            result = await self._sandbox.commands.run(
                cmd,
                timeout=timeout,
                envs=envs,
                cwd=cwd,
            )

            return CommandResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                error=None,
            )

        except TimeoutError as e:
            logger.warning(
                "Command timed out",
                extra={"cmd": cmd, "timeout": timeout},
            )
            return CommandResult(
                stdout="",
                stderr="",
                exit_code=None,
                error=f"Command timed out: {e}",
            )

        except ConnectionError as e:
            logger.error(
                "Connection error during command execution",
                extra={"cmd": cmd, "error": str(e)},
            )
            return CommandResult(
                stdout="",
                stderr="",
                exit_code=None,
                error=f"Connection error: Sandbox disconnected - {e}",
            )

        except Exception as e:
            logger.error(
                "Unexpected error during command execution",
                extra={"cmd": cmd, "error": str(e)},
            )
            return CommandResult(
                stdout="",
                stderr="",
                exit_code=None,
                error=f"Execution error: {e}",
            )

    async def write_file(self, path: str, content: str | bytes) -> None:
        """Write content to a file in the sandbox.

        Args:
            path: Path to the file in the sandbox.
            content: Content to write (string or bytes).
        """
        self._ensure_started()
        assert self._sandbox is not None

        logger.debug("Writing file to sandbox", extra={"path": path})
        await self._sandbox.files.write(path, content)

    async def read_file(self, path: str) -> str:
        """Read content from a file in the sandbox.

        Args:
            path: Path to the file in the sandbox.

        Returns:
            File content as a string.
        """
        self._ensure_started()
        assert self._sandbox is not None

        logger.debug("Reading file from sandbox", extra={"path": path})
        content: str = await self._sandbox.files.read(path)
        return content

    # -------------------------------------------------------------------------
    # Async Context Manager
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> E2BSandbox:
        """Enter the async context manager."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the async context manager, ensuring cleanup."""
        await self.stop()
