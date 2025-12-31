"""
Taskmaster Agent - The Planner Agent for DAW Workbench.

This module implements the Taskmaster agent that:
1. Receives high-level user requirements
2. Interviews users to clarify requirements
3. Conducts roundtable discussions with synthetic personas (CTO, UX, Security)
4. Generates structured PRD documents
5. Decomposes PRDs into atomic, testable tasks

The agent uses LangGraph for state machine workflow with states:
- INTERVIEW: Clarify user requirements
- ROUNDTABLE: Get critiques from synthetic personas
- GENERATE_PRD: Create structured PRD
- COMPLETE: Final state with tasks

References:
- agents.md: Planner Agent specification
- docs/planning/tasks.json: Task schema
- prompts/planner/prd_generator_v1.yaml: PRD generation prompt
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from daw_agents.mcp.client import MCPClient
from daw_agents.memory.neo4j import Neo4jConnector
from daw_agents.models.router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Enums and State Models
# -----------------------------------------------------------------------------


class PlannerStatus(str, Enum):
    """Status values for the Planner state machine."""

    INTERVIEW = "interview"
    AWAITING_INTERVIEW = "awaiting_interview"
    ROUNDTABLE = "roundtable"
    GENERATE_PRD = "generate_prd"
    COMPLETE = "complete"
    ERROR = "error"


class QuestionType(str, Enum):
    """Types of interview questions."""

    TEXT = "text"
    MULTI_CHOICE = "multi_choice"
    CHECKBOX = "checkbox"


class Question(BaseModel):
    """Represents an interview question for user clarification.

    Attributes:
        id: Unique question identifier (e.g., Q-001)
        type: Question type (text, multi_choice, checkbox)
        text: The question text to display
        options: Available options for multi_choice/checkbox questions
        required: Whether the question must be answered
        context: Additional context to help user answer
    """

    id: str = Field(..., description="Unique question identifier (e.g., Q-001)")
    type: QuestionType = Field(
        default=QuestionType.TEXT, description="Question type"
    )
    text: str = Field(..., description="The question text to display")
    options: list[str] | None = Field(
        default=None, description="Available options for multi_choice/checkbox"
    )
    required: bool = Field(default=True, description="Whether answer is required")
    context: str | None = Field(
        default=None, description="Additional context to help user answer"
    )


class InterviewState(BaseModel):
    """State of an ongoing interview with the user.

    Tracks the progress of clarifying questions and user responses.

    Attributes:
        workflow_id: ID of the workflow this interview belongs to
        questions: List of questions to ask the user
        answers: Dictionary mapping question IDs to user answers
        current_index: Index of the current question being asked
        completed: Whether the interview is complete
    """

    workflow_id: str = Field(..., description="Workflow ID this interview belongs to")
    questions: list[Question] = Field(
        default_factory=list, description="Questions to ask"
    )
    answers: dict[str, str | list[str]] = Field(
        default_factory=dict, description="User answers keyed by question ID"
    )
    current_index: int = Field(default=0, description="Current question index")
    completed: bool = Field(default=False, description="Whether interview is complete")


class Task(BaseModel):
    """Represents an atomic task to be executed.

    Follows the schema from tasks.json.
    """

    id: str = Field(..., description="Unique task identifier (e.g., TASK-001)")
    description: str = Field(..., description="Task description")
    priority: str = Field(..., description="Priority level (P0, P1, P2)")
    type: str = Field(..., description="Task type (setup, code, test, docs)")
    dependencies: list[str] = Field(
        default_factory=list, description="List of task IDs this depends on"
    )
    estimated_hours: float | None = Field(
        default=None, description="Estimated hours to complete"
    )
    model_hint: str | None = Field(
        default=None, description="Suggested model type (planning, coding, etc.)"
    )
    verification: dict[str, Any] | None = Field(
        default=None, description="Verification criteria"
    )
    context_files: list[str] | None = Field(
        default=None, description="Relevant context files"
    )
    instruction: str | None = Field(
        default=None, description="Detailed instruction for the task"
    )


class UserStory(BaseModel):
    """Represents a user story in the PRD."""

    id: str = Field(..., description="Unique story ID (e.g., US-001)")
    description: str = Field(..., description="User story description")
    priority: str = Field(..., description="Priority level (P0, P1, P2)")
    acceptance_criteria: list[str] = Field(
        default_factory=list, description="Acceptance criteria"
    )


class PRDOutput(BaseModel):
    """Structured PRD output following the prd_generator schema."""

    title: str = Field(..., description="PRD title")
    overview: str = Field(..., description="High-level product overview")
    user_stories: list[dict[str, Any]] = Field(
        default_factory=list, description="User stories"
    )
    tech_specs: dict[str, Any] = Field(
        default_factory=dict, description="Technical specifications"
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list, description="Overall acceptance criteria"
    )


class RoundtablePersona(BaseModel):
    """Represents a synthetic persona for roundtable discussion."""

    name: str = Field(..., description="Persona name (e.g., CTO, UX, Security)")
    role: str = Field(..., description="Role description")
    focus: str = Field(..., description="Focus area for critique")
    critique_prompt: str = Field(..., description="Prompt template for critique")


class PlannerState(TypedDict):
    """State for the Planner LangGraph workflow.

    This TypedDict defines all fields maintained across nodes.
    """

    requirement: str
    messages: list[dict[str, str]]
    clarifications: list[str]
    roundtable_critiques: list[str]
    prd: PRDOutput | None
    tasks: list[Task]
    status: PlannerStatus
    error: str | None
    interview_state: InterviewState | None  # Added for interview flow


# -----------------------------------------------------------------------------
# Default Personas
# -----------------------------------------------------------------------------

DEFAULT_PERSONAS = [
    RoundtablePersona(
        name="CTO",
        role="Chief Technology Officer",
        focus="Technical architecture and scalability",
        critique_prompt="""As the CTO, evaluate this proposal from a technical perspective:
- Is the architecture scalable?
- Are there any technical debt concerns?
- What are the infrastructure requirements?
- Are there security architecture considerations?

Proposal:
{proposal}

Provide specific, actionable technical feedback.""",
    ),
    RoundtablePersona(
        name="UX",
        role="Head of User Experience",
        focus="User experience and accessibility",
        critique_prompt="""As the Head of UX, evaluate this proposal from a user experience perspective:
- Is the user flow intuitive?
- Are there accessibility concerns?
- What about mobile experience?
- How will users learn to use this?

Proposal:
{proposal}

Provide specific, actionable UX feedback.""",
    ),
    RoundtablePersona(
        name="Security",
        role="Chief Information Security Officer",
        focus="Security and compliance",
        critique_prompt="""As the CISO, evaluate this proposal from a security perspective:
- What are the authentication/authorization requirements?
- Are there data privacy concerns?
- What compliance requirements apply (GDPR, SOC2, etc.)?
- What security testing is needed?

Proposal:
{proposal}

Provide specific, actionable security feedback.""",
    ),
]


# -----------------------------------------------------------------------------
# Prompt Templates
# -----------------------------------------------------------------------------

INTERVIEW_PROMPT = """You are an expert Product Manager conducting a requirements interview.

USER REQUIREMENT:
{requirement}

PREVIOUS CONVERSATION:
{conversation}

Your task is to ask clarifying questions to better understand the user's needs.
Focus on:
1. Target users and use cases
2. Key features and priorities
3. Technical constraints
4. Timeline and budget considerations
5. Integration requirements

Ask 3-5 specific, targeted questions. Be professional and concise."""

QUESTION_GENERATION_PROMPT = """You are an expert Product Manager analyzing a user requirement to generate clarifying questions.

USER REQUIREMENT:
{requirement}

PREVIOUS CONVERSATION:
{conversation}

Generate structured interview questions in JSON format:
[
    {{
        "id": "Q-001",
        "type": "text|multi_choice|checkbox",
        "text": "The question to ask",
        "options": ["option1", "option2"],  // Only for multi_choice/checkbox
        "required": true,
        "context": "Why this question matters"
    }}
]

Guidelines:
- Generate 3-5 targeted questions
- Use "text" type for open-ended questions
- Use "multi_choice" when user should pick one option
- Use "checkbox" when user can select multiple options
- Mark P0 questions as required=true
- Include context to help user understand importance

Output ONLY valid JSON array, no additional text."""

PRD_GENERATION_PROMPT = """You are an expert Product Manager generating a structured PRD.

ORIGINAL REQUIREMENT:
{requirement}

CLARIFICATIONS FROM USER:
{clarifications}

ROUNDTABLE FEEDBACK:
{critiques}

Generate a complete PRD in JSON format with the following structure:
{{
    "title": "PRD title",
    "overview": "High-level product overview",
    "user_stories": [
        {{
            "id": "US-001",
            "description": "As a [user], I want [goal] so that [benefit]",
            "priority": "P0|P1|P2",
            "acceptance_criteria": ["criterion 1", "criterion 2"]
        }}
    ],
    "tech_specs": {{
        "architecture": "Architecture description",
        "technology_stack": ["tech1", "tech2"],
        "constraints": ["constraint1"]
    }},
    "acceptance_criteria": ["Overall criterion 1", "Overall criterion 2"]
}}

Ensure:
- At least one P0 user story
- All stories have acceptance criteria
- Tech specs include architecture decisions
- Address all roundtable feedback

Output ONLY valid JSON, no additional text."""

TASK_DECOMPOSITION_PROMPT = """You are a senior software architect decomposing a PRD into tasks.

PRD:
{prd}

Break down this PRD into atomic, testable tasks following this JSON structure:
[
    {{
        "id": "TASK-001",
        "description": "Task description",
        "priority": "P0|P1|P2",
        "type": "setup|code|test|docs",
        "dependencies": ["TASK-000"],
        "estimated_hours": 2.0,
        "model_hint": "coding|planning|validation|fast",
        "verification": {{
            "type": "test_pass|file_exists",
            "command": "pytest tests/..."
        }},
        "instruction": "Detailed implementation instructions"
    }}
]

Guidelines:
- Start with setup/infrastructure tasks
- Each coding task should have test coverage
- Consider dependencies carefully
- P0 tasks are critical path
- Estimate hours realistically

Output ONLY valid JSON array, no additional text."""


# -----------------------------------------------------------------------------
# Taskmaster Agent
# -----------------------------------------------------------------------------


class Taskmaster:
    """The Planner Agent that converts requirements into tasks.

    Implements a LangGraph workflow with states:
    1. INTERVIEW - Clarify user requirements
    2. ROUNDTABLE - Get critiques from synthetic personas
    3. GENERATE_PRD - Create structured PRD
    4. COMPLETE - Extract and prioritize tasks

    Attributes:
        workflow: Compiled LangGraph workflow
        _model_router: Model router for LLM selection
        _mcp_client: MCP client for tool access
        _neo4j: Neo4j connector for persistence
    """

    def __init__(
        self,
        model_router: ModelRouter | None = None,
        mcp_client: MCPClient | None = None,
        neo4j_connector: Neo4jConnector | None = None,
        personas: list[RoundtablePersona] | None = None,
    ) -> None:
        """Initialize the Taskmaster agent.

        Args:
            model_router: Optional custom model router. Uses default if None.
            mcp_client: Optional MCP client for tool access.
            neo4j_connector: Optional Neo4j connector for persistence.
            personas: Optional custom personas. Uses defaults if None.
        """
        self._model_router = model_router or ModelRouter()
        self._mcp_client = mcp_client
        self._neo4j = neo4j_connector
        self._personas = personas or DEFAULT_PERSONAS

        # Build and compile the LangGraph workflow
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> Any:
        """Build the LangGraph state machine workflow.

        Returns:
            Compiled StateGraph workflow.
        """
        # Create the state graph
        builder = StateGraph(PlannerState)

        # Add nodes
        builder.add_node("interview", self._interview_node)
        builder.add_node("roundtable", self._roundtable_node)
        builder.add_node("generate_prd", self._generate_prd_node)
        builder.add_node("decompose_tasks", self._decompose_tasks_node)

        # Add edges
        builder.add_edge(START, "interview")
        builder.add_conditional_edges(
            "interview",
            self._route_after_interview,
            {
                "roundtable": "roundtable",
                "generate_prd": "generate_prd",
            },
        )
        builder.add_edge("roundtable", "generate_prd")
        builder.add_edge("generate_prd", "decompose_tasks")
        builder.add_edge("decompose_tasks", END)

        return builder.compile()

    def _route_after_interview(self, state: PlannerState) -> str:
        """Route after interview based on whether we have enough clarifications.

        Args:
            state: Current planner state

        Returns:
            Next node name ("roundtable" or "generate_prd")
        """
        # Check if interview is completed
        interview_state = state.get("interview_state")
        if interview_state and not interview_state.completed:
            # Still awaiting user responses - this shouldn't happen in normal flow
            # as we pause workflow when awaiting interview
            return "generate_prd"

        # If we have clarifications, proceed to roundtable
        if state.get("clarifications"):
            return "roundtable"
        # Skip roundtable if no clarifications needed (simple request)
        return "generate_prd"

    async def _interview_node(self, state: PlannerState) -> dict[str, Any]:
        """Interview node: Generate or process clarifying questions.

        This node handles the interview flow in two modes:
        1. Initial entry: Generate questions and return AWAITING_INTERVIEW status
        2. Resume with answers: Process answers and proceed to next step

        Args:
            state: Current planner state

        Returns:
            State updates with messages, clarifications, and interview_state
        """
        logger.info("Entering interview node")

        interview_state = state.get("interview_state")

        # Check if we're resuming with completed answers
        if interview_state and interview_state.completed:
            logger.info("Interview completed, processing answers")
            return await self._process_interview_answers(state, interview_state)

        # Check if we have an existing interview in progress with answers
        if interview_state and interview_state.answers:
            # User provided some answers, check if complete
            required_answered = all(
                q.id in interview_state.answers
                for q in interview_state.questions
                if q.required
            )
            if required_answered:
                # Mark as completed and process
                updated_interview = InterviewState(
                    workflow_id=interview_state.workflow_id,
                    questions=interview_state.questions,
                    answers=interview_state.answers,
                    current_index=len(interview_state.questions),
                    completed=True,
                )
                return await self._process_interview_answers(state, updated_interview)

        # Generate new questions if no interview state exists
        return await self._generate_interview_questions(state)

    async def _generate_interview_questions(
        self, state: PlannerState
    ) -> dict[str, Any]:
        """Generate interview questions based on the requirement.

        Args:
            state: Current planner state

        Returns:
            State updates with interview questions and AWAITING_INTERVIEW status
        """
        logger.info("Generating interview questions")

        # Build conversation context
        conversation = "\n".join(
            f"{m['role']}: {m['content']}" for m in state.get("messages", [])
        )

        prompt = QUESTION_GENERATION_PROMPT.format(
            requirement=state["requirement"], conversation=conversation
        )

        try:
            response = await self._model_router.route(
                task_type=TaskType.PLANNING,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Product Manager. Output valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            # Parse the questions from JSON response
            questions_data = json.loads(self._extract_json(response))

            # Ensure questions_data is a list
            if not isinstance(questions_data, list):
                raise ValueError("Expected JSON array of questions")

            questions = []
            for i, q_data in enumerate(questions_data):
                # Skip invalid entries (non-dict items)
                if not isinstance(q_data, dict):
                    continue

                # Normalize the type field
                q_type = q_data.get("type", "text")
                if q_type not in ["text", "multi_choice", "checkbox"]:
                    q_type = "text"

                questions.append(
                    Question(
                        id=q_data.get("id", f"Q-{i + 1:03d}"),
                        type=QuestionType(q_type),
                        text=q_data.get("text", ""),
                        options=q_data.get("options"),
                        required=q_data.get("required", True),
                        context=q_data.get("context"),
                    )
                )

            # Create interview state
            # Generate a workflow_id if not present (for standalone usage)
            workflow_id = state.get("workflow_id", "standalone")
            interview = InterviewState(
                workflow_id=workflow_id,
                questions=questions,
                answers={},
                current_index=0,
                completed=False,
            )

            # Add the questions to messages
            new_messages = list(state.get("messages", []))
            questions_text = "\n".join(
                f"Q{i + 1}: {q.text}" for i, q in enumerate(questions)
            )
            new_messages.append({"role": "assistant", "content": questions_text})

            return {
                "messages": new_messages,
                "status": PlannerStatus.AWAITING_INTERVIEW,
                "interview_state": interview,
            }

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse questions JSON, falling back: %s", str(e))
            # Fallback: Create a single text question
            interview = InterviewState(
                workflow_id=state.get("workflow_id", "standalone"),
                questions=[
                    Question(
                        id="Q-001",
                        type=QuestionType.TEXT,
                        text="Please provide more details about your requirements.",
                        required=True,
                        context="We need more information to proceed.",
                    )
                ],
                answers={},
                current_index=0,
                completed=False,
            )
            return {
                "status": PlannerStatus.AWAITING_INTERVIEW,
                "interview_state": interview,
            }
        except Exception as e:
            logger.error("Interview question generation failed: %s", str(e))
            raise

    async def _process_interview_answers(
        self, state: PlannerState, interview_state: InterviewState
    ) -> dict[str, Any]:
        """Process completed interview answers and prepare clarifications.

        Args:
            state: Current planner state
            interview_state: Completed interview state with answers

        Returns:
            State updates with clarifications derived from answers
        """
        logger.info("Processing interview answers")

        # Build clarifications from answers
        clarifications: list[str] = []
        for question in interview_state.questions:
            answer = interview_state.answers.get(question.id)
            if answer:
                if isinstance(answer, list):
                    answer_text = ", ".join(answer)
                else:
                    answer_text = answer
                clarifications.append(f"{question.text}: {answer_text}")

        # Update messages with the Q&A
        new_messages = list(state.get("messages", []))
        qa_summary = "\n".join(clarifications)
        new_messages.append({"role": "user", "content": f"Answers:\n{qa_summary}"})

        # Mark interview as completed
        completed_interview = InterviewState(
            workflow_id=interview_state.workflow_id,
            questions=interview_state.questions,
            answers=interview_state.answers,
            current_index=len(interview_state.questions),
            completed=True,
        )

        return {
            "messages": new_messages,
            "clarifications": clarifications,
            "status": PlannerStatus.INTERVIEW,
            "interview_state": completed_interview,
        }

    def submit_interview_answer(
        self,
        state: PlannerState,
        question_id: str,
        answer: str | list[str],
    ) -> PlannerState:
        """Submit an answer to an interview question.

        This method is called by the API to submit user answers.

        Args:
            state: Current planner state
            question_id: ID of the question being answered
            answer: User's answer (string or list for checkbox)

        Returns:
            Updated PlannerState with the answer recorded

        Raises:
            ValueError: If no interview is in progress or question not found
        """
        interview_state = state.get("interview_state")
        if not interview_state:
            raise ValueError("No interview in progress")

        # Verify question exists
        question_ids = [q.id for q in interview_state.questions]
        if question_id not in question_ids:
            raise ValueError(f"Question {question_id} not found in interview")

        # Add the answer
        new_answers = dict(interview_state.answers)
        new_answers[question_id] = answer

        # Calculate new current index
        current_idx = interview_state.current_index
        for i, q in enumerate(interview_state.questions):
            if q.id == question_id and i >= current_idx:
                current_idx = i + 1
                break

        # Check if all required questions are answered
        all_required_answered = all(
            q.id in new_answers for q in interview_state.questions if q.required
        )

        updated_interview = InterviewState(
            workflow_id=interview_state.workflow_id,
            questions=interview_state.questions,
            answers=new_answers,
            current_index=current_idx,
            completed=all_required_answered,
        )

        # Return updated state
        new_state: PlannerState = {
            **state,
            "interview_state": updated_interview,
        }

        # If completed, update status to continue workflow
        if updated_interview.completed:
            new_state["status"] = PlannerStatus.INTERVIEW

        return new_state

    def skip_remaining_questions(self, state: PlannerState) -> PlannerState:
        """Skip all remaining optional questions and complete interview.

        Args:
            state: Current planner state

        Returns:
            Updated PlannerState with interview marked complete

        Raises:
            ValueError: If required questions are unanswered
        """
        interview_state = state.get("interview_state")
        if not interview_state:
            raise ValueError("No interview in progress")

        # Check if all required questions are answered
        unanswered_required = [
            q
            for q in interview_state.questions
            if q.required and q.id not in interview_state.answers
        ]

        if unanswered_required:
            raise ValueError(
                f"Cannot skip: {len(unanswered_required)} required questions unanswered"
            )

        # Mark as completed
        updated_interview = InterviewState(
            workflow_id=interview_state.workflow_id,
            questions=interview_state.questions,
            answers=interview_state.answers,
            current_index=len(interview_state.questions),
            completed=True,
        )

        new_state: PlannerState = {
            **state,
            "interview_state": updated_interview,
            "status": PlannerStatus.INTERVIEW,
        }

        return new_state

    def get_current_question(self, state: PlannerState) -> Question | None:
        """Get the current question waiting for an answer.

        Args:
            state: Current planner state

        Returns:
            Current Question or None if interview complete or not started
        """
        interview_state = state.get("interview_state")
        if not interview_state or interview_state.completed:
            return None

        if interview_state.current_index >= len(interview_state.questions):
            return None

        return interview_state.questions[interview_state.current_index]

    def get_next_unanswered_question(self, state: PlannerState) -> Question | None:
        """Get the next unanswered question.

        Args:
            state: Current planner state

        Returns:
            Next unanswered Question or None if all answered
        """
        interview_state = state.get("interview_state")
        if not interview_state or interview_state.completed:
            return None

        for question in interview_state.questions:
            if question.id not in interview_state.answers:
                return question

        return None

    async def _roundtable_node(self, state: PlannerState) -> dict[str, Any]:
        """Roundtable node: Collect critiques from synthetic personas.

        Args:
            state: Current planner state

        Returns:
            State updates with roundtable_critiques
        """
        logger.info("Entering roundtable node")

        # Build proposal from messages
        proposal = state["requirement"]
        if state.get("clarifications"):
            proposal += "\n\nClarifications:\n" + "\n".join(state["clarifications"])

        critiques: list[str] = []

        for persona in self._personas:
            try:
                prompt = persona.critique_prompt.format(proposal=proposal)

                response = await self._model_router.route(
                    task_type=TaskType.PLANNING,
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are {persona.name}, {persona.role}. "
                            f"Focus on: {persona.focus}",
                        },
                        {"role": "user", "content": prompt},
                    ],
                )

                critiques.append(f"{persona.name}: {response}")
                logger.debug("Got critique from %s", persona.name)

            except Exception as e:
                logger.warning("Failed to get critique from %s: %s", persona.name, e)
                critiques.append(f"{persona.name}: (critique unavailable)")

        return {
            "roundtable_critiques": critiques,
            "status": PlannerStatus.ROUNDTABLE,
        }

    async def _generate_prd_node(self, state: PlannerState) -> dict[str, Any]:
        """Generate PRD node: Create structured PRD from requirements.

        Args:
            state: Current planner state

        Returns:
            State updates with prd
        """
        logger.info("Entering generate_prd node")

        clarifications_text = "\n".join(state.get("clarifications", []))
        critiques_text = "\n".join(state.get("roundtable_critiques", []))

        prompt = PRD_GENERATION_PROMPT.format(
            requirement=state["requirement"],
            clarifications=clarifications_text or "None provided",
            critiques=critiques_text or "None provided",
        )

        try:
            response = await self._model_router.route(
                task_type=TaskType.PLANNING,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Product Manager. Output valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            # Parse the JSON response
            prd_data = json.loads(self._extract_json(response))
            prd = PRDOutput(**prd_data)

            return {
                "prd": prd,
                "status": PlannerStatus.GENERATE_PRD,
            }

        except json.JSONDecodeError as e:
            logger.error("Failed to parse PRD JSON: %s", str(e))
            # Return a minimal PRD
            prd = PRDOutput(
                title=f"PRD for: {state['requirement'][:50]}",
                overview=state["requirement"],
                user_stories=[],
                tech_specs={},
                acceptance_criteria=[],
            )
            return {
                "prd": prd,
                "status": PlannerStatus.GENERATE_PRD,
                "error": f"PRD parsing error: {str(e)}",
            }
        except Exception as e:
            logger.error("Generate PRD failed: %s", str(e))
            raise

    async def _decompose_tasks_node(self, state: PlannerState) -> dict[str, Any]:
        """Decompose tasks node: Break PRD into atomic tasks.

        Args:
            state: Current planner state

        Returns:
            State updates with tasks
        """
        logger.info("Entering decompose_tasks node")

        prd = state.get("prd")
        if not prd:
            return {
                "tasks": [],
                "status": PlannerStatus.COMPLETE,
                "error": "No PRD to decompose",
            }

        prd_json = prd.model_dump_json()

        prompt = TASK_DECOMPOSITION_PROMPT.format(prd=prd_json)

        try:
            response = await self._model_router.route(
                task_type=TaskType.PLANNING,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a software architect. Output valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            # Parse tasks
            tasks_data = json.loads(self._extract_json(response))
            tasks = [Task(**t) for t in tasks_data]

            # Prioritize tasks
            ordered_tasks = self.prioritize(tasks)

            # Assign metadata to tasks without it
            enhanced_tasks = [self.assign_metadata(t) for t in ordered_tasks]

            # Persist conversation if Neo4j is available
            if self._neo4j:
                await self._persist_conversation(state)

            return {
                "tasks": enhanced_tasks,
                "status": PlannerStatus.COMPLETE,
            }

        except json.JSONDecodeError as e:
            logger.error("Failed to parse tasks JSON: %s", str(e))
            return {
                "tasks": [],
                "status": PlannerStatus.COMPLETE,
                "error": f"Task parsing error: {str(e)}",
            }
        except Exception as e:
            logger.error("Decompose tasks failed: %s", str(e))
            raise

    def _extract_json(self, text: str) -> str:
        """Extract JSON from a text response that may contain markdown.

        Args:
            text: Raw text that may contain JSON

        Returns:
            Extracted JSON string
        """
        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Try to find JSON directly - prioritize whichever delimiter appears first
        bracket_idx = text.find("[")
        brace_idx = text.find("{")

        # Determine which appears first and use appropriate parsing order
        if bracket_idx >= 0 and (brace_idx < 0 or bracket_idx < brace_idx):
            # Array appears first
            pairs = [("[", "]"), ("{", "}")]
        else:
            # Object appears first or only object exists
            pairs = [("{", "}"), ("[", "]")]

        for start_char, end_char in pairs:
            start = text.find(start_char)
            if start >= 0:
                # Find matching end
                depth = 0
                for i, char in enumerate(text[start:], start):
                    if char == start_char:
                        depth += 1
                    elif char == end_char:
                        depth -= 1
                        if depth == 0:
                            return text[start : i + 1]

        return text

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def create_initial_state(
        self, requirement: str, workflow_id: str | None = None
    ) -> PlannerState:
        """Create initial state for the workflow.

        Args:
            requirement: User's requirement string
            workflow_id: Optional workflow ID for tracking

        Returns:
            Initial PlannerState
        """
        return {
            "requirement": requirement,
            "messages": [{"role": "user", "content": requirement}],
            "clarifications": [],
            "roundtable_critiques": [],
            "prd": None,
            "tasks": [],
            "status": PlannerStatus.INTERVIEW,
            "error": None,
            "interview_state": None,
        }

    async def plan(self, requirement: str) -> list[Task]:
        """Execute the full planning workflow.

        Takes a high-level requirement and returns a list of atomic tasks.

        Args:
            requirement: User's requirement string

        Returns:
            List of prioritized Tasks

        Raises:
            Exception: If workflow execution fails
        """
        logger.info("Starting planning workflow for: %s", requirement[:100])

        initial_state = self.create_initial_state(requirement)

        try:
            final_state = await self.workflow.ainvoke(initial_state)
            tasks: list[Task] = final_state["tasks"]
            return tasks

        except Exception as e:
            logger.error("Planning workflow failed: %s", str(e))
            raise

    def get_personas(self) -> list[RoundtablePersona]:
        """Get the configured roundtable personas.

        Returns:
            List of RoundtablePersona objects
        """
        return self._personas

    def prioritize(self, tasks: list[Task]) -> list[Task]:
        """Order tasks by dependency and priority.

        Uses topological sort to respect dependencies,
        then sorts by priority within each level.

        Args:
            tasks: Unsorted list of tasks

        Returns:
            Topologically sorted tasks respecting dependencies and priority
        """
        if not tasks:
            return []

        # Build dependency graph
        task_map = {t.id: t for t in tasks}
        in_degree: dict[str, int] = {t.id: 0 for t in tasks}
        dependents: dict[str, list[str]] = {t.id: [] for t in tasks}

        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in task_map:
                    in_degree[task.id] += 1
                    dependents[dep_id].append(task.id)

        # Topological sort with priority
        result: list[Task] = []
        priority_order = {"P0": 0, "P1": 1, "P2": 2}

        # Get all tasks with no dependencies
        ready = [t for t in tasks if in_degree[t.id] == 0]
        ready.sort(key=lambda t: priority_order.get(t.priority, 3))

        while ready:
            # Take highest priority task
            current = ready.pop(0)
            result.append(current)

            # Update dependents
            for dep_id in dependents[current.id]:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    ready.append(task_map[dep_id])
                    ready.sort(key=lambda t: priority_order.get(t.priority, 3))

        # Add any remaining tasks (cyclic dependencies)
        remaining = [t for t in tasks if t not in result]
        remaining.sort(key=lambda t: priority_order.get(t.priority, 3))
        result.extend(remaining)

        return result

    def assign_metadata(self, task: Task) -> Task:
        """Assign metadata to a task if not already set.

        Adds model_hint and estimated_hours based on task type.

        Args:
            task: Task to enhance

        Returns:
            Task with metadata assigned
        """
        # Create a copy with potential updates
        task_dict = task.model_dump()

        # Assign model_hint based on task type
        if task.model_hint is None:
            type_to_hint = {
                "setup": "fast",
                "code": "coding",
                "test": "coding",
                "docs": "fast",
                "config": "fast",
                "review": "validation",
            }
            task_dict["model_hint"] = type_to_hint.get(task.type, "coding")

        # Estimate hours based on priority and type
        if task.estimated_hours is None:
            base_hours = {
                "setup": 0.5,
                "code": 2.0,
                "test": 1.0,
                "docs": 0.5,
                "config": 0.5,
            }
            priority_multiplier = {
                "P0": 1.5,
                "P1": 1.0,
                "P2": 0.75,
            }
            base = base_hours.get(task.type, 1.5)
            multiplier = priority_multiplier.get(task.priority, 1.0)
            task_dict["estimated_hours"] = round(base * multiplier, 1)

        return Task(**task_dict)

    def _get_next_status(self, state: PlannerState) -> PlannerStatus:
        """Determine the next status based on current state.

        Used for state transition logic.

        Args:
            state: Current planner state

        Returns:
            Next PlannerStatus value
        """
        current = state["status"]

        if current == PlannerStatus.INTERVIEW:
            # Move to roundtable if we have clarifications
            if state.get("clarifications"):
                return PlannerStatus.ROUNDTABLE
            return PlannerStatus.GENERATE_PRD

        if current == PlannerStatus.ROUNDTABLE:
            return PlannerStatus.GENERATE_PRD

        if current == PlannerStatus.GENERATE_PRD:
            return PlannerStatus.COMPLETE

        return current

    async def _persist_conversation(self, state: PlannerState) -> None:
        """Persist the conversation to Neo4j.

        Args:
            state: Current planner state
        """
        if self._neo4j is None:
            return

        try:
            # Create conversation node
            await self._neo4j.create_node(
                labels=["Conversation", "Planning"],
                properties={
                    "requirement": state["requirement"],
                    "clarifications": state.get("clarifications", []),
                    "status": state["status"],
                },
            )
            logger.debug("Persisted conversation to Neo4j")
        except Exception as e:
            logger.warning("Failed to persist conversation: %s", str(e))


__all__ = [
    "Taskmaster",
    "Task",
    "PRDOutput",
    "PlannerState",
    "PlannerStatus",
    "RoundtablePersona",
    "Question",
    "QuestionType",
    "InterviewState",
]
