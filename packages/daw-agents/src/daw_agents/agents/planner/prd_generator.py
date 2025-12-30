"""
PRD Generator for enhanced PRD output (PRD-OUTPUT-001).

This module implements the PRDGenerator class that:
1. Generates structured PRD from Taskmaster output
2. Creates User Stories with P0/P1/P2 priority levels
3. Generates Tech Specs with clear architecture decisions
4. Converts acceptance criteria to testable Given/When/Then format
5. Adds non-functional requirements (performance, security)
6. Validates completeness before allowing task decomposition

The PRDGenerator enhances the basic PRDOutput from Taskmaster
into a fully-validated PRDSchema suitable for task decomposition.

References:
- FR-02.3: PRD Output Format requirements
- taskmaster.py: Taskmaster agent that produces initial PRDOutput
- prd_schema.py: Schema definitions for PRD structure
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from daw_agents.models.router import ModelRouter, TaskType
from daw_agents.schemas.prd_schema import (
    AcceptanceCriteriaSchema,
    NonFunctionalRequirementSchema,
    NonFunctionalType,
    PRDSchema,
    TechSpecSchema,
    UserStoryPriority,
    UserStorySchema,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Re-export for backward compatibility
# =============================================================================

# Re-export from prd_schema for tests that import from this module
AcceptanceCriterion = AcceptanceCriteriaSchema
NonFunctionalRequirement = NonFunctionalRequirementSchema
TechSpec = TechSpecSchema


# =============================================================================
# Configuration and Result Models
# =============================================================================


class PRDGenerationConfig(BaseModel):
    """Configuration for PRD generation and validation.

    Controls what elements are required for a complete PRD.
    """

    require_p0_story: bool = Field(
        default=True, description="Require at least one P0 user story"
    )
    require_acceptance_criteria: bool = Field(
        default=True, description="Require acceptance criteria for all P0 stories"
    )
    require_tech_specs: bool = Field(
        default=True, description="Require complete tech specs"
    )
    require_nfr: bool = Field(
        default=False, description="Require non-functional requirements"
    )
    min_user_stories: int = Field(
        default=1, description="Minimum number of user stories"
    )
    min_acceptance_criteria_per_story: int = Field(
        default=1, description="Minimum acceptance criteria per P0 story"
    )


class PRDValidationResult(BaseModel):
    """Result of PRD validation.

    Contains validation status, errors, and warnings.
    """

    is_valid: bool = Field(..., description="Whether the PRD is valid")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class PRDValidationError(Exception):
    """Exception raised when PRD validation fails.

    Attributes:
        message: Error message
        errors: List of specific validation errors
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        """Initialize PRD validation error.

        Args:
            message: Error message
            errors: List of specific validation errors
        """
        super().__init__(message)
        self.message = message
        self.errors = errors or []

    def __str__(self) -> str:
        """Return error message."""
        return self.message


# =============================================================================
# Prompt Templates
# =============================================================================

PRD_ENHANCEMENT_PROMPT = """You are an expert Product Manager enhancing a PRD.

ORIGINAL PRD:
{original_prd}

CLARIFICATIONS:
{clarifications}

ROUNDTABLE FEEDBACK:
{critiques}

Enhance this PRD to a complete, structured format with the following:

1. **User Stories**: Each story needs:
   - Unique ID (US-XXX)
   - Title
   - Description in "As a [user], I want [goal] so that [benefit]" format
   - Priority (P0=critical, P1=high, P2=medium)
   - Acceptance criteria in Given/When/Then format

2. **Tech Specs**: Include:
   - Architecture pattern
   - Key architecture decisions
   - Technology stack
   - Infrastructure requirements (if applicable)
   - Constraints

3. **Acceptance Criteria**: All criteria in Given/When/Then format:
   - given: Precondition
   - when: Action
   - then: Expected result

4. **Non-Functional Requirements**: At least consider:
   - Performance (response times, throughput)
   - Security (authentication, authorization)
   - Scalability (if applicable)

Output ONLY valid JSON matching this structure:
{{
    "title": "PRD Title",
    "version": "1.0.0",
    "overview": "Product overview",
    "user_stories": [
        {{
            "id": "US-001",
            "title": "Story Title",
            "description": "As a user, I want...",
            "priority": "P0",
            "acceptance_criteria": [
                {{"given": "...", "when": "...", "then": "..."}}
            ]
        }}
    ],
    "tech_specs": {{
        "architecture_pattern": "...",
        "architecture_decisions": ["..."],
        "technology_stack": ["..."],
        "infrastructure_requirements": ["..."],
        "constraints": ["..."]
    }},
    "acceptance_criteria": [
        {{"given": "...", "when": "...", "then": "..."}}
    ],
    "non_functional_requirements": [
        {{
            "type": "performance|security|scalability|reliability|maintainability|usability",
            "description": "...",
            "metric": "...",
            "target": "...",
            "priority": "P0|P1|P2"
        }}
    ]
}}

Ensure at least one P0 user story with acceptance criteria."""


# =============================================================================
# PRDGenerator Class
# =============================================================================


class PRDGenerator:
    """Generates and validates structured PRD documents.

    The PRDGenerator takes input from Taskmaster (basic PRDOutput)
    and enhances it into a fully-validated PRDSchema with:
    - User stories in proper format with priorities
    - Acceptance criteria in Given/When/Then format
    - Complete tech specs with architecture decisions
    - Non-functional requirements

    Attributes:
        _model_router: Router for LLM model selection
        _config: Configuration for generation and validation
    """

    def __init__(
        self,
        model_router: ModelRouter | None = None,
        config: PRDGenerationConfig | None = None,
    ) -> None:
        """Initialize the PRD generator.

        Args:
            model_router: Optional custom model router. Uses default if None.
            config: Optional generation configuration. Uses defaults if None.
        """
        self._model_router = model_router or ModelRouter()
        self._config = config or PRDGenerationConfig()

    async def generate(
        self,
        requirement: str,
        clarifications: list[str] | None = None,
        roundtable_critiques: list[str] | None = None,
    ) -> PRDSchema:
        """Generate a complete PRD from requirements.

        Takes a user requirement and optional context to generate
        a fully-structured PRD document.

        Args:
            requirement: User's requirement string
            clarifications: Optional clarifications from interview
            roundtable_critiques: Optional feedback from roundtable

        Returns:
            Complete PRDSchema object

        Raises:
            PRDValidationError: If generated PRD fails validation
        """
        logger.info("Generating PRD for requirement: %s", requirement[:100])

        # Format inputs
        clarifications_text = (
            "\n".join(clarifications) if clarifications else "None provided"
        )
        critiques_text = (
            "\n".join(roundtable_critiques)
            if roundtable_critiques
            else "None provided"
        )

        prompt = PRD_ENHANCEMENT_PROMPT.format(
            original_prd=requirement,
            clarifications=clarifications_text,
            critiques=critiques_text,
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

            # Parse the response
            prd_data = json.loads(self._extract_json(response))
            prd = self._parse_prd_response(prd_data)

            return prd

        except json.JSONDecodeError as e:
            logger.error("Failed to parse PRD JSON: %s", str(e))
            raise PRDValidationError(
                message=f"Failed to parse PRD response: {e}",
                errors=[str(e)],
            ) from e

    async def enhance_from_taskmaster(
        self,
        taskmaster_output: dict[str, Any],
        clarifications: list[str] | None = None,
        roundtable_critiques: list[str] | None = None,
    ) -> PRDSchema:
        """Enhance a Taskmaster PRDOutput into a complete PRDSchema.

        Takes the basic PRDOutput from Taskmaster and enhances it
        with proper structure, Given/When/Then criteria, and NFRs.

        Args:
            taskmaster_output: Dictionary from Taskmaster PRDOutput
            clarifications: Optional clarifications
            roundtable_critiques: Optional roundtable feedback

        Returns:
            Enhanced PRDSchema object
        """
        logger.info("Enhancing Taskmaster output to PRDSchema")

        # Convert taskmaster output to JSON string for the prompt
        original_prd_json = json.dumps(taskmaster_output, indent=2)

        clarifications_text = (
            "\n".join(clarifications) if clarifications else "None provided"
        )
        critiques_text = (
            "\n".join(roundtable_critiques)
            if roundtable_critiques
            else "None provided"
        )

        prompt = PRD_ENHANCEMENT_PROMPT.format(
            original_prd=original_prd_json,
            clarifications=clarifications_text,
            critiques=critiques_text,
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

            prd_data = json.loads(self._extract_json(response))
            prd = self._parse_prd_response(prd_data)

            return prd

        except json.JSONDecodeError as e:
            logger.error("Failed to parse enhanced PRD JSON: %s", str(e))
            raise PRDValidationError(
                message=f"Failed to parse enhanced PRD: {e}",
                errors=[str(e)],
            ) from e

    def _parse_prd_response(self, data: dict[str, Any]) -> PRDSchema:
        """Parse PRD response data into PRDSchema.

        Args:
            data: Dictionary with PRD data

        Returns:
            PRDSchema object
        """
        # Parse user stories
        user_stories: list[UserStorySchema] = []
        for story_data in data.get("user_stories", []):
            acceptance_criteria = [
                AcceptanceCriteriaSchema(
                    given=ac.get("given", ""),
                    when=ac.get("when", ""),
                    then=ac.get("then", ""),
                    and_given=ac.get("and_given", []),
                    and_when=ac.get("and_when", []),
                    and_then=ac.get("and_then", []),
                )
                for ac in story_data.get("acceptance_criteria", [])
            ]

            # Parse priority, handling string values
            priority_str = story_data.get("priority", "P1")
            try:
                priority = UserStoryPriority(priority_str)
            except ValueError:
                priority = UserStoryPriority.P1

            user_stories.append(
                UserStorySchema(
                    id=story_data.get("id", f"US-{len(user_stories) + 1:03d}"),
                    title=story_data.get("title", story_data.get("description", "")[:50]),
                    description=story_data.get("description", ""),
                    priority=priority,
                    acceptance_criteria=acceptance_criteria,
                    dependencies=story_data.get("dependencies", []),
                    tags=story_data.get("tags", []),
                )
            )

        # Parse tech specs
        tech_data = data.get("tech_specs", {})
        tech_specs = TechSpecSchema(
            architecture_pattern=tech_data.get("architecture_pattern", "Not specified"),
            architecture_decisions=tech_data.get("architecture_decisions", []),
            technology_stack=tech_data.get("technology_stack", []),
            infrastructure_requirements=tech_data.get("infrastructure_requirements", []),
            constraints=tech_data.get("constraints", []),
            integrations=tech_data.get("integrations", []),
        )

        # Parse overall acceptance criteria
        acceptance_criteria = [
            AcceptanceCriteriaSchema(
                given=ac.get("given", ""),
                when=ac.get("when", ""),
                then=ac.get("then", ""),
            )
            for ac in data.get("acceptance_criteria", [])
        ]

        # Parse NFRs
        non_functional_requirements: list[NonFunctionalRequirementSchema] = []
        for nfr_data in data.get("non_functional_requirements", []):
            nfr_type_str = nfr_data.get("type", "performance")
            try:
                nfr_type = NonFunctionalType(nfr_type_str.lower())
            except ValueError:
                nfr_type = NonFunctionalType.PERFORMANCE

            priority_str = nfr_data.get("priority", "P1")
            try:
                nfr_priority = UserStoryPriority(priority_str)
            except ValueError:
                nfr_priority = UserStoryPriority.P1

            non_functional_requirements.append(
                NonFunctionalRequirementSchema(
                    type=nfr_type,
                    description=nfr_data.get("description", ""),
                    metric=nfr_data.get("metric", ""),
                    target=nfr_data.get("target", ""),
                    priority=nfr_priority,
                )
            )

        return PRDSchema(
            title=data.get("title", "Untitled PRD"),
            version=data.get("version", "1.0.0"),
            overview=data.get("overview", ""),
            user_stories=user_stories,
            tech_specs=tech_specs,
            acceptance_criteria=acceptance_criteria,
            non_functional_requirements=non_functional_requirements,
            assumptions=data.get("assumptions", []),
            risks=data.get("risks", []),
            out_of_scope=data.get("out_of_scope", []),
        )

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
                depth = 0
                for i, char in enumerate(text[start:], start):
                    if char == start_char:
                        depth += 1
                    elif char == end_char:
                        depth -= 1
                        if depth == 0:
                            return text[start : i + 1]

        return text

    def validate_completeness(self, prd: PRDSchema) -> PRDValidationResult:
        """Validate that a PRD is complete and ready for task decomposition.

        Checks all configured requirements and returns validation result.

        Args:
            prd: PRDSchema to validate

        Returns:
            PRDValidationResult with status, errors, and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check for P0 story if required
        if self._config.require_p0_story:
            p0_stories = [s for s in prd.user_stories if s.priority == UserStoryPriority.P0]
            if not p0_stories:
                errors.append("PRD must have at least one P0 (critical) user story")

        # Check minimum user stories
        if len(prd.user_stories) < self._config.min_user_stories:
            errors.append(
                f"PRD must have at least {self._config.min_user_stories} user story(ies)"
            )

        # Check acceptance criteria for P0 stories
        if self._config.require_acceptance_criteria:
            p0_stories = [s for s in prd.user_stories if s.priority == UserStoryPriority.P0]
            for story in p0_stories:
                if len(story.acceptance_criteria) < self._config.min_acceptance_criteria_per_story:
                    errors.append(
                        f"P0 story {story.id} must have at least "
                        f"{self._config.min_acceptance_criteria_per_story} acceptance criteria"
                    )

        # Check tech specs if required
        if self._config.require_tech_specs:
            if not prd.tech_specs.architecture_pattern or prd.tech_specs.architecture_pattern == "Not specified":
                errors.append("Tech specs must include an architecture pattern")
            if not prd.tech_specs.architecture_pattern.strip():
                errors.append("Architecture pattern cannot be empty")

        # Check NFRs if required
        if self._config.require_nfr:
            if not prd.non_functional_requirements:
                errors.append("PRD must have at least one non-functional requirement")

        # Add warnings for optional elements
        if not prd.non_functional_requirements and not self._config.require_nfr:
            warnings.append("Consider adding non-functional requirements")

        if not prd.tech_specs.technology_stack:
            warnings.append("Consider specifying a technology stack")

        return PRDValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def can_proceed_to_task_decomposition(self, prd: PRDSchema) -> bool:
        """Check if PRD is complete enough to proceed to task decomposition.

        This is the gate that prevents task decomposition on incomplete PRDs.

        Args:
            prd: PRDSchema to check

        Returns:
            True if PRD is valid and can proceed, False otherwise
        """
        result = self.validate_completeness(prd)
        return result.is_valid


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Main class
    "PRDGenerator",
    # Configuration and results
    "PRDGenerationConfig",
    "PRDValidationResult",
    "PRDValidationError",
    # Re-exported from schema for convenience
    "AcceptanceCriterion",
    "NonFunctionalRequirement",
    "TechSpec",
    "UserStoryPriority",
    "NonFunctionalType",
]
