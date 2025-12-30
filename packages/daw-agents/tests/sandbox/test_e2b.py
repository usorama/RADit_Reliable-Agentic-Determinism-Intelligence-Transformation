"""Comprehensive tests for E2B Sandbox Wrapper.

This module tests the E2B sandbox wrapper implementation for secure
code execution in isolated cloud environments.

Tests cover:
1. Sandbox initialization with API key
2. Command execution with output capture
3. File operations (write/read)
4. Timeout handling
5. Resource limits configuration
6. Error handling for failed commands
7. Sandbox lifecycle management (create/kill)
8. Network allowlist capabilities
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# -----------------------------------------------------------------------------
# Test: SandboxConfig Model
# -----------------------------------------------------------------------------


class TestSandboxConfigModel:
    """Tests for the SandboxConfig Pydantic model."""

    def test_sandbox_config_creation_minimal(self) -> None:
        """SandboxConfig should be creatable with just API key."""
        from daw_agents.sandbox.e2b import SandboxConfig

        config = SandboxConfig(api_key="test_api_key")

        assert config.api_key == "test_api_key"
        assert config.timeout == 300  # Default 5 minutes
        assert config.template == "base"  # Default template

    def test_sandbox_config_creation_full(self) -> None:
        """SandboxConfig should accept all configuration options."""
        from daw_agents.sandbox.e2b import SandboxConfig

        config = SandboxConfig(
            api_key="test_api_key",
            timeout=600,
            template="python-3.11",
            cpu_limit=2,
            memory_limit_mb=512,
            network_allowlist=["api.github.com", "pypi.org"],
        )

        assert config.api_key == "test_api_key"
        assert config.timeout == 600
        assert config.template == "python-3.11"
        assert config.cpu_limit == 2
        assert config.memory_limit_mb == 512
        assert "api.github.com" in config.network_allowlist

    def test_sandbox_config_validation_timeout(self) -> None:
        """SandboxConfig should validate timeout within limits."""
        from daw_agents.sandbox.e2b import SandboxConfig

        # Valid timeout
        config = SandboxConfig(api_key="test", timeout=3600)
        assert config.timeout == 3600

        # Max timeout for hobby users is 3600
        config_max = SandboxConfig(api_key="test", timeout=86400)
        assert config_max.timeout == 86400  # Pro users can have 24h


# -----------------------------------------------------------------------------
# Test: CommandResult Model
# -----------------------------------------------------------------------------


class TestCommandResultModel:
    """Tests for the CommandResult Pydantic model."""

    def test_command_result_success(self) -> None:
        """CommandResult should represent successful command execution."""
        from daw_agents.sandbox.e2b import CommandResult

        result = CommandResult(
            stdout="Hello, World!",
            stderr="",
            exit_code=0,
            error=None,
        )

        assert result.stdout == "Hello, World!"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.error is None
        assert result.success is True

    def test_command_result_failure(self) -> None:
        """CommandResult should represent failed command execution."""
        from daw_agents.sandbox.e2b import CommandResult

        result = CommandResult(
            stdout="",
            stderr="command not found: invalid_cmd",
            exit_code=127,
            error=None,
        )

        assert result.exit_code == 127
        assert "command not found" in result.stderr
        assert result.success is False

    def test_command_result_with_error(self) -> None:
        """CommandResult should handle execution errors."""
        from daw_agents.sandbox.e2b import CommandResult

        result = CommandResult(
            stdout="",
            stderr="",
            exit_code=None,
            error="Timeout exceeded",
        )

        assert result.error == "Timeout exceeded"
        assert result.success is False


# -----------------------------------------------------------------------------
# Test: E2BSandbox Initialization
# -----------------------------------------------------------------------------


class TestE2BSandboxInitialization:
    """Tests for E2BSandbox initialization."""

    def test_sandbox_initialization_with_api_key(self) -> None:
        """E2BSandbox should initialize with API key."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="e2b_test_key")
        sandbox = E2BSandbox(config=config)

        assert sandbox.config.api_key == "e2b_test_key"
        assert sandbox._sandbox is None  # Not started yet

    def test_sandbox_initialization_with_env_key(self) -> None:
        """E2BSandbox should use E2B_API_KEY from environment."""
        from daw_agents.sandbox.e2b import E2BSandbox

        with patch.dict("os.environ", {"E2B_API_KEY": "env_test_key"}):
            sandbox = E2BSandbox.from_env()

        assert sandbox.config.api_key == "env_test_key"

    def test_sandbox_initialization_with_custom_timeout(self) -> None:
        """E2BSandbox should accept custom timeout configuration."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key", timeout=600)
        sandbox = E2BSandbox(config=config)

        assert sandbox.config.timeout == 600


# -----------------------------------------------------------------------------
# Test: Sandbox Lifecycle
# -----------------------------------------------------------------------------


class TestSandboxLifecycle:
    """Tests for sandbox lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_sandbox(self) -> None:
        """start() should create a new E2B sandbox."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        # Mock the E2B SDK - patch the module import location
        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.sandbox_id = "sbx_test_123"
        mock_e2b_sandbox.is_running.return_value = True

        mock_async_sandbox = MagicMock()
        mock_async_sandbox.create = AsyncMock(return_value=mock_e2b_sandbox)

        with patch("e2b.AsyncSandbox", mock_async_sandbox):
            await sandbox.start()

            assert sandbox._sandbox is not None
            assert sandbox.sandbox_id == "sbx_test_123"
            assert sandbox.is_running is True

    @pytest.mark.asyncio
    async def test_stop_sandbox(self) -> None:
        """stop() should terminate the sandbox."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.kill = AsyncMock(return_value=True)

        sandbox._sandbox = mock_e2b_sandbox

        result = await sandbox.stop()

        assert result is True
        mock_e2b_sandbox.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_support(self) -> None:
        """E2BSandbox should support async context manager protocol."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.sandbox_id = "sbx_context_123"
        mock_e2b_sandbox.kill = AsyncMock(return_value=True)

        mock_async_sandbox = MagicMock()
        mock_async_sandbox.create = AsyncMock(return_value=mock_e2b_sandbox)

        with patch("e2b.AsyncSandbox", mock_async_sandbox):
            async with E2BSandbox(config=config) as sandbox:
                assert sandbox.sandbox_id == "sbx_context_123"

            # After exiting, sandbox should be stopped
            mock_e2b_sandbox.kill.assert_called_once()


# -----------------------------------------------------------------------------
# Test: Command Execution
# -----------------------------------------------------------------------------


class TestCommandExecution:
    """Tests for command execution in sandbox."""

    @pytest.mark.asyncio
    async def test_run_command_success(self) -> None:
        """run_command should execute command and return result."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        # Mock E2B sandbox and commands module
        mock_commands = MagicMock()
        mock_command_result = MagicMock()
        mock_command_result.stdout = "Hello, World!"
        mock_command_result.stderr = ""
        mock_command_result.exit_code = 0
        mock_commands.run = AsyncMock(return_value=mock_command_result)

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.commands = mock_commands
        sandbox._sandbox = mock_e2b_sandbox

        result = await sandbox.run_command("echo 'Hello, World!'")

        assert result.stdout == "Hello, World!"
        assert result.exit_code == 0
        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_command_with_timeout(self) -> None:
        """run_command should respect timeout parameter."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        mock_commands = MagicMock()
        mock_command_result = MagicMock()
        mock_command_result.stdout = "done"
        mock_command_result.stderr = ""
        mock_command_result.exit_code = 0
        mock_commands.run = AsyncMock(return_value=mock_command_result)

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.commands = mock_commands
        sandbox._sandbox = mock_e2b_sandbox

        await sandbox.run_command("sleep 5 && echo done", timeout=30)

        # Verify timeout was passed
        mock_commands.run.assert_called_once()
        call_kwargs = mock_commands.run.call_args[1]
        assert call_kwargs.get("timeout") == 30

    @pytest.mark.asyncio
    async def test_run_command_with_env_vars(self) -> None:
        """run_command should support environment variables."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        mock_commands = MagicMock()
        mock_command_result = MagicMock()
        mock_command_result.stdout = "test_value"
        mock_command_result.stderr = ""
        mock_command_result.exit_code = 0
        mock_commands.run = AsyncMock(return_value=mock_command_result)

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.commands = mock_commands
        sandbox._sandbox = mock_e2b_sandbox

        await sandbox.run_command(
            "echo $MY_VAR",
            envs={"MY_VAR": "test_value"},
        )

        call_kwargs = mock_commands.run.call_args[1]
        assert call_kwargs.get("envs") == {"MY_VAR": "test_value"}

    @pytest.mark.asyncio
    async def test_run_command_with_working_directory(self) -> None:
        """run_command should support working directory."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        mock_commands = MagicMock()
        mock_command_result = MagicMock()
        mock_command_result.stdout = "/app"
        mock_command_result.stderr = ""
        mock_command_result.exit_code = 0
        mock_commands.run = AsyncMock(return_value=mock_command_result)

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.commands = mock_commands
        sandbox._sandbox = mock_e2b_sandbox

        await sandbox.run_command("pwd", cwd="/app")

        call_kwargs = mock_commands.run.call_args[1]
        assert call_kwargs.get("cwd") == "/app"

    @pytest.mark.asyncio
    async def test_run_command_failure(self) -> None:
        """run_command should handle non-zero exit codes."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        mock_commands = MagicMock()
        mock_command_result = MagicMock()
        mock_command_result.stdout = ""
        mock_command_result.stderr = "command not found: invalid_cmd"
        mock_command_result.exit_code = 127
        mock_commands.run = AsyncMock(return_value=mock_command_result)

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.commands = mock_commands
        sandbox._sandbox = mock_e2b_sandbox

        result = await sandbox.run_command("invalid_cmd")

        assert result.success is False
        assert result.exit_code == 127
        assert "command not found" in result.stderr

    @pytest.mark.asyncio
    async def test_run_command_not_started(self) -> None:
        """run_command should raise error if sandbox not started."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig, SandboxNotStartedError

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        with pytest.raises(SandboxNotStartedError):
            await sandbox.run_command("echo hello")


# -----------------------------------------------------------------------------
# Test: File Operations
# -----------------------------------------------------------------------------


class TestFileOperations:
    """Tests for file operations in sandbox."""

    @pytest.mark.asyncio
    async def test_write_file(self) -> None:
        """write_file should write content to sandbox filesystem."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        mock_files = MagicMock()
        mock_files.write = AsyncMock()

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.files = mock_files
        sandbox._sandbox = mock_e2b_sandbox

        await sandbox.write_file("/app/test.py", "print('hello')")

        mock_files.write.assert_called_once_with("/app/test.py", "print('hello')")

    @pytest.mark.asyncio
    async def test_read_file(self) -> None:
        """read_file should read content from sandbox filesystem."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        mock_files = MagicMock()
        mock_files.read = AsyncMock(return_value="print('hello')")

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.files = mock_files
        sandbox._sandbox = mock_e2b_sandbox

        content = await sandbox.read_file("/app/test.py")

        assert content == "print('hello')"
        mock_files.read.assert_called_once_with("/app/test.py")

    @pytest.mark.asyncio
    async def test_write_file_not_started(self) -> None:
        """write_file should raise error if sandbox not started."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig, SandboxNotStartedError

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        with pytest.raises(SandboxNotStartedError):
            await sandbox.write_file("/test.txt", "content")

    @pytest.mark.asyncio
    async def test_read_file_not_started(self) -> None:
        """read_file should raise error if sandbox not started."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig, SandboxNotStartedError

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        with pytest.raises(SandboxNotStartedError):
            await sandbox.read_file("/test.txt")


# -----------------------------------------------------------------------------
# Test: Error Handling
# -----------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling in sandbox operations."""

    @pytest.mark.asyncio
    async def test_handle_timeout_error(self) -> None:
        """Sandbox should handle command timeout gracefully."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        mock_commands = MagicMock()
        mock_commands.run = AsyncMock(side_effect=TimeoutError("Command timed out"))

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.commands = mock_commands
        sandbox._sandbox = mock_e2b_sandbox

        result = await sandbox.run_command("sleep 100", timeout=1)

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handle_connection_error(self) -> None:
        """Sandbox should handle connection errors gracefully."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        mock_commands = MagicMock()
        mock_commands.run = AsyncMock(side_effect=ConnectionError("Sandbox disconnected"))

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.commands = mock_commands
        sandbox._sandbox = mock_e2b_sandbox

        result = await sandbox.run_command("echo hello")

        assert result.success is False
        assert "disconnected" in result.error.lower()


# -----------------------------------------------------------------------------
# Test: Sandbox Cleanup
# -----------------------------------------------------------------------------


class TestSandboxCleanup:
    """Tests for proper sandbox cleanup on completion/error."""

    @pytest.mark.asyncio
    async def test_cleanup_on_context_exit(self) -> None:
        """Sandbox should be killed when context manager exits."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.sandbox_id = "sbx_cleanup_123"
        mock_e2b_sandbox.kill = AsyncMock(return_value=True)

        mock_async_sandbox = MagicMock()
        mock_async_sandbox.create = AsyncMock(return_value=mock_e2b_sandbox)

        with patch("e2b.AsyncSandbox", mock_async_sandbox):
            async with E2BSandbox(config=config):
                pass

        mock_e2b_sandbox.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_on_exception(self) -> None:
        """Sandbox should be killed even when exception occurs."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")

        mock_e2b_sandbox = MagicMock()
        mock_e2b_sandbox.sandbox_id = "sbx_exception_123"
        mock_e2b_sandbox.kill = AsyncMock(return_value=True)

        mock_async_sandbox = MagicMock()
        mock_async_sandbox.create = AsyncMock(return_value=mock_e2b_sandbox)

        with patch("e2b.AsyncSandbox", mock_async_sandbox):
            with pytest.raises(RuntimeError, match="Test exception"):
                async with E2BSandbox(config=config):
                    raise RuntimeError("Test exception")

        # Sandbox should still be killed
        mock_e2b_sandbox.kill.assert_called_once()


# -----------------------------------------------------------------------------
# Test: Utility Methods
# -----------------------------------------------------------------------------


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_load_api_key_from_file(self) -> None:
        """Should be able to load API key from file."""
        from daw_agents.sandbox.e2b import load_api_key_from_file

        with patch("pathlib.Path.read_text", return_value="e2b_test_key_from_file\n"):
            key = load_api_key_from_file("/path/to/key.txt")

        assert key == "e2b_test_key_from_file"

    def test_validate_sandbox_running(self) -> None:
        """is_running should return correct status."""
        from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig

        config = SandboxConfig(api_key="test_key")
        sandbox = E2BSandbox(config=config)

        # Not started
        assert sandbox.is_running is False

        # Started
        mock_e2b = MagicMock()
        mock_e2b.is_running.return_value = True
        sandbox._sandbox = mock_e2b

        assert sandbox.is_running is True
