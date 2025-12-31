"""
Tests for Taskmaster Interview functionality (INTERACT-001).

This module tests the interview response collection feature:
1. Question and InterviewState models
2. AWAITING_INTERVIEW status
3. Interview node question generation
4. Answer submission and tracking
5. Interview completion logic
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daw_agents.agents.planner.taskmaster import (
    InterviewState,
    PlannerState,
    PlannerStatus,
    Question,
    QuestionType,
    Taskmaster,
)


class TestQuestionModel:
    """Test Question Pydantic model."""

    def test_question_creation_text_type(self) -> None:
        """Test creating a text question."""
        question = Question(
            id="Q-001",
            type=QuestionType.TEXT,
            text="What features do you need?",
            required=True,
            context="Understanding feature requirements",
        )
        assert question.id == "Q-001"
        assert question.type == QuestionType.TEXT
        assert question.text == "What features do you need?"
        assert question.required is True
        assert question.options is None

    def test_question_creation_multi_choice(self) -> None:
        """Test creating a multi-choice question."""
        question = Question(
            id="Q-002",
            type=QuestionType.MULTI_CHOICE,
            text="What is your preferred technology stack?",
            options=["React", "Vue", "Angular", "Svelte"],
            required=True,
        )
        assert question.type == QuestionType.MULTI_CHOICE
        assert question.options == ["React", "Vue", "Angular", "Svelte"]
        assert len(question.options) == 4

    def test_question_creation_checkbox(self) -> None:
        """Test creating a checkbox question."""
        question = Question(
            id="Q-003",
            type=QuestionType.CHECKBOX,
            text="Which platforms should be supported?",
            options=["Web", "iOS", "Android", "Desktop"],
            required=False,
        )
        assert question.type == QuestionType.CHECKBOX
        assert question.required is False

    def test_question_default_values(self) -> None:
        """Test question default values."""
        question = Question(
            id="Q-004",
            text="Describe your timeline.",
        )
        assert question.type == QuestionType.TEXT
        assert question.required is True
        assert question.options is None
        assert question.context is None


class TestInterviewStateModel:
    """Test InterviewState Pydantic model."""

    def test_interview_state_creation(self) -> None:
        """Test creating an interview state."""
        questions = [
            Question(id="Q-001", text="Question 1"),
            Question(id="Q-002", text="Question 2"),
        ]
        state = InterviewState(
            workflow_id="workflow-123",
            questions=questions,
            answers={},
            current_index=0,
            completed=False,
        )
        assert state.workflow_id == "workflow-123"
        assert len(state.questions) == 2
        assert state.current_index == 0
        assert state.completed is False

    def test_interview_state_with_answers(self) -> None:
        """Test interview state with partial answers."""
        questions = [
            Question(id="Q-001", text="Question 1"),
            Question(id="Q-002", text="Question 2"),
        ]
        state = InterviewState(
            workflow_id="workflow-123",
            questions=questions,
            answers={"Q-001": "Answer 1"},
            current_index=1,
            completed=False,
        )
        assert "Q-001" in state.answers
        assert state.answers["Q-001"] == "Answer 1"
        assert state.current_index == 1

    def test_interview_state_checkbox_answer(self) -> None:
        """Test interview state with checkbox (list) answer."""
        questions = [
            Question(
                id="Q-001",
                type=QuestionType.CHECKBOX,
                text="Select platforms",
                options=["Web", "Mobile"],
            ),
        ]
        state = InterviewState(
            workflow_id="workflow-123",
            questions=questions,
            answers={"Q-001": ["Web", "Mobile"]},
            current_index=1,
            completed=True,
        )
        assert isinstance(state.answers["Q-001"], list)
        assert len(state.answers["Q-001"]) == 2

    def test_interview_state_defaults(self) -> None:
        """Test interview state default values."""
        state = InterviewState(workflow_id="workflow-123")
        assert state.questions == []
        assert state.answers == {}
        assert state.current_index == 0
        assert state.completed is False


class TestPlannerStatusEnum:
    """Test PlannerStatus enum includes AWAITING_INTERVIEW."""

    def test_awaiting_interview_status_exists(self) -> None:
        """Test that AWAITING_INTERVIEW status exists."""
        assert hasattr(PlannerStatus, "AWAITING_INTERVIEW")
        assert PlannerStatus.AWAITING_INTERVIEW == "awaiting_interview"

    def test_all_status_values(self) -> None:
        """Test all expected status values exist."""
        expected_statuses = [
            "interview",
            "awaiting_interview",
            "roundtable",
            "generate_prd",
            "complete",
            "error",
        ]
        actual_values = [s.value for s in PlannerStatus]
        for expected in expected_statuses:
            assert expected in actual_values


class TestPlannerStateWithInterview:
    """Test PlannerState TypedDict includes interview_state."""

    def test_planner_state_has_interview_state_field(self) -> None:
        """Test that PlannerState includes interview_state."""
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
            "interview_state": None,
        }
        assert "interview_state" in state
        assert state["interview_state"] is None

    def test_planner_state_with_interview_state(self) -> None:
        """Test PlannerState with actual interview state."""
        interview = InterviewState(
            workflow_id="wf-123",
            questions=[Question(id="Q-001", text="Test?")],
            answers={},
            current_index=0,
            completed=False,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }
        assert state["interview_state"] is not None
        assert state["interview_state"].workflow_id == "wf-123"


class TestTaskmasterInterviewGeneration:
    """Test Taskmaster interview question generation."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster with mocked model router."""
        mock_router = MagicMock()
        return Taskmaster(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_interview_node_generates_questions(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test that interview node generates questions and returns AWAITING_INTERVIEW."""
        initial_state: PlannerState = {
            "requirement": "Build a todo app",
            "messages": [{"role": "user", "content": "Build a todo app"}],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
            "interview_state": None,
        }

        # Mock response as the model would return it - a clean JSON array
        mock_response = '[{"id": "Q-001", "type": "text", "text": "What features do you need?", "required": true, "context": "Understanding requirements"}, {"id": "Q-002", "type": "multi_choice", "text": "What is your tech stack?", "options": ["React", "Vue", "Angular"], "required": true}]'

        with patch.object(
            taskmaster._model_router, "route", new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = mock_response

            result = await taskmaster._interview_node(initial_state)

            assert result["status"] == PlannerStatus.AWAITING_INTERVIEW
            assert result["interview_state"] is not None
            assert len(result["interview_state"].questions) == 2
            assert result["interview_state"].completed is False

    @pytest.mark.asyncio
    async def test_interview_node_fallback_on_parse_error(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test interview node fallback when JSON parsing fails."""
        initial_state: PlannerState = {
            "requirement": "Build an app",
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
            # Return invalid JSON
            mock_route.return_value = "This is not valid JSON"

            result = await taskmaster._interview_node(initial_state)

            # Should create fallback question
            assert result["status"] == PlannerStatus.AWAITING_INTERVIEW
            assert result["interview_state"] is not None
            assert len(result["interview_state"].questions) == 1


class TestTaskmasterAnswerSubmission:
    """Test Taskmaster answer submission methods."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance."""
        return Taskmaster()

    def test_submit_interview_answer_single(self, taskmaster: Taskmaster) -> None:
        """Test submitting a single answer."""
        questions = [
            Question(id="Q-001", text="Question 1", required=True),
            Question(id="Q-002", text="Question 2", required=True),
        ]
        interview = InterviewState(
            workflow_id="wf-123",
            questions=questions,
            answers={},
            current_index=0,
            completed=False,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        new_state = taskmaster.submit_interview_answer(
            state, "Q-001", "My answer"
        )

        assert "Q-001" in new_state["interview_state"].answers
        assert new_state["interview_state"].answers["Q-001"] == "My answer"
        assert new_state["interview_state"].current_index == 1

    def test_submit_interview_answer_completes_interview(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test that submitting all required answers completes interview."""
        questions = [
            Question(id="Q-001", text="Question 1", required=True),
        ]
        interview = InterviewState(
            workflow_id="wf-123",
            questions=questions,
            answers={},
            current_index=0,
            completed=False,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        new_state = taskmaster.submit_interview_answer(
            state, "Q-001", "Final answer"
        )

        assert new_state["interview_state"].completed is True
        assert new_state["status"] == PlannerStatus.INTERVIEW

    def test_submit_answer_invalid_question_id(self, taskmaster: Taskmaster) -> None:
        """Test error when submitting answer for invalid question."""
        questions = [Question(id="Q-001", text="Question 1")]
        interview = InterviewState(
            workflow_id="wf-123",
            questions=questions,
            answers={},
            current_index=0,
            completed=False,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        with pytest.raises(ValueError, match="not found"):
            taskmaster.submit_interview_answer(state, "Q-999", "Answer")

    def test_submit_answer_no_interview(self, taskmaster: Taskmaster) -> None:
        """Test error when no interview in progress."""
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
            "interview_state": None,
        }

        with pytest.raises(ValueError, match="No interview"):
            taskmaster.submit_interview_answer(state, "Q-001", "Answer")


class TestTaskmasterSkipRemaining:
    """Test Taskmaster skip remaining questions functionality."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance."""
        return Taskmaster()

    def test_skip_remaining_with_all_required_answered(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test skipping remaining questions when required are answered."""
        questions = [
            Question(id="Q-001", text="Required Q", required=True),
            Question(id="Q-002", text="Optional Q", required=False),
        ]
        interview = InterviewState(
            workflow_id="wf-123",
            questions=questions,
            answers={"Q-001": "Required answer"},
            current_index=1,
            completed=False,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        new_state = taskmaster.skip_remaining_questions(state)

        assert new_state["interview_state"].completed is True

    def test_skip_remaining_fails_with_unanswered_required(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test skip fails when required questions are unanswered."""
        questions = [
            Question(id="Q-001", text="Required Q1", required=True),
            Question(id="Q-002", text="Required Q2", required=True),
        ]
        interview = InterviewState(
            workflow_id="wf-123",
            questions=questions,
            answers={"Q-001": "Answer 1"},
            current_index=1,
            completed=False,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        with pytest.raises(ValueError, match="Cannot skip"):
            taskmaster.skip_remaining_questions(state)


class TestTaskmasterGetQuestion:
    """Test Taskmaster question retrieval methods."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance."""
        return Taskmaster()

    def test_get_current_question(self, taskmaster: Taskmaster) -> None:
        """Test getting current question."""
        questions = [
            Question(id="Q-001", text="Question 1"),
            Question(id="Q-002", text="Question 2"),
        ]
        interview = InterviewState(
            workflow_id="wf-123",
            questions=questions,
            answers={},
            current_index=0,
            completed=False,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        question = taskmaster.get_current_question(state)

        assert question is not None
        assert question.id == "Q-001"

    def test_get_current_question_returns_none_when_complete(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test get_current_question returns None when interview complete."""
        interview = InterviewState(
            workflow_id="wf-123",
            questions=[Question(id="Q-001", text="Q1")],
            answers={"Q-001": "A1"},
            current_index=1,
            completed=True,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        question = taskmaster.get_current_question(state)

        assert question is None

    def test_get_next_unanswered_question(self, taskmaster: Taskmaster) -> None:
        """Test getting next unanswered question."""
        questions = [
            Question(id="Q-001", text="Question 1"),
            Question(id="Q-002", text="Question 2"),
            Question(id="Q-003", text="Question 3"),
        ]
        interview = InterviewState(
            workflow_id="wf-123",
            questions=questions,
            answers={"Q-001": "A1"},  # First answered, skip to second
            current_index=1,
            completed=False,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        question = taskmaster.get_next_unanswered_question(state)

        assert question is not None
        assert question.id == "Q-002"


class TestTaskmasterInterviewProcessing:
    """Test Taskmaster interview answer processing."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster with mocked dependencies."""
        mock_router = MagicMock()
        return Taskmaster(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_process_interview_answers(self, taskmaster: Taskmaster) -> None:
        """Test processing completed interview answers."""
        questions = [
            Question(id="Q-001", text="What features?"),
            Question(id="Q-002", text="What stack?"),
        ]
        interview = InterviewState(
            workflow_id="wf-123",
            questions=questions,
            answers={"Q-001": "CRUD ops", "Q-002": "React"},
            current_index=2,
            completed=True,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        result = await taskmaster._process_interview_answers(state, interview)

        # Should have clarifications derived from answers
        assert "clarifications" in result
        assert len(result["clarifications"]) == 2
        assert result["status"] == PlannerStatus.INTERVIEW

    @pytest.mark.asyncio
    async def test_interview_node_with_completed_answers(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test interview node processes completed answers."""
        questions = [
            Question(id="Q-001", text="What?", required=True),
        ]
        interview = InterviewState(
            workflow_id="wf-123",
            questions=questions,
            answers={"Q-001": "Answer"},
            current_index=1,
            completed=True,
        )
        state: PlannerState = {
            "requirement": "Build an app",
            "messages": [],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.AWAITING_INTERVIEW,
            "error": None,
            "interview_state": interview,
        }

        result = await taskmaster._interview_node(state)

        # Should process answers and return INTERVIEW status for continuation
        assert result["status"] == PlannerStatus.INTERVIEW
        assert "clarifications" in result


class TestTaskmasterCreateInitialState:
    """Test Taskmaster.create_initial_state includes interview_state."""

    @pytest.fixture
    def taskmaster(self) -> Taskmaster:
        """Create a Taskmaster instance."""
        return Taskmaster()

    def test_initial_state_includes_interview_state(
        self, taskmaster: Taskmaster
    ) -> None:
        """Test that create_initial_state includes interview_state field."""
        state = taskmaster.create_initial_state("Build an app")

        assert "interview_state" in state
        assert state["interview_state"] is None
