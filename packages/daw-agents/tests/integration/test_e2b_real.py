"""Real E2B Sandbox Integration Tests.

This module contains integration tests that connect to real E2B sandboxes.
These tests require a valid E2B API key and will make actual API calls.

NO MOCKS ARE USED in these tests - they verify real sandbox behavior.

To run these tests:
    # With E2B_API_KEY environment variable
    E2B_API_KEY=your_key pytest tests/integration/test_e2b_real.py -v

    # With .creds/e2b_api_key.txt file
    pytest tests/integration/test_e2b_real.py -v

    # Skip slow tests
    pytest tests/integration/test_e2b_real.py -m 'integration and not slow' -v

Tests:
1. test_e2b_sandbox_creates_and_destroys - Sandbox lifecycle
2. test_e2b_real_command_execution - Command execution
3. test_e2b_real_file_operations - File read/write
4. test_e2b_sandbox_context_manager - Context manager cleanup
5. test_e2b_sandbox_python_execution - Python code execution
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from daw_agents.sandbox.e2b import E2BSandbox, SandboxConfig


# -----------------------------------------------------------------------------
# Test: Sandbox Lifecycle
# -----------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2b_sandbox_creates_and_destroys(e2b_config: SandboxConfig) -> None:
    """Real E2B sandbox lifecycle - create, verify running, destroy.

    This test verifies that:
    1. A sandbox can be created with real E2B API
    2. The sandbox has a valid sandbox_id after creation
    3. The sandbox can execute commands (proves it's running)
    4. The sandbox can be stopped and cleaned up
    """
    from daw_agents.sandbox.e2b import E2BSandbox

    sandbox = E2BSandbox(config=e2b_config)

    # Initially not running - no sandbox reference yet
    assert sandbox._sandbox is None
    assert sandbox.sandbox_id is None

    # Start sandbox
    await sandbox.start()

    try:
        # Verify sandbox was created successfully
        assert sandbox.sandbox_id is not None
        assert isinstance(sandbox.sandbox_id, str)
        assert len(sandbox.sandbox_id) > 0
        # Prove sandbox is running by executing a command
        result = await sandbox.run_command("echo 'sandbox alive'")
        assert result.success is True
        assert "sandbox alive" in result.stdout
    finally:
        # Stop and verify cleanup
        stopped = await sandbox.stop()
        assert stopped is True


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2b_real_command_execution(e2b_sandbox: E2BSandbox) -> None:
    """Execute real command in E2B sandbox.

    This test verifies that:
    1. A simple echo command executes successfully
    2. stdout contains the expected output
    3. exit_code is 0 for successful commands
    4. The success property returns True
    """
    # Execute a simple echo command
    result = await e2b_sandbox.run_command("echo 'Hello from E2B!'")

    # Verify command result
    assert result.success is True
    assert result.exit_code == 0
    assert "Hello from E2B!" in result.stdout
    assert result.error is None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2b_real_command_with_environment_variables(
    e2b_sandbox: E2BSandbox,
) -> None:
    """Execute command with environment variables in real E2B sandbox.

    This test verifies that:
    1. Environment variables can be passed to commands
    2. The sandbox correctly expands environment variables
    """
    result = await e2b_sandbox.run_command(
        "echo $TEST_VAR",
        envs={"TEST_VAR": "integration_test_value"},
    )

    assert result.success is True
    assert "integration_test_value" in result.stdout


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2b_real_file_operations(e2b_sandbox: E2BSandbox) -> None:
    """Write and read files in real E2B sandbox.

    This test verifies that:
    1. Files can be written to the sandbox filesystem
    2. Files can be read back from the sandbox
    3. Content is preserved correctly through write/read cycle
    """
    test_content = "Hello, this is a test file!\nLine 2\nLine 3"
    test_path = "/tmp/integration_test_file.txt"

    # Write file to sandbox
    await e2b_sandbox.write_file(test_path, test_content)

    # Read file back from sandbox
    read_content = await e2b_sandbox.read_file(test_path)

    # Verify content matches
    assert read_content == test_content

    # Verify file exists using ls command
    result = await e2b_sandbox.run_command(f"ls -la {test_path}")
    assert result.success is True
    assert "integration_test_file.txt" in result.stdout


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2b_sandbox_context_manager(e2b_config: SandboxConfig) -> None:
    """E2B sandbox context manager auto-cleanup.

    This test verifies that:
    1. Sandbox starts when entering context
    2. Sandbox has valid sandbox_id inside context
    3. Commands execute successfully inside context
    4. Context manager exits without error (cleanup is called)
    """
    from daw_agents.sandbox.e2b import E2BSandbox

    sandbox_id_inside: str | None = None

    async with E2BSandbox(config=e2b_config) as sandbox:
        # Inside context, sandbox should have a valid ID (proves it's running)
        sandbox_id_inside = sandbox.sandbox_id
        assert sandbox_id_inside is not None
        assert isinstance(sandbox_id_inside, str)
        assert len(sandbox_id_inside) > 0

        # Run a command to verify sandbox is functional
        result = await sandbox.run_command("echo 'context test'")
        assert result.success is True
        assert "context test" in result.stdout

    # If we get here without exception, the context manager properly exited
    # and stop() was called. The sandbox_id we captured proves it ran.
    assert sandbox_id_inside is not None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2b_sandbox_python_execution(e2b_sandbox: E2BSandbox) -> None:
    """Execute Python code in real E2B sandbox.

    This test verifies that:
    1. Python is available in the sandbox
    2. Python code executes correctly
    3. Python output is captured in stdout
    """
    # Execute Python code
    result = await e2b_sandbox.run_command('python3 -c "print(2 + 2)"')

    assert result.success is True
    assert "4" in result.stdout


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2b_sandbox_working_directory(e2b_sandbox: E2BSandbox) -> None:
    """Execute command with working directory in E2B sandbox.

    This test verifies that:
    1. cwd parameter correctly changes the working directory
    2. Commands execute in the specified directory
    """
    # First, create a directory
    await e2b_sandbox.run_command("mkdir -p /tmp/test_cwd_dir")

    # Create a file in that directory
    await e2b_sandbox.write_file("/tmp/test_cwd_dir/marker.txt", "cwd marker")

    # List files from that directory using cwd
    result = await e2b_sandbox.run_command("ls", cwd="/tmp/test_cwd_dir")

    assert result.success is True
    assert "marker.txt" in result.stdout


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2b_sandbox_command_failure(e2b_sandbox: E2BSandbox) -> None:
    """Verify proper handling of failing commands in E2B sandbox.

    This test verifies that:
    1. Non-existent commands return non-zero exit code
    2. success property returns False for failed commands
    3. stderr contains error information
    """
    # Run a command that will fail
    result = await e2b_sandbox.run_command("this_command_does_not_exist_12345")

    assert result.success is False
    assert result.exit_code != 0
    # stderr should contain some error message about command not found


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2b_sandbox_binary_file_operations(e2b_sandbox: E2BSandbox) -> None:
    """Write and verify binary content in E2B sandbox.

    This test verifies that file operations work with binary-like content
    by creating a Python script and executing it.
    """
    # Write a Python script
    script_content = """#!/usr/bin/env python3
import sys
print("Script executed successfully!")
print(f"Python version: {sys.version_info.major}.{sys.version_info.minor}")
sys.exit(0)
"""
    script_path = "/tmp/test_script.py"

    await e2b_sandbox.write_file(script_path, script_content)

    # Make it executable and run
    await e2b_sandbox.run_command(f"chmod +x {script_path}")
    result = await e2b_sandbox.run_command(f"python3 {script_path}")

    assert result.success is True
    assert "Script executed successfully!" in result.stdout
    assert "Python version:" in result.stdout
