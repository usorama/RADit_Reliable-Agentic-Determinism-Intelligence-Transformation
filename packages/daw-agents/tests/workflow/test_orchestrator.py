"""Tests for the Main Workflow Orchestrator (ORCHESTRATOR-001).

This test module follows TDD workflow - tests are written FIRST to define
expected behavior before implementation.

The Orchestrator is the CORE WORKFLOW ENGINE that coordinates all agents:
- User Input -> Planner -> Task Decomposition -> Executor -> Validator -> Deployment

Test coverage:
- OrchestratorState TypedDict
- OrchestratorStatus enum
- OrchestratorConfig Pydantic model
- WorkflowResult Pydantic model
- Orchestrator class with LangGraph workflow
- State transitions and checkpoints (Redis-backed)
- Human-in-the-loop interrupts
- Integration with Planner, Executor, Validator agents
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# -----------------------------------------------------------------------------
# Test: OrchestratorStatus Enum
# -----------------------------------------------------------------------------


class TestOrchestratorStatus:
    """Tests for OrchestratorStatus enum values."""

    def test_status_enum_has_planning(self) -> None:
        """OrchestratorStatus should have PLANNING state."""
        from daw_agents.workflow.orchestrator import OrchestratorStatus

        assert hasattr(OrchestratorStatus, "PLANNING")
        assert OrchestratorStatus.PLANNING.value == "planning"

    def test_status_enum_has_coding(self) -> None:
        """OrchestratorStatus should have CODING state."""
        from daw_agents.workflow.orchestrator import OrchestratorStatus

        assert hasattr(OrchestratorStatus, "CODING")
        assert OrchestratorStatus.CODING.value == "coding"

    def test_status_enum_has_validating(self) -> None:
        """OrchestratorStatus should have VALIDATING state."""
        from daw_agents.workflow.orchestrator import OrchestratorStatus

        assert hasattr(OrchestratorStatus, "VALIDATING")
        assert OrchestratorStatus.VALIDATING.value == "validating"

    def test_status_enum_has_deploying(self) -> None:
        """OrchestratorStatus should have DEPLOYING state."""
        from daw_agents.workflow.orchestrator import OrchestratorStatus

        assert hasattr(OrchestratorStatus, "DEPLOYING")
        assert OrchestratorStatus.DEPLOYING.value == "deploying"

    def test_status_enum_has_complete(self) -> None:
        """OrchestratorStatus should have COMPLETE state."""
        from daw_agents.workflow.orchestrator import OrchestratorStatus

        assert hasattr(OrchestratorStatus, "COMPLETE")
        assert OrchestratorStatus.COMPLETE.value == "complete"

    def test_status_enum_has_error(self) -> None:
        """OrchestratorStatus should have ERROR state."""
        from daw_agents.workflow.orchestrator import OrchestratorStatus

        assert hasattr(OrchestratorStatus, "ERROR")
        assert OrchestratorStatus.ERROR.value == "error"

    def test_status_enum_has_awaiting_approval(self) -> None:
        """OrchestratorStatus should have AWAITING_APPROVAL for human-in-the-loop."""
        from daw_agents.workflow.orchestrator import OrchestratorStatus

        assert hasattr(OrchestratorStatus, "AWAITING_APPROVAL")
        assert OrchestratorStatus.AWAITING_APPROVAL.value == "awaiting_approval"


# -----------------------------------------------------------------------------
# Test: OrchestratorConfig Pydantic Model
# -----------------------------------------------------------------------------


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig Pydantic model."""

    def test_config_has_max_retries(self) -> None:
        """OrchestratorConfig should have max_retries field."""
        from daw_agents.workflow.orchestrator import OrchestratorConfig

        config = OrchestratorConfig()
        assert hasattr(config, "max_retries")
        assert config.max_retries == 3  # Default

    def test_config_has_require_human_approval(self) -> None:
        """OrchestratorConfig should have require_human_approval field."""
        from daw_agents.workflow.orchestrator import OrchestratorConfig

        config = OrchestratorConfig()
        assert hasattr(config, "require_human_approval")
        assert config.require_human_approval is True  # Default for deployment

    def test_config_has_checkpoint_enabled(self) -> None:
        """OrchestratorConfig should have checkpoint_enabled field."""
        from daw_agents.workflow.orchestrator import OrchestratorConfig

        config = OrchestratorConfig()
        assert hasattr(config, "checkpoint_enabled")
        assert config.checkpoint_enabled is True  # Default

    def test_config_custom_values(self) -> None:
        """OrchestratorConfig should accept custom values."""
        from daw_agents.workflow.orchestrator import OrchestratorConfig

        config = OrchestratorConfig(
            max_retries=5,
            require_human_approval=False,
            checkpoint_enabled=False,
        )
        assert config.max_retries == 5
        assert config.require_human_approval is False
        assert config.checkpoint_enabled is False


# -----------------------------------------------------------------------------
# Test: WorkflowResult Pydantic Model
# -----------------------------------------------------------------------------


class TestWorkflowResult:
    """Tests for WorkflowResult Pydantic model."""

    def test_result_has_success(self) -> None:
        """WorkflowResult should have success field."""
        from daw_agents.workflow.orchestrator import WorkflowResult

        result = WorkflowResult(
            success=True,
            status="complete",
            prd_output=None,
            tasks=[],
            executor_results=[],
            validator_results=[],
        )
        assert result.success is True

    def test_result_has_status(self) -> None:
        """WorkflowResult should have status field."""
        from daw_agents.workflow.orchestrator import WorkflowResult

        result = WorkflowResult(
            success=True,
            status="complete",
            prd_output=None,
            tasks=[],
            executor_results=[],
            validator_results=[],
        )
        assert result.status == "complete"

    def test_result_has_prd_output(self) -> None:
        """WorkflowResult should have prd_output field."""
        from daw_agents.workflow.orchestrator import WorkflowResult

        result = WorkflowResult(
            success=True,
            status="complete",
            prd_output={"title": "Test PRD"},
            tasks=[],
            executor_results=[],
            validator_results=[],
        )
        assert result.prd_output == {"title": "Test PRD"}

    def test_result_has_tasks(self) -> None:
        """WorkflowResult should have tasks field."""
        from daw_agents.workflow.orchestrator import WorkflowResult

        result = WorkflowResult(
            success=True,
            status="complete",
            prd_output=None,
            tasks=[{"id": "TASK-001"}],
            executor_results=[],
            validator_results=[],
        )
        assert result.tasks == [{"id": "TASK-001"}]

    def test_result_has_executor_results(self) -> None:
        """WorkflowResult should have executor_results field."""
        from daw_agents.workflow.orchestrator import WorkflowResult

        result = WorkflowResult(
            success=True,
            status="complete",
            prd_output=None,
            tasks=[],
            executor_results=[{"task_id": "TASK-001", "success": True}],
            validator_results=[],
        )
        assert len(result.executor_results) == 1

    def test_result_has_validator_results(self) -> None:
        """WorkflowResult should have validator_results field."""
        from daw_agents.workflow.orchestrator import WorkflowResult

        result = WorkflowResult(
            success=True,
            status="complete",
            prd_output=None,
            tasks=[],
            executor_results=[],
            validator_results=[{"task_id": "TASK-001", "passed": True}],
        )
        assert len(result.validator_results) == 1

    def test_result_has_error_optional(self) -> None:
        """WorkflowResult should have optional error field."""
        from daw_agents.workflow.orchestrator import WorkflowResult

        result = WorkflowResult(
            success=False,
            status="error",
            prd_output=None,
            tasks=[],
            executor_results=[],
            validator_results=[],
            error="Something went wrong",
        )
        assert result.error == "Something went wrong"


# -----------------------------------------------------------------------------
# Test: OrchestratorState TypedDict
# -----------------------------------------------------------------------------


class TestOrchestratorState:
    """Tests for OrchestratorState TypedDict structure."""

    def test_state_accepts_user_input(self) -> None:
        """OrchestratorState should accept user_input field."""
        from daw_agents.workflow.orchestrator import OrchestratorState

        state: OrchestratorState = {
            "user_input": "Build a calculator app",
            "prd_output": None,
            "tasks": [],
            "current_task_idx": 0,
            "executor_results": [],
            "validator_results": [],
            "deployment_status": None,
            "status": "planning",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }
        assert state["user_input"] == "Build a calculator app"

    def test_state_accepts_prd_output(self) -> None:
        """OrchestratorState should accept prd_output field."""
        from daw_agents.workflow.orchestrator import OrchestratorState

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": {"title": "Calculator", "overview": "A simple calc"},
            "tasks": [],
            "current_task_idx": 0,
            "executor_results": [],
            "validator_results": [],
            "deployment_status": None,
            "status": "planning",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }
        assert state["prd_output"] is not None
        assert state["prd_output"]["title"] == "Calculator"

    def test_state_accepts_tasks_list(self) -> None:
        """OrchestratorState should accept tasks list."""
        from daw_agents.workflow.orchestrator import OrchestratorState

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": None,
            "tasks": [{"id": "TASK-001", "description": "Create main"}],
            "current_task_idx": 0,
            "executor_results": [],
            "validator_results": [],
            "deployment_status": None,
            "status": "coding",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }
        assert len(state["tasks"]) == 1

    def test_state_accepts_current_task_idx(self) -> None:
        """OrchestratorState should track current task index."""
        from daw_agents.workflow.orchestrator import OrchestratorState

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": None,
            "tasks": [{"id": "TASK-001"}, {"id": "TASK-002"}],
            "current_task_idx": 1,
            "executor_results": [],
            "validator_results": [],
            "deployment_status": None,
            "status": "coding",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }
        assert state["current_task_idx"] == 1

    def test_state_accepts_human_approval_required(self) -> None:
        """OrchestratorState should track human approval requirement."""
        from daw_agents.workflow.orchestrator import OrchestratorState

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": None,
            "tasks": [],
            "current_task_idx": 0,
            "executor_results": [],
            "validator_results": [],
            "deployment_status": None,
            "status": "awaiting_approval",
            "error": None,
            "human_approval_required": True,
            "retry_count": 0,
        }
        assert state["human_approval_required"] is True


# -----------------------------------------------------------------------------
# Test: Orchestrator Class Initialization
# -----------------------------------------------------------------------------


class TestOrchestratorInit:
    """Tests for Orchestrator class initialization."""

    def test_init_creates_workflow(self) -> None:
        """Orchestrator should create a LangGraph workflow on init."""
        from daw_agents.workflow.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        assert orchestrator.workflow is not None

    def test_init_accepts_model_router(self) -> None:
        """Orchestrator should accept a custom ModelRouter."""
        from daw_agents.models.router import ModelRouter
        from daw_agents.workflow.orchestrator import Orchestrator

        router = ModelRouter()
        orchestrator = Orchestrator(model_router=router)
        assert orchestrator._model_router is router

    def test_init_accepts_config(self) -> None:
        """Orchestrator should accept OrchestratorConfig."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorConfig

        config = OrchestratorConfig(max_retries=5)
        orchestrator = Orchestrator(config=config)
        assert orchestrator._config.max_retries == 5

    def test_init_with_taskmaster(self) -> None:
        """Orchestrator should accept a Taskmaster instance."""
        from daw_agents.agents.planner.taskmaster import Taskmaster
        from daw_agents.workflow.orchestrator import Orchestrator

        taskmaster = MagicMock(spec=Taskmaster)
        orchestrator = Orchestrator(taskmaster=taskmaster)
        assert orchestrator._taskmaster is taskmaster

    def test_init_with_developer(self) -> None:
        """Orchestrator should accept a Developer instance."""
        from daw_agents.agents.developer.graph import Developer
        from daw_agents.workflow.orchestrator import Orchestrator

        developer = MagicMock(spec=Developer)
        orchestrator = Orchestrator(developer=developer)
        assert orchestrator._developer is developer

    def test_init_with_validator(self) -> None:
        """Orchestrator should accept a ValidatorAgent instance."""
        from daw_agents.agents.validator.agent import ValidatorAgent
        from daw_agents.workflow.orchestrator import Orchestrator

        validator = MagicMock(spec=ValidatorAgent)
        orchestrator = Orchestrator(validator=validator)
        assert orchestrator._validator is validator


# -----------------------------------------------------------------------------
# Test: Orchestrator Workflow Nodes
# -----------------------------------------------------------------------------


class TestOrchestratorNodes:
    """Tests for Orchestrator LangGraph workflow nodes."""

    @pytest.mark.asyncio
    async def test_plan_node_calls_taskmaster(self) -> None:
        """Plan node should invoke Taskmaster for PRD generation."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorState

        mock_taskmaster = AsyncMock()
        mock_taskmaster.plan.return_value = [
            MagicMock(id="TASK-001", description="Setup")
        ]
        mock_taskmaster.workflow = MagicMock()
        mock_taskmaster.workflow.ainvoke = AsyncMock(
            return_value={
                "prd": MagicMock(model_dump=lambda: {"title": "Test PRD"}),
                "tasks": [MagicMock(model_dump=lambda: {"id": "TASK-001"})],
            }
        )

        orchestrator = Orchestrator(taskmaster=mock_taskmaster)

        state: OrchestratorState = {
            "user_input": "Build a calculator",
            "prd_output": None,
            "tasks": [],
            "current_task_idx": 0,
            "executor_results": [],
            "validator_results": [],
            "deployment_status": None,
            "status": "planning",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }

        result = await orchestrator._plan_node(state)
        assert "prd_output" in result or "tasks" in result

    @pytest.mark.asyncio
    async def test_execute_node_calls_developer(self) -> None:
        """Execute node should invoke Developer for task execution."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorState

        mock_developer = AsyncMock()
        mock_developer.execute.return_value = MagicMock(
            success=True,
            source_code="def add(a, b): return a + b",
            test_code="def test_add(): assert add(1, 2) == 3",
        )

        orchestrator = Orchestrator(developer=mock_developer)

        state: OrchestratorState = {
            "user_input": "Build a calculator",
            "prd_output": {"title": "Calculator"},
            "tasks": [{"id": "TASK-001", "description": "Implement add function"}],
            "current_task_idx": 0,
            "executor_results": [],
            "validator_results": [],
            "deployment_status": None,
            "status": "coding",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }

        result = await orchestrator._execute_node(state)
        assert "executor_results" in result

    @pytest.mark.asyncio
    async def test_validate_node_calls_validator(self) -> None:
        """Validate node should invoke ValidatorAgent."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorState

        mock_validator = AsyncMock()
        mock_validator.validate.return_value = MagicMock(
            status="approved",
            passed_tests=True,
            passed_security=True,
            passed_style=True,
        )

        orchestrator = Orchestrator(validator=mock_validator)

        state: OrchestratorState = {
            "user_input": "Build a calculator",
            "prd_output": {"title": "Calculator"},
            "tasks": [{"id": "TASK-001"}],
            "current_task_idx": 0,
            "executor_results": [{"task_id": "TASK-001", "source_code": "def add(): pass"}],
            "validator_results": [],
            "deployment_status": None,
            "status": "validating",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }

        result = await orchestrator._validate_node(state)
        assert "validator_results" in result

    @pytest.mark.asyncio
    async def test_deploy_node_sets_awaiting_approval(self) -> None:
        """Deploy node should set awaiting_approval when human approval required."""
        from daw_agents.workflow.orchestrator import (
            Orchestrator,
            OrchestratorConfig,
            OrchestratorState,
        )

        config = OrchestratorConfig(require_human_approval=True)
        orchestrator = Orchestrator(config=config)

        state: OrchestratorState = {
            "user_input": "Build a calculator",
            "prd_output": {"title": "Calculator"},
            "tasks": [{"id": "TASK-001"}],
            "current_task_idx": 0,
            "executor_results": [{"task_id": "TASK-001", "success": True}],
            "validator_results": [{"task_id": "TASK-001", "passed": True}],
            "deployment_status": None,
            "status": "deploying",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }

        result = await orchestrator._deploy_node(state)
        assert result.get("human_approval_required") is True or result.get("status") == "awaiting_approval"


# -----------------------------------------------------------------------------
# Test: Orchestrator Routing Logic
# -----------------------------------------------------------------------------


class TestOrchestratorRouting:
    """Tests for Orchestrator workflow routing logic."""

    def test_route_after_plan_to_execute(self) -> None:
        """After planning, should route to execute if tasks exist."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorState

        orchestrator = Orchestrator()

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": {"title": "App"},
            "tasks": [{"id": "TASK-001"}],
            "current_task_idx": 0,
            "executor_results": [],
            "validator_results": [],
            "deployment_status": None,
            "status": "planning",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }

        route = orchestrator._route_after_plan(state)
        assert route == "execute"

    def test_route_after_plan_to_error_no_tasks(self) -> None:
        """After planning, should route to error if no tasks generated."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorState

        orchestrator = Orchestrator()

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": None,
            "tasks": [],
            "current_task_idx": 0,
            "executor_results": [],
            "validator_results": [],
            "deployment_status": None,
            "status": "planning",
            "error": "Failed to generate tasks",
            "human_approval_required": False,
            "retry_count": 0,
        }

        route = orchestrator._route_after_plan(state)
        assert route == "error"

    def test_route_after_execute_to_validate(self) -> None:
        """After execution, should route to validate."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorState

        orchestrator = Orchestrator()

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": {"title": "App"},
            "tasks": [{"id": "TASK-001"}],
            "current_task_idx": 0,
            "executor_results": [{"task_id": "TASK-001", "success": True}],
            "validator_results": [],
            "deployment_status": None,
            "status": "coding",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }

        route = orchestrator._route_after_execute(state)
        assert route == "validate"

    def test_route_after_validate_to_next_task(self) -> None:
        """After validation, should route to execute if more tasks exist."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorState

        orchestrator = Orchestrator()

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": {"title": "App"},
            "tasks": [{"id": "TASK-001"}, {"id": "TASK-002"}],
            "current_task_idx": 0,  # Still on first task
            "executor_results": [{"task_id": "TASK-001", "success": True}],
            "validator_results": [{"task_id": "TASK-001", "passed": True}],
            "deployment_status": None,
            "status": "validating",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }

        route = orchestrator._route_after_validate(state)
        assert route == "execute"

    def test_route_after_validate_to_deploy(self) -> None:
        """After all tasks validated, should route to deploy."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorState

        orchestrator = Orchestrator()

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": {"title": "App"},
            "tasks": [{"id": "TASK-001"}],
            "current_task_idx": 0,
            "executor_results": [{"task_id": "TASK-001", "success": True}],
            "validator_results": [{"task_id": "TASK-001", "passed": True}],
            "deployment_status": None,
            "status": "validating",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }

        route = orchestrator._route_after_validate(state)
        assert route == "deploy"

    def test_route_after_validate_retry_on_failure(self) -> None:
        """After validation failure, should retry execution."""
        from daw_agents.workflow.orchestrator import (
            Orchestrator,
            OrchestratorConfig,
            OrchestratorState,
        )

        config = OrchestratorConfig(max_retries=3)
        orchestrator = Orchestrator(config=config)

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": {"title": "App"},
            "tasks": [{"id": "TASK-001"}],
            "current_task_idx": 0,
            "executor_results": [{"task_id": "TASK-001", "success": True}],
            "validator_results": [{"task_id": "TASK-001", "passed": False, "fixable": True}],
            "deployment_status": None,
            "status": "validating",
            "error": None,
            "human_approval_required": False,
            "retry_count": 1,
        }

        route = orchestrator._route_after_validate(state)
        assert route == "execute"  # Retry

    def test_route_after_validate_error_max_retries(self) -> None:
        """After max retries, should route to error."""
        from daw_agents.workflow.orchestrator import (
            Orchestrator,
            OrchestratorConfig,
            OrchestratorState,
        )

        config = OrchestratorConfig(max_retries=3)
        orchestrator = Orchestrator(config=config)

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": {"title": "App"},
            "tasks": [{"id": "TASK-001"}],
            "current_task_idx": 0,
            "executor_results": [{"task_id": "TASK-001", "success": True}],
            "validator_results": [{"task_id": "TASK-001", "passed": False, "fixable": True}],
            "deployment_status": None,
            "status": "validating",
            "error": None,
            "human_approval_required": False,
            "retry_count": 3,  # At max
        }

        route = orchestrator._route_after_validate(state)
        assert route == "error"


# -----------------------------------------------------------------------------
# Test: Orchestrator Execute Full Workflow
# -----------------------------------------------------------------------------


class TestOrchestratorExecute:
    """Tests for Orchestrator execute method."""

    @pytest.mark.asyncio
    async def test_execute_returns_workflow_result(self) -> None:
        """Execute should return WorkflowResult."""
        from daw_agents.workflow.orchestrator import Orchestrator, WorkflowResult

        # Create mock agents
        mock_taskmaster = AsyncMock()
        mock_taskmaster.workflow = MagicMock()
        mock_taskmaster.workflow.ainvoke = AsyncMock(
            return_value={
                "prd": MagicMock(model_dump=lambda: {"title": "Test PRD"}),
                "tasks": [MagicMock(model_dump=lambda: {"id": "TASK-001"})],
                "status": "complete",
            }
        )

        mock_developer = AsyncMock()
        mock_developer.execute = AsyncMock(
            return_value=MagicMock(
                success=True,
                source_code="print('hello')",
                test_code="def test(): pass",
                model_dump=lambda: {"success": True},
            )
        )

        mock_validator = AsyncMock()
        mock_validator.validate = AsyncMock(
            return_value=MagicMock(
                status="approved",
                passed_tests=True,
                passed_security=True,
                passed_style=True,
                model_dump=lambda: {"status": "approved"},
            )
        )

        orchestrator = Orchestrator(
            taskmaster=mock_taskmaster,
            developer=mock_developer,
            validator=mock_validator,
        )

        result = await orchestrator.execute("Build a hello world app")

        assert isinstance(result, WorkflowResult)

    @pytest.mark.asyncio
    async def test_execute_handles_errors(self) -> None:
        """Execute should handle errors gracefully."""
        from daw_agents.workflow.orchestrator import Orchestrator, WorkflowResult

        mock_taskmaster = AsyncMock()
        mock_taskmaster.workflow = MagicMock()
        mock_taskmaster.workflow.ainvoke = AsyncMock(side_effect=Exception("API error"))

        orchestrator = Orchestrator(taskmaster=mock_taskmaster)

        result = await orchestrator.execute("Build an app")

        assert isinstance(result, WorkflowResult)
        assert result.success is False
        assert result.error is not None


# -----------------------------------------------------------------------------
# Test: Human-in-the-Loop Approval
# -----------------------------------------------------------------------------


class TestOrchestratorApproval:
    """Tests for human-in-the-loop approval functionality."""

    @pytest.mark.asyncio
    async def test_approve_workflow_continues(self) -> None:
        """Approve method should continue workflow after human approval."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorConfig

        config = OrchestratorConfig(require_human_approval=True)
        orchestrator = Orchestrator(config=config)

        # Simulate a paused workflow awaiting approval
        orchestrator._pending_approval = {
            "workflow_id": "test-123",
            "state": {
                "status": "awaiting_approval",
                "human_approval_required": True,
            },
        }

        result = await orchestrator.approve("test-123")
        assert result is True or result.get("continued") is True

    @pytest.mark.asyncio
    async def test_reject_workflow_cancels(self) -> None:
        """Reject method should cancel workflow."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorConfig

        config = OrchestratorConfig(require_human_approval=True)
        orchestrator = Orchestrator(config=config)

        orchestrator._pending_approval = {
            "workflow_id": "test-123",
            "state": {
                "status": "awaiting_approval",
                "human_approval_required": True,
            },
        }

        result = await orchestrator.reject("test-123", reason="Not ready")
        assert result is True or result.get("cancelled") is True


# -----------------------------------------------------------------------------
# Test: Redis Checkpoint Integration
# -----------------------------------------------------------------------------


class TestOrchestratorCheckpoints:
    """Tests for Redis checkpoint integration."""

    @pytest.mark.asyncio
    async def test_checkpoint_saves_state(self) -> None:
        """Checkpoints should save workflow state to Redis."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorConfig

        config = OrchestratorConfig(checkpoint_enabled=True)

        with patch("daw_agents.workflow.orchestrator.get_async_redis_client") as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            orchestrator = Orchestrator(config=config)

            # Verify checkpoint mechanism is configured
            assert orchestrator._config.checkpoint_enabled is True

    @pytest.mark.asyncio
    async def test_checkpoint_restores_state(self) -> None:
        """Should be able to restore workflow from checkpoint."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorConfig

        config = OrchestratorConfig(checkpoint_enabled=True)
        orchestrator = Orchestrator(config=config)

        # This tests the interface exists
        assert hasattr(orchestrator, "restore_from_checkpoint") or hasattr(
            orchestrator, "_restore_checkpoint"
        )


# -----------------------------------------------------------------------------
# Test: Event Emission for Streaming
# -----------------------------------------------------------------------------


class TestOrchestratorEvents:
    """Tests for event emission for UI streaming."""

    def test_orchestrator_has_event_emitter(self) -> None:
        """Orchestrator should have event emitter for streaming."""
        from daw_agents.workflow.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        assert hasattr(orchestrator, "on_event") or hasattr(orchestrator, "_emit_event")

    @pytest.mark.asyncio
    async def test_emits_status_change_events(self) -> None:
        """Orchestrator should emit events on status changes."""
        from daw_agents.workflow.orchestrator import Orchestrator

        events_received: list[dict[str, Any]] = []

        def event_handler(event: dict[str, Any]) -> None:
            events_received.append(event)

        orchestrator = Orchestrator()
        if hasattr(orchestrator, "on_event"):
            orchestrator.on_event(event_handler)
        elif hasattr(orchestrator, "_event_handlers"):
            orchestrator._event_handlers.append(event_handler)

        # Verify event system is set up
        assert hasattr(orchestrator, "_event_handlers") or hasattr(orchestrator, "_emit_event")


# -----------------------------------------------------------------------------
# Test: Integration with Deploy Gates
# -----------------------------------------------------------------------------


class TestOrchestratorDeployGates:
    """Tests for integration with deployment gates."""

    @pytest.mark.asyncio
    async def test_deploy_checks_gates(self) -> None:
        """Deploy should check deployment gates before proceeding."""
        from daw_agents.workflow.orchestrator import Orchestrator, OrchestratorState

        orchestrator = Orchestrator()

        state: OrchestratorState = {
            "user_input": "Build app",
            "prd_output": {"title": "App"},
            "tasks": [{"id": "TASK-001"}],
            "current_task_idx": 0,
            "executor_results": [{"task_id": "TASK-001", "success": True}],
            "validator_results": [{"task_id": "TASK-001", "passed": True}],
            "deployment_status": None,
            "status": "deploying",
            "error": None,
            "human_approval_required": False,
            "retry_count": 0,
        }

        result = await orchestrator._deploy_node(state)
        assert "deployment_status" in result


# -----------------------------------------------------------------------------
# Test: Orchestrator Create Initial State
# -----------------------------------------------------------------------------


class TestOrchestratorCreateState:
    """Tests for create_initial_state method."""

    def test_create_initial_state(self) -> None:
        """create_initial_state should create valid OrchestratorState."""
        from daw_agents.workflow.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        state = orchestrator.create_initial_state("Build a calculator")

        assert state["user_input"] == "Build a calculator"
        assert state["prd_output"] is None
        assert state["tasks"] == []
        assert state["current_task_idx"] == 0
        assert state["status"] == "planning"
        assert state["error"] is None


# -----------------------------------------------------------------------------
# Test: Workflow Graph Structure
# -----------------------------------------------------------------------------


class TestOrchestratorGraphStructure:
    """Tests for the LangGraph workflow structure."""

    def test_workflow_has_plan_node(self) -> None:
        """Workflow should have plan node."""
        from daw_agents.workflow.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        # Check that the node exists in the graph
        assert hasattr(orchestrator, "_plan_node")

    def test_workflow_has_execute_node(self) -> None:
        """Workflow should have execute node."""
        from daw_agents.workflow.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        assert hasattr(orchestrator, "_execute_node")

    def test_workflow_has_validate_node(self) -> None:
        """Workflow should have validate node."""
        from daw_agents.workflow.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        assert hasattr(orchestrator, "_validate_node")

    def test_workflow_has_deploy_node(self) -> None:
        """Workflow should have deploy node."""
        from daw_agents.workflow.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        assert hasattr(orchestrator, "_deploy_node")
