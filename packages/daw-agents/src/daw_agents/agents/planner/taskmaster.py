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
    ROUNDTABLE = "roundtable"
    GENERATE_PRD = "generate_prd"
    COMPLETE = "complete"
    ERROR = "error"


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
        # If we have clarifications, proceed to roundtable
        # In a real implementation, this could check if user confirmed
        if state.get("clarifications"):
            return "roundtable"
        # Skip roundtable if no clarifications needed (simple request)
        return "generate_prd"

    async def _interview_node(self, state: PlannerState) -> dict[str, Any]:
        """Interview node: Ask clarifying questions.

        Args:
            state: Current planner state

        Returns:
            State updates with messages and clarifications
        """
        logger.info("Entering interview node")

        # Build conversation context
        conversation = "\n".join(
            f"{m['role']}: {m['content']}" for m in state.get("messages", [])
        )

        prompt = INTERVIEW_PROMPT.format(
            requirement=state["requirement"], conversation=conversation
        )

        try:
            response = await self._model_router.route(
                task_type=TaskType.PLANNING,
                messages=[
                    {"role": "system", "content": "You are a Product Manager."},
                    {"role": "user", "content": prompt},
                ],
            )

            # Add the assistant's questions to messages
            new_messages = list(state.get("messages", []))
            new_messages.append({"role": "assistant", "content": response})

            # In a real implementation, we'd wait for user response
            # For now, simulate a clarification
            clarifications = state.get("clarifications", [])
            if not clarifications:
                clarifications = [response]

            return {
                "messages": new_messages,
                "clarifications": clarifications,
                "status": PlannerStatus.INTERVIEW,
            }

        except Exception as e:
            logger.error("Interview node failed: %s", str(e))
            raise

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

        # Try to find JSON directly
        for start_char, end_char in [("{", "}"), ("[", "]")]:
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

    def create_initial_state(self, requirement: str) -> PlannerState:
        """Create initial state for the workflow.

        Args:
            requirement: User's requirement string

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
]
