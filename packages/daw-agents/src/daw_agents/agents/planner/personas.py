"""
Roundtable Personas for the Taskmaster Agent (PLANNER-002).

This module implements enhanced persona system for conducting roundtable discussions:
1. PersonaConfig - Configuration model for defining personas
2. PersonaCritique - Structured output model for critiques
3. Default Personas - CTO, UX, and Security personas with distinct focus areas
4. PersonaRegistry - Registry for managing available personas
5. RoundtableSession - Session manager for running critique sessions

Each persona provides a unique perspective:
- CTO: Architecture, scalability, tech debt, maintainability
- UX: Usability, accessibility, user flows, onboarding
- Security: Vulnerabilities, compliance, data protection, authentication

References:
- agents.md: Planner Agent specification
- PLANNER-001: Taskmaster Agent (base roundtable functionality)
- docs/planning/tasks.json: PLANNER-002 task definition
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from daw_agents.models.router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class CritiqueSeverity(str, Enum):
    """Severity levels for critique concerns."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class PersonaConfig(BaseModel):
    """Configuration for a synthetic persona.

    Defines the persona's identity, focus areas, and prompt template
    used for generating critiques.

    Attributes:
        name: Short identifier for the persona (e.g., "CTO")
        role: Full role title (e.g., "Chief Technology Officer")
        critique_focus: List of areas this persona focuses on
        prompt_template: Template string with {concept} placeholder
        description: Optional description of the persona
        system_prompt: Optional custom system prompt for the LLM
    """

    name: str = Field(..., description="Persona identifier (e.g., CTO, UX)")
    role: str = Field(..., description="Full role title")
    critique_focus: list[str] = Field(
        ..., description="List of focus areas for critique"
    )
    prompt_template: str = Field(
        ..., description="Prompt template with {concept} placeholder"
    )
    description: str | None = Field(
        default=None, description="Optional persona description"
    )
    system_prompt: str | None = Field(
        default=None, description="Optional custom system prompt"
    )


class PersonaCritique(BaseModel):
    """Structured critique output from a persona.

    Represents the analysis and feedback from a single persona
    on a concept or proposal.

    Attributes:
        persona_name: Name of the persona providing the critique
        concerns: List of concerns or issues identified
        recommendations: List of actionable recommendations
        questions: List of clarifying questions
        severity: Overall severity level of concerns
        summary: Brief summary of the critique
    """

    persona_name: str = Field(..., description="Name of the critiquing persona")
    concerns: list[str] = Field(
        default_factory=list, description="List of identified concerns"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="List of recommendations"
    )
    questions: list[str] = Field(
        default_factory=list, description="List of clarifying questions"
    )
    severity: CritiqueSeverity = Field(
        default=CritiqueSeverity.LOW, description="Overall severity level"
    )
    summary: str = Field(..., description="Brief summary of the critique")

    def to_markdown(self) -> str:
        """Convert critique to markdown format.

        Returns:
            Formatted markdown string representation of the critique.
        """
        lines = [f"## {self.persona_name} Critique"]
        lines.append(f"\n**Severity**: {self.severity.value}\n")
        lines.append(f"**Summary**: {self.summary}\n")

        if self.concerns:
            lines.append("\n### Concerns")
            for concern in self.concerns:
                lines.append(f"- {concern}")

        if self.recommendations:
            lines.append("\n### Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")

        if self.questions:
            lines.append("\n### Questions")
            for question in self.questions:
                lines.append(f"- {question}")

        return "\n".join(lines)


class SynthesizedFeedback(BaseModel):
    """Synthesized feedback from multiple persona critiques.

    Combines and summarizes feedback from all personas into
    a unified view.

    Attributes:
        all_concerns: Combined list of all concerns
        all_recommendations: Combined list of all recommendations
        all_questions: Combined list of all questions
        highest_severity: Highest severity among all critiques
        combined_summary: Overall summary combining all feedback
        persona_summaries: Dict mapping persona name to their summary
    """

    all_concerns: list[str] = Field(
        default_factory=list, description="All concerns from all personas"
    )
    all_recommendations: list[str] = Field(
        default_factory=list, description="All recommendations from all personas"
    )
    all_questions: list[str] = Field(
        default_factory=list, description="All questions from all personas"
    )
    highest_severity: CritiqueSeverity = Field(
        default=CritiqueSeverity.LOW, description="Highest severity level"
    )
    combined_summary: str = Field(
        default="", description="Combined summary of all critiques"
    )
    persona_summaries: dict[str, str] = Field(
        default_factory=dict, description="Summaries by persona"
    )


# -----------------------------------------------------------------------------
# Default Personas
# -----------------------------------------------------------------------------

CTO_PERSONA = PersonaConfig(
    name="CTO",
    role="Chief Technology Officer",
    critique_focus=["architecture", "scalability", "tech_debt", "maintainability"],
    prompt_template="""As the Chief Technology Officer, critically evaluate this concept from a technical perspective.

CONCEPT TO EVALUATE:
{concept}

You must analyze:
1. **Architecture**: Is the proposed architecture sound? Are there better patterns?
2. **Scalability**: How will this scale with users/data growth? What are the bottlenecks?
3. **Tech Debt**: What technical debt might this introduce? How can it be minimized?
4. **Maintainability**: How easy will this be to maintain and extend over time?

Provide your response in JSON format:
{{
    "concerns": ["list of specific technical concerns"],
    "recommendations": ["list of actionable technical recommendations"],
    "questions": ["list of clarifying questions"],
    "severity": "low|medium|high|critical",
    "summary": "brief overall technical assessment"
}}

Be specific and actionable. Focus on real technical risks and opportunities.""",
    description="Evaluates technical architecture, scalability, and maintainability",
    system_prompt="You are a seasoned CTO with 20+ years of experience building scalable systems. You focus on technical excellence, long-term maintainability, and avoiding technical debt.",
)


UX_PERSONA = PersonaConfig(
    name="UX",
    role="Head of User Experience",
    critique_focus=["usability", "accessibility", "user_flows", "onboarding"],
    prompt_template="""As the Head of User Experience, critically evaluate this concept from a user perspective.

CONCEPT TO EVALUATE:
{concept}

You must analyze:
1. **Usability**: Is this intuitive for users? Where might they struggle?
2. **Accessibility**: Does this meet WCAG guidelines? How accessible is it?
3. **User Flows**: Are the workflows efficient? Where are the friction points?
4. **Onboarding**: How will new users learn to use this? Is there a learning curve?

Provide your response in JSON format:
{{
    "concerns": ["list of specific UX concerns"],
    "recommendations": ["list of actionable UX recommendations"],
    "questions": ["list of clarifying questions about user needs"],
    "severity": "low|medium|high|critical",
    "summary": "brief overall UX assessment"
}}

Be specific and actionable. Consider diverse user personas and edge cases.""",
    description="Evaluates user experience, accessibility, and user flows",
    system_prompt="You are an expert UX designer with deep knowledge of accessibility, user research, and human-centered design. You advocate for users and inclusive design.",
)


SECURITY_PERSONA = PersonaConfig(
    name="Security",
    role="Chief Information Security Officer",
    critique_focus=[
        "vulnerabilities",
        "compliance",
        "data_protection",
        "authentication",
    ],
    prompt_template="""As the Chief Information Security Officer, critically evaluate this concept from a security perspective.

CONCEPT TO EVALUATE:
{concept}

You must analyze:
1. **Vulnerabilities**: What security vulnerabilities might exist? (OWASP Top 10)
2. **Compliance**: What compliance requirements apply? (GDPR, SOC2, HIPAA, etc.)
3. **Data Protection**: How is sensitive data handled? Is encryption adequate?
4. **Authentication**: Is auth/authz properly designed? Are there privilege escalation risks?

Provide your response in JSON format:
{{
    "concerns": ["list of specific security concerns"],
    "recommendations": ["list of actionable security recommendations"],
    "questions": ["list of clarifying questions about security requirements"],
    "severity": "low|medium|high|critical",
    "summary": "brief overall security assessment"
}}

Be specific and actionable. Assume attackers will try to exploit any weakness.""",
    description="Evaluates security vulnerabilities, compliance, and data protection",
    system_prompt="You are a security-focused CISO who has seen many breaches. You think like an attacker and advocate for defense in depth. Security is non-negotiable.",
)


# -----------------------------------------------------------------------------
# PersonaRegistry
# -----------------------------------------------------------------------------


class PersonaRegistry:
    """Registry for managing available personas.

    Provides methods to register, retrieve, and list personas.
    Initializes with default CTO, UX, and Security personas.
    """

    def __init__(self) -> None:
        """Initialize registry with default personas."""
        self._personas: dict[str, PersonaConfig] = {}
        # Register default personas
        self.register(CTO_PERSONA)
        self.register(UX_PERSONA)
        self.register(SECURITY_PERSONA)

    def register(self, persona: PersonaConfig) -> None:
        """Register a persona in the registry.

        Args:
            persona: PersonaConfig to register
        """
        self._personas[persona.name.lower()] = persona
        logger.debug("Registered persona: %s", persona.name)

    def unregister(self, name: str) -> None:
        """Remove a persona from the registry.

        Args:
            name: Name of the persona to remove
        """
        key = name.lower()
        if key in self._personas:
            del self._personas[key]
            logger.debug("Unregistered persona: %s", name)

    def get_persona(self, name: str) -> PersonaConfig | None:
        """Get a persona by name (case insensitive).

        Args:
            name: Persona name to look up

        Returns:
            PersonaConfig if found, None otherwise
        """
        return self._personas.get(name.lower())

    def list_personas(self) -> list[str]:
        """List all registered persona names.

        Returns:
            List of persona names (original case from registration)
        """
        return [p.name for p in self._personas.values()]

    def get_all(self) -> list[PersonaConfig]:
        """Get all registered personas.

        Returns:
            List of all PersonaConfig objects
        """
        return list(self._personas.values())


# -----------------------------------------------------------------------------
# RoundtableSession
# -----------------------------------------------------------------------------


class RoundtableSession:
    """Session manager for running roundtable discussions.

    Orchestrates critique collection from multiple personas
    and synthesizes their feedback.

    Attributes:
        _model_router: Router for LLM calls
        _registry: Registry of available personas
    """

    def __init__(
        self,
        model_router: ModelRouter,
        registry: PersonaRegistry | None = None,
    ) -> None:
        """Initialize a roundtable session.

        Args:
            model_router: Model router for LLM calls
            registry: Optional custom persona registry
        """
        self._model_router = model_router
        self._registry = registry or PersonaRegistry()

    def get_persona(self, name: str) -> PersonaConfig | None:
        """Get a persona from the registry.

        Args:
            name: Persona name

        Returns:
            PersonaConfig if found, None otherwise
        """
        return self._registry.get_persona(name)

    async def run_critique(
        self, persona: PersonaConfig, concept: str
    ) -> PersonaCritique:
        """Run a critique with a single persona.

        Args:
            persona: PersonaConfig to use
            concept: Concept/proposal to critique

        Returns:
            PersonaCritique with the persona's feedback
        """
        logger.info("Running critique with persona: %s", persona.name)

        # Format the prompt
        prompt = persona.prompt_template.format(concept=concept)

        # Build messages
        system_message = persona.system_prompt or f"You are {persona.name}, {persona.role}."
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._model_router.route(
                task_type=TaskType.PLANNING,
                messages=messages,
            )

            # Parse the response
            critique_data = self._extract_critique(response, persona.name)
            return PersonaCritique(persona_name=persona.name, **critique_data)

        except Exception as e:
            logger.warning(
                "Failed to get critique from %s: %s", persona.name, str(e)
            )
            # Return a minimal critique indicating the error
            return PersonaCritique(
                persona_name=persona.name,
                concerns=[f"Error getting critique: {str(e)}"],
                recommendations=[],
                questions=[],
                severity=CritiqueSeverity.LOW,
                summary=f"Unable to complete critique due to error: {str(e)}",
            )

    def _extract_critique(self, response: str, persona_name: str) -> dict[str, Any]:
        """Extract critique data from LLM response.

        Args:
            response: Raw LLM response
            persona_name: Name of the persona (for error handling)

        Returns:
            Dict with critique fields
        """
        # Try to extract JSON from the response
        json_str = self._extract_json(response)

        try:
            data: dict[str, Any] = json.loads(json_str)
            # Validate and normalize severity
            severity_val = data.get("severity", "low")
            severity_str = str(severity_val).lower() if severity_val else "low"
            if severity_str not in ["low", "medium", "high", "critical"]:
                severity_str = "low"
            data["severity"] = severity_str
            return data
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse critique JSON from %s: %s", persona_name, e)
            # Return a fallback critique
            return {
                "concerns": ["Could not parse structured response"],
                "recommendations": [],
                "questions": [],
                "severity": "low",
                "summary": response[:500] if response else "No response received",
            }

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

    async def run_roundtable(
        self,
        concept: str,
        persona_names: list[str] | None = None,
    ) -> list[PersonaCritique]:
        """Run a full roundtable with multiple personas.

        Args:
            concept: Concept/proposal to critique
            persona_names: Optional list of specific persona names to use.
                          If None, uses all registered personas.

        Returns:
            List of PersonaCritique objects from all personas
        """
        logger.info("Starting roundtable session")

        # Get personas to use
        if persona_names:
            personas = [
                p
                for name in persona_names
                if (p := self._registry.get_persona(name)) is not None
            ]
        else:
            personas = self._registry.get_all()

        # Collect critiques from all personas
        critiques: list[PersonaCritique] = []
        for persona in personas:
            try:
                critique = await self.run_critique(persona, concept)
                critiques.append(critique)
            except Exception as e:
                logger.warning(
                    "Persona %s failed, continuing with others: %s",
                    persona.name,
                    str(e),
                )
                # Add a failure critique
                critiques.append(
                    PersonaCritique(
                        persona_name=persona.name,
                        concerns=[f"Critique failed: {str(e)}"],
                        recommendations=[],
                        questions=[],
                        severity=CritiqueSeverity.LOW,
                        summary=f"Unable to complete critique: {str(e)}",
                    )
                )

        logger.info("Roundtable complete: %d critiques collected", len(critiques))
        return critiques

    def synthesize_feedback(
        self, critiques: list[PersonaCritique]
    ) -> SynthesizedFeedback:
        """Synthesize feedback from multiple critiques.

        Combines concerns, recommendations, and questions from all
        critiques and determines the highest severity.

        Args:
            critiques: List of PersonaCritique objects

        Returns:
            SynthesizedFeedback with combined data
        """
        if not critiques:
            return SynthesizedFeedback(
                combined_summary="No critiques provided",
            )

        # Combine all data
        all_concerns: list[str] = []
        all_recommendations: list[str] = []
        all_questions: list[str] = []
        persona_summaries: dict[str, str] = {}

        # Track highest severity
        severity_order = {
            CritiqueSeverity.LOW: 0,
            CritiqueSeverity.MEDIUM: 1,
            CritiqueSeverity.HIGH: 2,
            CritiqueSeverity.CRITICAL: 3,
        }
        highest_severity = CritiqueSeverity.LOW

        for critique in critiques:
            all_concerns.extend(critique.concerns)
            all_recommendations.extend(critique.recommendations)
            all_questions.extend(critique.questions)
            persona_summaries[critique.persona_name] = critique.summary

            if severity_order[critique.severity] > severity_order[highest_severity]:
                highest_severity = critique.severity

        # Build combined summary
        summary_parts = [
            f"**{name}**: {summary}"
            for name, summary in persona_summaries.items()
        ]
        combined_summary = "\n".join(summary_parts)

        return SynthesizedFeedback(
            all_concerns=all_concerns,
            all_recommendations=all_recommendations,
            all_questions=all_questions,
            highest_severity=highest_severity,
            combined_summary=combined_summary,
            persona_summaries=persona_summaries,
        )


# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = [
    # Enums
    "CritiqueSeverity",
    # Models
    "PersonaConfig",
    "PersonaCritique",
    "SynthesizedFeedback",
    # Default Personas
    "CTO_PERSONA",
    "UX_PERSONA",
    "SECURITY_PERSONA",
    # Classes
    "PersonaRegistry",
    "RoundtableSession",
]
