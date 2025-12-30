"""
PRD Schema definitions for structured PRD output (PRD-OUTPUT-001).

This module defines Pydantic models for:
1. User Stories with P0/P1/P2 priority levels
2. Tech Specs with architecture decisions
3. Acceptance Criteria in Given/When/Then (Gherkin) format
4. Non-functional requirements (performance, security, etc.)

These schemas are used by PRDGenerator to produce structured,
validated PRD documents that can be converted to Markdown or JSON.

References:
- FR-02.3: PRD Output Format requirements
- docs/planning/stories/definition_of_done.md: DoD for PRD-OUTPUT-001
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

# =============================================================================
# Enums
# =============================================================================


class UserStoryPriority(str, Enum):
    """Priority levels for user stories.

    P0: Critical - Must have for MVP
    P1: High - Important but not blocking
    P2: Medium - Nice to have
    """

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class NonFunctionalType(str, Enum):
    """Types of non-functional requirements."""

    PERFORMANCE = "performance"
    SECURITY = "security"
    SCALABILITY = "scalability"
    RELIABILITY = "reliability"
    MAINTAINABILITY = "maintainability"
    USABILITY = "usability"


# =============================================================================
# Acceptance Criteria (Given/When/Then Format)
# =============================================================================


class AcceptanceCriteriaSchema(BaseModel):
    """Acceptance criterion in Given/When/Then (Gherkin) format.

    This format enables testable acceptance criteria that can be
    directly converted to BDD test scenarios.
    """

    given: str = Field(..., description="Precondition or context")
    when: str = Field(..., description="Action or trigger")
    then: str = Field(..., description="Expected outcome")
    and_given: list[str] = Field(
        default_factory=list, description="Additional preconditions"
    )
    and_when: list[str] = Field(
        default_factory=list, description="Additional actions"
    )
    and_then: list[str] = Field(
        default_factory=list, description="Additional expected outcomes"
    )

    def to_gherkin(self) -> str:
        """Convert to Gherkin scenario format.

        Returns:
            Gherkin-formatted scenario string
        """
        lines = [f"Given {self.given}"]
        for clause in self.and_given:
            lines.append(f"  And {clause}")
        lines.append(f"When {self.when}")
        for clause in self.and_when:
            lines.append(f"  And {clause}")
        lines.append(f"Then {self.then}")
        for clause in self.and_then:
            lines.append(f"  And {clause}")
        return "\n".join(lines)


# =============================================================================
# User Story Schema
# =============================================================================


class UserStorySchema(BaseModel):
    """User story with priority and testable acceptance criteria.

    Follows the format: As a [user], I want [goal] so that [benefit]
    """

    id: str = Field(..., description="Unique story identifier (e.g., US-001)")
    title: str = Field(..., description="Brief story title")
    description: str = Field(
        ..., description="Full user story description in As a/I want/So that format"
    )
    priority: UserStoryPriority = Field(..., description="Priority level (P0/P1/P2)")
    acceptance_criteria: list[AcceptanceCriteriaSchema] = Field(
        default_factory=list, description="Testable acceptance criteria"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="IDs of stories this depends on"
    )
    tags: list[str] = Field(
        default_factory=list, description="Categorization tags (e.g., mvp, backend)"
    )
    estimated_points: int | None = Field(
        default=None, description="Story point estimate"
    )
    notes: str | None = Field(default=None, description="Additional notes")


# =============================================================================
# Tech Spec Schema
# =============================================================================


class TechSpecSchema(BaseModel):
    """Technical specifications with architecture decisions.

    Captures the technical approach and constraints for implementation.
    """

    architecture_pattern: str = Field(
        ..., description="Overall architecture pattern (e.g., Microservices, Monolith)"
    )
    architecture_decisions: list[str] = Field(
        default_factory=list, description="Key architecture decisions (ADRs)"
    )
    technology_stack: list[str] = Field(
        default_factory=list, description="Technologies to be used"
    )
    infrastructure_requirements: list[str] = Field(
        default_factory=list, description="Infrastructure needs"
    )
    constraints: list[str] = Field(
        default_factory=list, description="Technical constraints"
    )
    integrations: list[str] = Field(
        default_factory=list, description="External system integrations"
    )
    data_model: dict[str, Any] | None = Field(
        default=None, description="High-level data model description"
    )


# =============================================================================
# Non-Functional Requirements Schema
# =============================================================================


class NonFunctionalRequirementSchema(BaseModel):
    """Non-functional requirement with measurable target.

    NFRs define quality attributes like performance, security, etc.
    """

    type: NonFunctionalType = Field(..., description="NFR category")
    description: str = Field(..., description="Description of the requirement")
    metric: str = Field(..., description="How it will be measured")
    target: str = Field(..., description="Target value or threshold")
    priority: UserStoryPriority = Field(
        default=UserStoryPriority.P1, description="Priority level"
    )
    verification_method: str | None = Field(
        default=None, description="How to verify the NFR is met"
    )


# =============================================================================
# Complete PRD Schema
# =============================================================================


class PRDSchema(BaseModel):
    """Complete PRD schema for structured output.

    This is the main schema that combines all PRD components.
    """

    title: str = Field(..., description="PRD title")
    version: str = Field(default="1.0.0", description="PRD version")
    overview: str = Field(..., description="High-level product overview")
    user_stories: list[UserStorySchema] = Field(
        default_factory=list, description="User stories with acceptance criteria"
    )
    tech_specs: TechSpecSchema = Field(
        ..., description="Technical specifications"
    )
    acceptance_criteria: list[AcceptanceCriteriaSchema] = Field(
        default_factory=list, description="Overall product acceptance criteria"
    )
    non_functional_requirements: list[NonFunctionalRequirementSchema] = Field(
        default_factory=list, description="Non-functional requirements"
    )
    assumptions: list[str] = Field(
        default_factory=list, description="Key assumptions"
    )
    risks: list[str] = Field(
        default_factory=list, description="Known risks"
    )
    out_of_scope: list[str] = Field(
        default_factory=list, description="Explicitly out of scope items"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_tech_specs(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure tech_specs is properly structured."""
        if isinstance(data, dict):
            tech_specs = data.get("tech_specs")
            if tech_specs is None:
                data["tech_specs"] = TechSpecSchema(
                    architecture_pattern="Not specified",
                    architecture_decisions=[],
                    technology_stack=[],
                )
        return data

    def to_markdown(self) -> str:
        """Convert PRD to Markdown format.

        Returns:
            Markdown-formatted PRD document
        """
        lines: list[str] = []

        # Title and version
        lines.append(f"# {self.title}")
        lines.append(f"\n**Version**: {self.version}\n")

        # Overview
        lines.append("## Overview\n")
        lines.append(self.overview)
        lines.append("")

        # User Stories
        if self.user_stories:
            lines.append("## User Stories\n")
            for story in self.user_stories:
                lines.append(f"### {story.id}: {story.title}\n")
                lines.append(f"**Priority**: {story.priority.value}\n")
                lines.append(story.description)
                lines.append("")

                if story.acceptance_criteria:
                    lines.append("**Acceptance Criteria**:\n")
                    for i, ac in enumerate(story.acceptance_criteria, 1):
                        lines.append(f"**Scenario {i}**:")
                        lines.append(f"```gherkin\n{ac.to_gherkin()}\n```")
                    lines.append("")

        # Tech Specs
        lines.append("## Technical Specifications\n")
        lines.append(f"**Architecture Pattern**: {self.tech_specs.architecture_pattern}\n")

        if self.tech_specs.architecture_decisions:
            lines.append("### Architecture Decisions\n")
            for decision in self.tech_specs.architecture_decisions:
                lines.append(f"- {decision}")
            lines.append("")

        if self.tech_specs.technology_stack:
            lines.append("### Technology Stack\n")
            for tech in self.tech_specs.technology_stack:
                lines.append(f"- {tech}")
            lines.append("")

        if self.tech_specs.infrastructure_requirements:
            lines.append("### Infrastructure Requirements\n")
            for req in self.tech_specs.infrastructure_requirements:
                lines.append(f"- {req}")
            lines.append("")

        if self.tech_specs.constraints:
            lines.append("### Constraints\n")
            for constraint in self.tech_specs.constraints:
                lines.append(f"- {constraint}")
            lines.append("")

        # Overall Acceptance Criteria
        if self.acceptance_criteria:
            lines.append("## Product Acceptance Criteria\n")
            for i, ac in enumerate(self.acceptance_criteria, 1):
                lines.append(f"**Scenario {i}**:")
                lines.append(f"```gherkin\n{ac.to_gherkin()}\n```")
            lines.append("")

        # Non-Functional Requirements
        if self.non_functional_requirements:
            lines.append("## Non-Functional Requirements\n")
            for nfr in self.non_functional_requirements:
                lines.append(f"### {nfr.type.value.title()}\n")
                lines.append(f"- **Description**: {nfr.description}")
                lines.append(f"- **Metric**: {nfr.metric}")
                lines.append(f"- **Target**: {nfr.target}")
                lines.append(f"- **Priority**: {nfr.priority.value}")
                lines.append("")

        # Assumptions
        if self.assumptions:
            lines.append("## Assumptions\n")
            for assumption in self.assumptions:
                lines.append(f"- {assumption}")
            lines.append("")

        # Risks
        if self.risks:
            lines.append("## Risks\n")
            for risk in self.risks:
                lines.append(f"- {risk}")
            lines.append("")

        # Out of Scope
        if self.out_of_scope:
            lines.append("## Out of Scope\n")
            for item in self.out_of_scope:
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "UserStoryPriority",
    "NonFunctionalType",
    "AcceptanceCriteriaSchema",
    "UserStorySchema",
    "TechSpecSchema",
    "NonFunctionalRequirementSchema",
    "PRDSchema",
]
