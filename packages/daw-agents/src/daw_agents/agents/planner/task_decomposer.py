"""Task Decomposition Agent for DAW Workbench.

This module implements the TaskDecomposer that:
1. Parses PRD markdown into structured tasks
2. Uses complexity scores from ComplexityAnalyzer to size tasks
3. Generates task IDs (e.g., FEATURE-001, BUG-001)
4. Infers dependencies between tasks
5. Assigns context_files based on task content
6. Creates verification criteria for each task
7. Outputs tasks.json compatible format
8. Validates all tasks before emitting

Task: TASK-DECOMP-001
Dependencies: PLANNER-001 (Taskmaster), COMPLEXITY-001 (ComplexityAnalyzer)
Reference: FR-02.4 in PRD

Example usage:
    ```python
    decomposer = TaskDecomposer()
    result = await decomposer.decompose_prd(prd_markdown)
    tasks_json = result.to_tasks_json()
    ```
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from daw_agents.agents.planner.complexity_analyzer import (
    ComplexityAnalysis,
    ComplexityAnalyzer,
    ComplexityScore,
    DependencyGraph,
    RiskRating,
)
from daw_agents.agents.planner.taskmaster import PRDOutput
from daw_agents.models.router import ModelRouter
from daw_agents.models.router import TaskType as RouterTaskType

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class TaskPriority(str, Enum):
    """Task priority levels matching tasks.json schema."""

    P0 = "P0"  # Critical path
    P1 = "P1"  # Important
    P2 = "P2"  # Nice to have


class DecomposedTaskType(str, Enum):
    """Task type values matching tasks.json schema."""

    SETUP = "setup"
    CODE = "code"
    TEST = "test"
    DOCS = "docs"
    CONFIG = "config"


# Alias for compatibility (exported as TaskType)
TaskType = DecomposedTaskType


class VerificationType(str, Enum):
    """Verification type for tasks."""

    TEST_PASS = "test_pass"
    FILE_EXISTS = "file_exists"
    MANUAL = "manual"


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class TaskVerification(BaseModel):
    """Verification criteria for a task.

    Matches the verification field in tasks.json schema.
    """

    type: VerificationType = Field(..., description="Type of verification")
    command: str | None = Field(
        default=None, description="Command to run for test_pass type"
    )
    path: str | None = Field(
        default=None, description="Path to check for file_exists type"
    )

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Serialize to dict, excluding None values."""
        data = super().model_dump(**kwargs)
        # Convert enum to string value
        data["type"] = self.type.value
        # Remove None values for cleaner output
        return {k: v for k, v in data.items() if v is not None}


class DecomposedTask(BaseModel):
    """Represents a decomposed task matching tasks.json schema.

    All fields are designed to be compatible with the existing
    tasks.json format used by the DAW workbench.
    """

    id: str = Field(..., description="Unique task ID (e.g., FEATURE-001)")
    description: str = Field(..., description="Task description")
    priority: TaskPriority = Field(..., description="Priority level")
    type: DecomposedTaskType = Field(..., description="Task type")
    dependencies: list[str] = Field(
        default_factory=list, description="List of task IDs this depends on"
    )
    context_files: list[str] = Field(
        default_factory=list, description="Relevant context files"
    )
    verification: TaskVerification | None = Field(
        default=None, description="Verification criteria"
    )
    estimated_hours: float | None = Field(
        default=None, description="Estimated hours to complete"
    )
    model_hint: str | None = Field(
        default=None, description="Suggested model type"
    )
    instruction: str | None = Field(
        default=None, description="Detailed implementation instruction"
    )

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Serialize to dict with proper enum handling."""
        data = super().model_dump(**kwargs)
        # Convert enums to string values
        data["priority"] = self.priority.value
        data["type"] = self.type.value
        # Handle verification separately
        if self.verification:
            data["verification"] = self.verification.model_dump()
        else:
            data.pop("verification", None)
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}


class DecompositionResult(BaseModel):
    """Result of PRD decomposition.

    Contains all decomposed tasks and metadata.
    """

    prd_title: str = Field(..., description="Title of the analyzed PRD")
    tasks: list[DecomposedTask] = Field(
        default_factory=list, description="Decomposed tasks"
    )
    total_estimated_hours: float = Field(
        default=0.0, description="Total estimated hours"
    )

    def to_json(self) -> str:
        """Serialize the result to JSON format.

        Returns:
            JSON string representation
        """
        return json.dumps(
            {
                "prd_title": self.prd_title,
                "tasks": [t.model_dump() for t in self.tasks],
                "total_estimated_hours": self.total_estimated_hours,
            },
            indent=2,
        )

    def to_tasks_json(self) -> list[dict[str, Any]]:
        """Convert to tasks.json compatible format.

        Returns:
            List of task dictionaries matching tasks.json schema
        """
        return [task.model_dump() for task in self.tasks]


class TaskDecomposerConfig(BaseModel):
    """Configuration for TaskDecomposer.

    Controls various aspects of task generation.
    """

    max_tasks_per_feature: int = Field(
        default=5, description="Maximum tasks per feature"
    )
    min_task_hours: float = Field(
        default=0.5, description="Minimum hours per task"
    )
    max_task_hours: float = Field(
        default=8.0, description="Maximum hours per task"
    )
    id_prefix: str = Field(
        default="TASK", description="Default prefix for task IDs"
    )
    include_setup_tasks: bool = Field(
        default=True, description="Include setup/infrastructure tasks"
    )
    include_test_tasks: bool = Field(
        default=True, description="Include test writing tasks"
    )


# -----------------------------------------------------------------------------
# Prompt Templates
# -----------------------------------------------------------------------------


TASK_DECOMPOSITION_PROMPT = """You are an expert software architect decomposing a PRD into atomic, testable tasks.

PRD:
{prd}

COMPLEXITY ANALYSIS:
{complexity_analysis}

Break down this PRD into atomic, testable tasks following this JSON structure:
[
    {{
        "id": "TASK-001",
        "description": "Clear, actionable task description",
        "priority": "P0|P1|P2",
        "type": "setup|code|test|docs|config",
        "dependencies": ["TASK-000"],
        "context_files": ["src/path/to/file.py"],
        "verification": {{
            "type": "test_pass|file_exists",
            "command": "pytest tests/..."
        }},
        "instruction": "Detailed implementation instructions"
    }}
]

Guidelines:
1. Start with setup/infrastructure tasks (type: "setup")
2. Each feature should have corresponding test tasks (type: "test")
3. Use complexity scores to size tasks appropriately:
   - cognitive_load 1-3: simple task, 0.5-1 hour
   - cognitive_load 4-6: medium task, 1-3 hours
   - cognitive_load 7-8: complex task, 3-5 hours
   - cognitive_load 9-10: very complex task, 5-8 hours
4. Order dependencies correctly (setup before code, code before test)
5. Assign P0 to critical path tasks, P1 to important, P2 to nice-to-have
6. Include context_files for each coding task
7. Include verification criteria (prefer test_pass over file_exists)

Output ONLY valid JSON array, no additional text."""


# -----------------------------------------------------------------------------
# TaskDecomposer
# -----------------------------------------------------------------------------


class TaskDecomposer:
    """Decomposes PRD documents into atomic, testable tasks.

    Integrates with:
    - PLANNER-001 (Taskmaster): Accepts PRDOutput
    - COMPLEXITY-001 (ComplexityAnalyzer): Uses complexity scores for sizing

    Example:
        ```python
        decomposer = TaskDecomposer()
        result = await decomposer.decompose_prd(prd_markdown)
        for task in result.tasks:
            print(f"{task.id}: {task.description}")
        ```
    """

    # Type to model hint mapping
    TYPE_TO_HINT: dict[DecomposedTaskType, str] = {
        DecomposedTaskType.SETUP: "fast",
        DecomposedTaskType.CODE: "coding",
        DecomposedTaskType.TEST: "coding",
        DecomposedTaskType.DOCS: "fast",
        DecomposedTaskType.CONFIG: "fast",
    }

    # Complexity to hours mapping (base hours)
    COMPLEXITY_HOURS: dict[int, float] = {
        1: 0.5,
        2: 0.5,
        3: 1.0,
        4: 1.5,
        5: 2.0,
        6: 3.0,
        7: 4.0,
        8: 5.0,
        9: 6.0,
        10: 8.0,
    }

    def __init__(
        self,
        model_router: ModelRouter | None = None,
        complexity_analyzer: ComplexityAnalyzer | None = None,
        config: TaskDecomposerConfig | None = None,
    ) -> None:
        """Initialize the TaskDecomposer.

        Args:
            model_router: Optional custom model router. Creates default if None.
            complexity_analyzer: Optional complexity analyzer.
            config: Optional configuration. Uses defaults if None.
        """
        self._model_router = model_router or ModelRouter()
        self._complexity_analyzer = complexity_analyzer or ComplexityAnalyzer(
            model_router=self._model_router
        )
        self._config = config or TaskDecomposerConfig()
        self._task_counter: dict[str, int] = {}

    async def decompose_prd(self, prd: str) -> DecompositionResult:
        """Decompose a PRD markdown into atomic tasks.

        This is the main entry point that:
        1. Analyzes PRD complexity
        2. Extracts features and dependencies
        3. Generates atomic tasks
        4. Assigns metadata (hours, model hints, verification)
        5. Validates all tasks

        Args:
            prd: PRD markdown content

        Returns:
            DecompositionResult with all tasks
        """
        logger.info("Starting PRD decomposition")

        # Step 1: Get complexity analysis
        complexity_analysis = await self._complexity_analyzer.analyze_prd(prd)

        # Step 2: Generate tasks using LLM
        raw_tasks = await self._generate_tasks(prd, complexity_analysis)

        # Step 3: Parse and validate tasks
        tasks = self._parse_tasks(raw_tasks)

        # Step 4: Enrich with dependencies from complexity graph
        tasks = self.infer_dependencies(tasks, complexity_analysis.dependency_graph)

        # Step 5: Assign metadata
        tasks = self._enrich_tasks(tasks, complexity_analysis)

        # Step 6: Order tasks by dependencies
        tasks = self._order_tasks(tasks)

        # Step 7: Calculate total hours
        total_hours = sum(t.estimated_hours or 0 for t in tasks)

        result = DecompositionResult(
            prd_title=complexity_analysis.prd_title,
            tasks=tasks,
            total_estimated_hours=total_hours,
        )

        logger.info(
            "PRD decomposition complete: %d tasks, %.1f hours",
            len(tasks),
            total_hours,
        )

        return result

    async def decompose_prd_output(self, prd_output: PRDOutput) -> DecompositionResult:
        """Decompose a PRDOutput object into tasks.

        Convenience method for integration with Taskmaster.

        Args:
            prd_output: PRDOutput from Taskmaster

        Returns:
            DecompositionResult with all tasks
        """
        # Convert PRDOutput to markdown-like format
        prd_content = self._prd_output_to_markdown(prd_output)
        return await self.decompose_prd(prd_content)

    def _prd_output_to_markdown(self, prd_output: PRDOutput) -> str:
        """Convert PRDOutput to markdown format.

        Args:
            prd_output: PRDOutput object

        Returns:
            Markdown string representation
        """
        lines = [
            f"# {prd_output.title}",
            "",
            "## Overview",
            prd_output.overview,
            "",
            "## User Stories",
        ]

        for story in prd_output.user_stories:
            story_id = story.get("id", "US-XXX")
            description = story.get("description", "")
            priority = story.get("priority", "P1")
            lines.append(f"### {story_id}: {description} ({priority})")
            for criterion in story.get("acceptance_criteria", []):
                lines.append(f"- {criterion}")
            lines.append("")

        lines.append("## Tech Specs")
        if prd_output.tech_specs:
            for key, value in prd_output.tech_specs.items():
                if isinstance(value, list):
                    lines.append(f"- {key}: {', '.join(value)}")
                else:
                    lines.append(f"- {key}: {value}")

        return "\n".join(lines)

    async def _generate_tasks(
        self, prd: str, complexity_analysis: ComplexityAnalysis
    ) -> str:
        """Generate tasks using LLM.

        Args:
            prd: PRD content
            complexity_analysis: Complexity analysis result

        Returns:
            Raw JSON string from LLM
        """
        complexity_json = complexity_analysis.to_json()

        prompt = TASK_DECOMPOSITION_PROMPT.format(
            prd=prd,
            complexity_analysis=complexity_json,
        )

        try:
            response = await self._model_router.route(
                task_type=RouterTaskType.PLANNING,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a software architect. Output valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return response
        except Exception as e:
            logger.error("Task generation failed: %s", str(e))
            raise

    def _parse_tasks(self, raw_json: str) -> list[DecomposedTask]:
        """Parse raw JSON into DecomposedTask objects.

        Args:
            raw_json: Raw JSON string from LLM

        Returns:
            List of DecomposedTask objects
        """
        try:
            json_str = self._extract_json(raw_json)
            task_data = json.loads(json_str)

            if not isinstance(task_data, list):
                task_data = [task_data]

            tasks: list[DecomposedTask] = []
            for data in task_data:
                try:
                    # Parse priority
                    priority_str = data.get("priority", "P1")
                    priority = TaskPriority(priority_str)

                    # Parse type
                    type_str = data.get("type", "code")
                    task_type = DecomposedTaskType(type_str)

                    # Parse verification if present
                    verification = None
                    if "verification" in data and data["verification"]:
                        ver_data = data["verification"]
                        ver_type = VerificationType(ver_data.get("type", "test_pass"))
                        verification = TaskVerification(
                            type=ver_type,
                            command=ver_data.get("command"),
                            path=ver_data.get("path"),
                        )

                    task = DecomposedTask(
                        id=data.get("id", self.generate_task_id("TASK", len(tasks) + 1)),
                        description=data.get("description", ""),
                        priority=priority,
                        type=task_type,
                        dependencies=data.get("dependencies", []),
                        context_files=data.get("context_files", []),
                        verification=verification,
                        estimated_hours=data.get("estimated_hours"),
                        model_hint=data.get("model_hint"),
                        instruction=data.get("instruction"),
                    )
                    tasks.append(task)
                except Exception as e:
                    logger.warning("Failed to parse task: %s - %s", data, str(e))

            return tasks

        except json.JSONDecodeError as e:
            logger.error("Failed to parse tasks JSON: %s", str(e))
            return []

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown.

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

        # Try to find JSON array directly
        if "[" in text:
            start = text.find("[")
            depth = 0
            for i, char in enumerate(text[start:], start):
                if char == "[":
                    depth += 1
                elif char == "]":
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]

        return text

    def _enrich_tasks(
        self, tasks: list[DecomposedTask], complexity: ComplexityAnalysis
    ) -> list[DecomposedTask]:
        """Enrich tasks with metadata from complexity analysis.

        Args:
            tasks: List of parsed tasks
            complexity: Complexity analysis result

        Returns:
            Enriched tasks
        """
        # Build feature name to complexity map
        feature_scores: dict[str, ComplexityScore] = {
            score.feature.lower(): score for score in complexity.features
        }

        enriched = []
        for task in tasks:
            # Find matching complexity score
            matching_score = None
            task_lower = task.description.lower()
            for feature_name, score in feature_scores.items():
                if feature_name in task_lower or task_lower in feature_name:
                    matching_score = score
                    break

            # Assign estimated hours if not set
            if task.estimated_hours is None:
                if matching_score:
                    task.estimated_hours = self.estimate_hours(matching_score)
                else:
                    # Default based on task type
                    task.estimated_hours = self._default_hours(task.type)

            # Assign model hint if not set
            if task.model_hint is None:
                task.model_hint = self.assign_model_hint(task)

            # Assign context files if empty
            if not task.context_files:
                task.context_files = self.infer_context_files(task)

            # Assign verification if not set
            if task.verification is None:
                task.verification = self.generate_verification(task)

            enriched.append(task)

        return enriched

    def _default_hours(self, task_type: DecomposedTaskType) -> float:
        """Get default hours for a task type.

        Args:
            task_type: Type of task

        Returns:
            Default hours estimate
        """
        defaults = {
            DecomposedTaskType.SETUP: 1.0,
            DecomposedTaskType.CODE: 3.0,
            DecomposedTaskType.TEST: 2.0,
            DecomposedTaskType.DOCS: 1.0,
            DecomposedTaskType.CONFIG: 0.5,
        }
        return defaults.get(task_type, 2.0)

    def _order_tasks(self, tasks: list[DecomposedTask]) -> list[DecomposedTask]:
        """Order tasks by dependencies using topological sort.

        Args:
            tasks: Unordered list of tasks

        Returns:
            Tasks ordered respecting dependencies
        """
        if not tasks:
            return []

        # Build task map
        task_map = {t.id: t for t in tasks}
        in_degree: dict[str, int] = {t.id: 0 for t in tasks}
        dependents: dict[str, list[str]] = {t.id: [] for t in tasks}

        # Calculate in-degrees
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in task_map:
                    in_degree[task.id] += 1
                    dependents[dep_id].append(task.id)

        # Priority order for tie-breaking
        priority_order = {"P0": 0, "P1": 1, "P2": 2}

        # Topological sort with priority
        result: list[DecomposedTask] = []
        ready = [t for t in tasks if in_degree[t.id] == 0]
        ready.sort(key=lambda t: (priority_order.get(t.priority.value, 3), t.id))

        while ready:
            current = ready.pop(0)
            result.append(current)

            for dep_id in dependents[current.id]:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    ready.append(task_map[dep_id])
                    ready.sort(
                        key=lambda t: (priority_order.get(t.priority.value, 3), t.id)
                    )

        # Add any remaining tasks (cyclic dependencies)
        remaining = [t for t in tasks if t not in result]
        remaining.sort(key=lambda t: (priority_order.get(t.priority.value, 3), t.id))
        result.extend(remaining)

        return result

    # -------------------------------------------------------------------------
    # Public API - Helper Methods
    # -------------------------------------------------------------------------

    def generate_task_id(self, prefix: str, sequence: int) -> str:
        """Generate a task ID with the given prefix.

        Args:
            prefix: ID prefix (e.g., FEATURE, BUG, SETUP)
            sequence: Sequence number

        Returns:
            Task ID like "FEATURE-001"
        """
        return f"{prefix}-{sequence:03d}"

    def infer_dependencies(
        self, tasks: list[DecomposedTask], graph: DependencyGraph
    ) -> list[DecomposedTask]:
        """Infer task dependencies from complexity dependency graph.

        Args:
            tasks: List of tasks
            graph: Dependency graph from complexity analysis

        Returns:
            Tasks with enriched dependencies
        """
        if not graph.nodes:
            return tasks

        # Build feature name to task ID mapping
        feature_to_task: dict[str, str] = {}
        for task in tasks:
            task_desc_lower = task.description.lower()
            for node in graph.nodes:
                node_name_lower = node.name.lower()
                if node_name_lower in task_desc_lower:
                    feature_to_task[node.id] = task.id
                    break

        # Add inferred dependencies
        for task in tasks:
            task_desc_lower = task.description.lower()
            for node in graph.nodes:
                node_name_lower = node.name.lower()
                if node_name_lower in task_desc_lower:
                    # Add dependencies from graph
                    for dep_node_id in node.dependencies:
                        if dep_node_id in feature_to_task:
                            dep_task_id = feature_to_task[dep_node_id]
                            if (
                                dep_task_id not in task.dependencies
                                and dep_task_id != task.id
                            ):
                                task.dependencies.append(dep_task_id)
                    break

        return tasks

    def infer_context_files(self, task: DecomposedTask) -> list[str]:
        """Infer context files from task description.

        Args:
            task: Task to analyze

        Returns:
            List of inferred context file paths
        """
        context_files: list[str] = []
        description_lower = task.description.lower()

        # Common patterns for file inference
        patterns = {
            "auth": ["src/auth/handler.py", "src/auth/models.py"],
            "authentication": ["src/auth/handler.py", "src/auth/models.py"],
            "database": ["src/db/connector.py", "src/db/models.py"],
            "api": ["src/api/routes.py", "src/api/schemas.py"],
            "frontend": ["src/components/", "src/pages/"],
            "payment": ["src/payments/handler.py", "src/payments/stripe.py"],
            "cart": ["src/cart/handler.py", "src/cart/models.py"],
            "catalog": ["src/catalog/handler.py", "src/catalog/models.py"],
            "product": ["src/products/handler.py", "src/products/models.py"],
            "user": ["src/users/handler.py", "src/users/models.py"],
        }

        for keyword, files in patterns.items():
            if keyword in description_lower:
                context_files.extend(files)

        # Add test files for test tasks
        if task.type == DecomposedTaskType.TEST:
            context_files.append("tests/")

        # Deduplicate
        return list(dict.fromkeys(context_files))

    def generate_verification(self, task: DecomposedTask) -> TaskVerification:
        """Generate verification criteria for a task.

        Args:
            task: Task to generate verification for

        Returns:
            TaskVerification object
        """
        # Convert task ID to test file path
        task_id_lower = task.id.lower().replace("-", "_")

        if task.type == DecomposedTaskType.CODE:
            return TaskVerification(
                type=VerificationType.TEST_PASS,
                command=f"pytest tests/test_{task_id_lower}.py",
            )
        elif task.type == DecomposedTaskType.TEST:
            return TaskVerification(
                type=VerificationType.TEST_PASS,
                command=f"pytest tests/test_{task_id_lower}.py",
            )
        elif task.type == DecomposedTaskType.SETUP:
            # Infer path from description
            if "directory" in task.description.lower():
                return TaskVerification(
                    type=VerificationType.FILE_EXISTS,
                    path="src/",
                )
            return TaskVerification(
                type=VerificationType.TEST_PASS,
                command="pytest tests/",
            )
        elif task.type == DecomposedTaskType.DOCS:
            return TaskVerification(
                type=VerificationType.FILE_EXISTS,
                path="docs/",
            )
        else:
            return TaskVerification(
                type=VerificationType.TEST_PASS,
                command="pytest tests/",
            )

    def estimate_hours(self, complexity: ComplexityScore) -> float:
        """Estimate hours from complexity score.

        Args:
            complexity: Complexity score for the feature

        Returns:
            Estimated hours
        """
        cognitive_load = complexity.cognitive_load
        base_hours = self.COMPLEXITY_HOURS.get(cognitive_load, 2.0)

        # Adjust for risk rating
        risk_multiplier = {
            RiskRating.LOW: 0.8,
            RiskRating.MEDIUM: 1.0,
            RiskRating.HIGH: 1.3,
            RiskRating.CRITICAL: 1.5,
        }
        multiplier = risk_multiplier.get(complexity.risk_rating, 1.0)

        estimated = base_hours * multiplier

        # Clamp to config bounds
        return max(
            self._config.min_task_hours,
            min(self._config.max_task_hours, estimated),
        )

    def assign_model_hint(self, task: DecomposedTask) -> str:
        """Assign model hint based on task type.

        Args:
            task: Task to assign hint for

        Returns:
            Model hint string
        """
        return self.TYPE_TO_HINT.get(task.type, "coding")

    def validate_task(self, task: DecomposedTask) -> bool:
        """Validate a single task.

        Args:
            task: Task to validate

        Returns:
            True if valid, False otherwise
        """
        if not task.id or len(task.id) == 0:
            return False
        if not task.description or len(task.description) == 0:
            return False
        if not task.priority:
            return False
        if not task.type:
            return False
        return True

    def validate_all(self, tasks: list[DecomposedTask]) -> bool:
        """Validate all tasks.

        Args:
            tasks: List of tasks to validate

        Returns:
            True if all valid, False otherwise
        """
        return all(self.validate_task(t) for t in tasks)


__all__ = [
    "TaskDecomposer",
    "TaskDecomposerConfig",
    "DecomposedTask",
    "DecompositionResult",
    "TaskVerification",
    "TaskPriority",
    "TaskType",
    "VerificationType",
]
