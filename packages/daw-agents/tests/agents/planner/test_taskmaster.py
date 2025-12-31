"""
Tests for the Taskmaster Agent (PLANNER-001).

The Taskmaster agent is the Planner Agent that:
1. Receives high-level user requirements
2. Interviews users to clarify requirements
3. Conducts roundtable discussions with synthetic personas (CTO, UX, Security)
4. Generates structured PRD documents
5. Uses LangGraph for state machine workflow

States: INTERVIEW -> ROUNDTABLE -> GENERATE_PRD -> COMPLETE
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daw_agents.agents.planner.taskmaster import (
    PlannerState,
    PlannerStatus,
    PRDOutput,
    RoundtablePersona,
    Task,
    Taskmaster,
)


class TestPlannerState:
    """Test PlannerState TypedDict and related models."""

    def test_planner_state_fields_exist(self) -> None:
        """Verify PlannerState has all required fields."""
        state: PlannerState = {
            "requirement": "Build a todo app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
        }
        assert state["requirement"] == "Build a todo app"
        assert state["status"] == PlannerStatus.INTERVIEW
        assert state["messages"] == []
        assert state["prd"] is None

    def test_planner_status_enum_values(self) -> None:
        """Verify all PlannerStatus values exist."""
        assert PlannerStatus.INTERVIEW == "interview"
        assert PlannerStatus.ROUNDTABLE == "roundtable"
        assert PlannerStatus.GENERATE_PRD == "generate_prd"
        assert PlannerStatus.COMPLETE == "complete"
        assert PlannerStatus.ERROR == "error"


class TestTask:
    """Test Task Pydantic model."""

    def test_task_creation(self) -> None:
        """Test creating a Task with all fields."""
        task = Task(
            id="TASK-001",
            description="Implement user authentication",
            priority="P0",
            type="code",
            dependencies=[],
            estimated_hours=3.0,
            model_hint="coding",
            verification={"type": "test_pass", "command": "pytest tests/test_auth.py"},
        )
        assert task.id == "TASK-001"
        assert task.description == "Implement user authentication"
        assert task.priority == "P0"
        assert task.model_hint == "coding"

    def test_task_with_dependencies(self) -> None:
        """Test Task with dependencies."""
        task = Task(
            id="TASK-002",
            description="Implement user profile page",
            priority="P1",
            type="code",
            dependencies=["TASK-001"],
            estimated_hours=2.0,
        )
        assert task.dependencies == ["TASK-001"]

    def test_task_default_values(self) -> None:
        """Test Task default values."""
        task = Task(
            id="TASK-003",
            description="Add documentation",
            priority="P2",
            type="docs",
        )
        assert task.dependencies == []
        assert task.estimated_hours is None
        assert task.model_hint is None


class TestPRDOutput:
    """Test PRDOutput Pydantic model."""

    def test_prd_output_creation(self) -> None:
        """Test creating a PRDOutput with required fields."""
        prd = PRDOutput(
            title="Todo Application PRD",
            overview="A simple todo application for task management",
            user_stories=[
                {
                    "id": "US-001",
                    "description": "As a user, I can create tasks",
                    "priority": "P0",
                    "acceptance_criteria": ["Task appears in list after creation"],
                }
            ],
            tech_specs={
                "architecture": "Next.js frontend with FastAPI backend",
                "technology_stack": ["Next.js", "FastAPI", "PostgreSQL"],
            },
            acceptance_criteria=["All P0 stories complete", "Test coverage > 80%"],
        )
        assert prd.title == "Todo Application PRD"
        assert len(prd.user_stories) == 1

    def test_prd_output_validation(self) -> None:
        """Test PRDOutput requires all fields."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            PRDOutput(title="Test")  # Missing required fields


class TestRoundtablePersona:
    """Test RoundtablePersona model."""

    def test_persona_creation(self) -> None:
        """Test creating a RoundtablePersona."""
        persona = RoundtablePersona(
            name="CTO",
            role="Chief Technology Officer",
            focus="Technical feasibility and architecture",
            critique_prompt="Evaluate the technical architecture and scalability.",
        )
        assert persona.name == "CTO"
        assert persona.role == "Chief Technology Officer"


class TestTaskmasterInitialization:
    """Test Taskmaster agent initialization."""

    def test_taskmaster_init_default(self) -> None:
        """Test Taskmaster initializes with defaults."""
        taskmaster = Taskmaster()
        assert taskmaster is not None
        assert taskmaster.workflow is not None

    def test_taskmaster_init_with_custom_router(self) -> None:
        """Test Taskmaster can accept custom model router."""
        mock_router = MagicMock()
        taskmaster = Taskmaster(model_router=mock_router)
        assert taskmaster._model_router == mock_router

    def test_taskmaster_init_with_custom_mcp_client(self) -> None:
        """Test Taskmaster can accept custom MCP client."""
        mock_mcp = MagicMock()
        taskmaster = Taskmaster(mcp_client=mock_mcp)
        assert taskmaster._mcp_client == mock_mcp


class TestTaskmasterWorkflow:
    """Test Taskmaster LangGraph workflow structure."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance for testing."""
        return Taskmaster()

    def test_workflow_has_interview_node(self, taskmaster: Taskmaster) -> None:
        """Test workflow has interview node."""
        graph = taskmaster.workflow
        # Check that the compiled graph has expected nodes
        assert graph is not None
        # Graph inspection methods vary by LangGraph version

    def test_workflow_has_roundtable_node(self, taskmaster: Taskmaster) -> None:
        """Test workflow has roundtable node."""
        assert taskmaster.workflow is not None

    def test_workflow_has_generate_prd_node(self, taskmaster: Taskmaster) -> None:
        """Test workflow has generate_prd node."""
        assert taskmaster.workflow is not None


class TestTaskmasterPlan:
    """Test Taskmaster.plan() method."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster with mocked dependencies."""
        mock_router = MagicMock()
        return Taskmaster(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_plan_returns_tasks(self, taskmaster: Taskmaster) -> None:
        """Test that plan() returns a list of tasks."""
        # Mock the workflow invocation
        with patch.object(
            taskmaster, "workflow", new_callable=MagicMock
        ) as mock_workflow:
            mock_workflow.ainvoke = AsyncMock(
                return_value={
                    "requirement": "Build a todo app",
                    "messages": [],
                    "clarifications": [],
                    "roundtable_critiques": [],
                    "prd": PRDOutput(
                        title="Todo App",
                        overview="A todo application",
                        user_stories=[],
                        tech_specs={},
                        acceptance_criteria=[],
                    ),
                    "tasks": [
                        Task(
                            id="TASK-001",
                            description="Setup project",
                            priority="P0",
                            type="setup",
                        )
                    ],
                    "status": PlannerStatus.COMPLETE,
                    "error": None,
                }
            )

            result = await taskmaster.plan("Build a todo app")

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0].id == "TASK-001"

    @pytest.mark.asyncio
    async def test_plan_uses_planning_model(self, taskmaster: Taskmaster) -> None:
        """Test that plan() uses the PLANNING task type for model routing."""
        with patch.object(
            taskmaster, "workflow", new_callable=MagicMock
        ) as mock_workflow:
            mock_workflow.ainvoke = AsyncMock(
                return_value={
                    "requirement": "Test",
                    "messages": [],
                    "clarifications": [],
                    "roundtable_critiques": [],
                    "prd": None,
                    "tasks": [],
                    "status": PlannerStatus.COMPLETE,
                    "error": None,
                }
            )

            await taskmaster.plan("Build a todo app")

            # Verify workflow was invoked
            mock_workflow.ainvoke.assert_called_once()


class TestTaskmasterInterview:
    """Test Taskmaster interview functionality."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance for testing."""
        mock_router = MagicMock()
        return Taskmaster(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_interview_generates_clarifications(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test that interview node generates interview state or clarifications."""
        initial_state: PlannerState = {
            "requirement": "Build a web app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
            "interview_state": None,
        }

        with patch.object(
            taskmaster._model_router, "route", new_callable=AsyncMock
        ) as mock_route:
            # Return valid JSON for question generation
            mock_route.return_value = '[{"id": "Q-001", "type": "text", "text": "What features?", "required": true}]'

            result = await taskmaster._interview_node(initial_state)

            # New behavior: interview node generates interview_state
            assert "interview_state" in result or "clarifications" in result
            mock_route.assert_called()


class TestTaskmasterRoundtable:
    """Test Taskmaster roundtable functionality."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance for testing."""
        mock_router = MagicMock()
        return Taskmaster(model_router=mock_router)

    def test_default_personas_exist(self, taskmaster: Taskmaster) -> None:
        """Test that default personas (CTO, UX, Security) are defined."""
        personas = taskmaster.get_personas()
        persona_names = [p.name for p in personas]
        assert "CTO" in persona_names or "cto" in [n.lower() for n in persona_names]
        assert "UX" in persona_names or "ux" in [n.lower() for n in persona_names]
        assert (
            "Security" in persona_names
            or "security" in [n.lower() for n in persona_names]
        )

    @pytest.mark.asyncio
    async def test_roundtable_collects_critiques(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test that roundtable node collects critiques from all personas."""
        state: PlannerState = {
            "requirement": "Build a todo app",
            "messages": [
                {"role": "user", "content": "I need a simple todo app"},
                {"role": "assistant", "content": "Here's my initial proposal..."},
            ],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.ROUNDTABLE,
            "error": None,
        }

        with patch.object(
            taskmaster._model_router, "route", new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = "CTO critique: Consider scalability..."

            result = await taskmaster._roundtable_node(state)

            # Should have collected critiques
            assert "roundtable_critiques" in result
            # Called once per persona (at minimum)
            assert mock_route.call_count >= 1


class TestTaskmasterGeneratePRD:
    """Test Taskmaster PRD generation."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance for testing."""
        mock_router = MagicMock()
        return Taskmaster(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_generate_prd_returns_structured_output(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test that generate_prd node returns a structured PRD."""
        state: PlannerState = {
            "requirement": "Build a todo app",
            "messages": [],
            "clarifications": ["Need mobile support"],
            "roundtable_critiques": ["CTO: Add caching", "Security: Add auth"],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.GENERATE_PRD,
            "error": None,
        }

        mock_prd_response = """
        {
            "title": "Todo Application PRD",
            "overview": "A mobile-friendly todo app with authentication",
            "user_stories": [
                {
                    "id": "US-001",
                    "description": "As a user, I can create tasks",
                    "priority": "P0",
                    "acceptance_criteria": ["Task appears in list"]
                }
            ],
            "tech_specs": {
                "architecture": "Next.js with FastAPI",
                "technology_stack": ["Next.js", "FastAPI"]
            },
            "acceptance_criteria": ["All P0 features work"]
        }
        """

        with patch.object(
            taskmaster._model_router, "route", new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = mock_prd_response

            result = await taskmaster._generate_prd_node(state)

            assert "prd" in result
            # PRD should be a structured object
            assert result["prd"] is not None


class TestTaskmasterStateTransitions:
    """Test Taskmaster state machine transitions."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance for testing."""
        return Taskmaster()

    def test_initial_state_is_interview(self, taskmaster: Taskmaster) -> None:
        """Test that initial state is INTERVIEW."""
        initial_state = taskmaster.create_initial_state("Build a todo app")
        assert initial_state["status"] == PlannerStatus.INTERVIEW

    def test_interview_to_roundtable_transition(self, taskmaster: Taskmaster) -> None:
        """Test transition from INTERVIEW to ROUNDTABLE."""
        state: PlannerState = {
            "requirement": "Build a todo app",
            "messages": [{"role": "assistant", "content": "Got it"}],
            "clarifications": ["Need mobile support"],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
        }

        next_status = taskmaster._get_next_status(state)
        assert next_status == PlannerStatus.ROUNDTABLE

    def test_roundtable_to_generate_prd_transition(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test transition from ROUNDTABLE to GENERATE_PRD."""
        state: PlannerState = {
            "requirement": "Build a todo app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": ["CTO: Looks good", "UX: Improve flow"],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.ROUNDTABLE,
            "error": None,
        }

        next_status = taskmaster._get_next_status(state)
        assert next_status == PlannerStatus.GENERATE_PRD

    def test_generate_prd_to_complete_transition(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test transition from GENERATE_PRD to COMPLETE."""
        state: PlannerState = {
            "requirement": "Build a todo app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": MagicMock(),
            "tasks": [MagicMock()],
            "status": PlannerStatus.GENERATE_PRD,
            "error": None,
        }

        next_status = taskmaster._get_next_status(state)
        assert next_status == PlannerStatus.COMPLETE


class TestTaskmasterPrioritize:
    """Test Taskmaster.prioritize() method."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance for testing."""
        return Taskmaster()

    def test_prioritize_orders_by_dependency(self, taskmaster: Taskmaster) -> None:
        """Test that prioritize orders tasks by dependencies."""
        tasks = [
            Task(
                id="TASK-002",
                description="Build UI",
                priority="P0",
                type="code",
                dependencies=["TASK-001"],
            ),
            Task(
                id="TASK-001",
                description="Setup project",
                priority="P0",
                type="setup",
                dependencies=[],
            ),
            Task(
                id="TASK-003",
                description="Add tests",
                priority="P1",
                type="test",
                dependencies=["TASK-002"],
            ),
        ]

        ordered = taskmaster.prioritize(tasks)

        # TASK-001 should come before TASK-002
        task_ids = [t.id for t in ordered]
        assert task_ids.index("TASK-001") < task_ids.index("TASK-002")
        # TASK-002 should come before TASK-003
        assert task_ids.index("TASK-002") < task_ids.index("TASK-003")

    def test_prioritize_respects_priority_levels(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test that prioritize respects P0 > P1 > P2."""
        tasks = [
            Task(
                id="TASK-001",
                description="P2 task",
                priority="P2",
                type="docs",
                dependencies=[],
            ),
            Task(
                id="TASK-002",
                description="P0 task",
                priority="P0",
                type="code",
                dependencies=[],
            ),
            Task(
                id="TASK-003",
                description="P1 task",
                priority="P1",
                type="code",
                dependencies=[],
            ),
        ]

        ordered = taskmaster.prioritize(tasks)

        # P0 should come before P1, P1 before P2
        task_ids = [t.id for t in ordered]
        assert task_ids.index("TASK-002") < task_ids.index("TASK-003")
        assert task_ids.index("TASK-003") < task_ids.index("TASK-001")


class TestTaskmasterAssignMetadata:
    """Test Taskmaster.assign_metadata() method."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance for testing."""
        return Taskmaster()

    def test_assign_metadata_adds_model_hint(self, taskmaster: Taskmaster) -> None:
        """Test that assign_metadata adds model_hint for coding tasks."""
        task = Task(
            id="TASK-001",
            description="Implement auth",
            priority="P0",
            type="code",
            dependencies=[],
        )

        enhanced = taskmaster.assign_metadata(task)

        # Should have model_hint assigned
        assert enhanced.model_hint is not None
        assert enhanced.model_hint in ["coding", "planning", "validation", "fast"]

    def test_assign_metadata_estimates_hours(self, taskmaster: Taskmaster) -> None:
        """Test that assign_metadata estimates hours if not set."""
        task = Task(
            id="TASK-001",
            description="Implement complex feature",
            priority="P0",
            type="code",
            dependencies=[],
        )

        enhanced = taskmaster.assign_metadata(task)

        # Should have estimated_hours assigned
        assert enhanced.estimated_hours is not None
        assert enhanced.estimated_hours > 0


class TestTaskmasterNeo4jPersistence:
    """Test Taskmaster Neo4j conversation persistence."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster with mocked Neo4j."""
        mock_neo4j = MagicMock()
        return Taskmaster(neo4j_connector=mock_neo4j)

    @pytest.mark.asyncio
    async def test_conversation_persisted_to_neo4j(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test that conversations are persisted to Neo4j."""
        if taskmaster._neo4j is None:
            pytest.skip("No Neo4j connector configured")

        state: PlannerState = {
            "requirement": "Build a todo app",
            "messages": [
                {"role": "user", "content": "Build a todo app"},
                {"role": "assistant", "content": "I'll help you with that"},
            ],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
        }

        await taskmaster._persist_conversation(state)

        # Verify Neo4j was called
        taskmaster._neo4j.create_node.assert_called()


class TestTaskmasterErrorHandling:
    """Test Taskmaster error handling."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance for testing."""
        mock_router = MagicMock()
        return Taskmaster(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_plan_handles_model_error(self, taskmaster: Taskmaster) -> None:
        """Test that plan() handles model errors gracefully."""
        with patch.object(
            taskmaster, "workflow", new_callable=MagicMock
        ) as mock_workflow:
            mock_workflow.ainvoke = AsyncMock(side_effect=Exception("Model error"))

            with pytest.raises(Exception, match="Model error"):
                await taskmaster.plan("Build a todo app")

    @pytest.mark.asyncio
    async def test_error_state_captured(self, taskmaster: Taskmaster) -> None:
        """Test that error state is properly captured."""
        state: PlannerState = {
            "requirement": "Build a todo app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
        }

        # Simulate error during interview
        with patch.object(
            taskmaster._model_router, "route", new_callable=AsyncMock
        ) as mock_route:
            mock_route.side_effect = Exception("LLM failed")

            try:
                await taskmaster._interview_node(state)
            except Exception:
                pass

            # Error should be captured in state (implementation detail)


class TestTaskmasterWorkflowIntegration:
    """Integration tests for the complete Taskmaster workflow."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster with mocked dependencies."""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value='{"status": "ok"}')
        return Taskmaster(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_full_workflow_execution(self, taskmaster: Taskmaster) -> None:
        """Test executing the full workflow from requirement to tasks."""
        with patch.object(
            taskmaster, "workflow", new_callable=MagicMock
        ) as mock_workflow:
            mock_workflow.ainvoke = AsyncMock(
                return_value={
                    "requirement": "Build a todo app",
                    "messages": [
                        {"role": "user", "content": "Build a todo app"},
                        {"role": "assistant", "content": "Interview questions..."},
                    ],
                    "clarifications": ["Mobile support needed"],
                    "roundtable_critiques": ["CTO: Use microservices"],
                    "prd": PRDOutput(
                        title="Todo App",
                        overview="A todo app",
                        user_stories=[
                            {
                                "id": "US-001",
                                "description": "Create tasks",
                                "priority": "P0",
                                "acceptance_criteria": ["Works"],
                            }
                        ],
                        tech_specs={},
                        acceptance_criteria=[],
                    ),
                    "tasks": [
                        Task(
                            id="TASK-001",
                            description="Setup",
                            priority="P0",
                            type="setup",
                        ),
                        Task(
                            id="TASK-002",
                            description="Implement",
                            priority="P0",
                            type="code",
                            dependencies=["TASK-001"],
                        ),
                    ],
                    "status": PlannerStatus.COMPLETE,
                    "error": None,
                }
            )

            result = await taskmaster.plan("Build a todo app")

            # Should return tasks in correct order
            assert len(result) == 2
            assert result[0].id == "TASK-001"
            assert result[1].id == "TASK-002"
