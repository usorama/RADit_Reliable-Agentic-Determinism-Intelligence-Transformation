"""
Tests for Roundtable Personas (PLANNER-002).

This module tests the enhanced persona system for the Taskmaster agent:
1. PersonaConfig - Configuration model for personas
2. PersonaCritique - Structured critique output model
3. CTOPersona, UXPersona, SecurityPersona - Specialized persona instances
4. PersonaRegistry - Registry of available personas
5. RoundtableSession - Session manager for running roundtable discussions

Each persona provides a distinct critique perspective:
- CTO: Architecture, scalability, tech debt, maintainability
- UX: Usability, accessibility, user flows, onboarding
- Security: Vulnerabilities, compliance, data protection, authentication
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from daw_agents.agents.planner.personas import (
    CTO_PERSONA,
    SECURITY_PERSONA,
    UX_PERSONA,
    CritiqueSeverity,
    PersonaConfig,
    PersonaCritique,
    PersonaRegistry,
    RoundtableSession,
)
from daw_agents.models.router import ModelRouter


# -----------------------------------------------------------------------------
# PersonaConfig Tests
# -----------------------------------------------------------------------------


class TestPersonaConfig:
    """Test PersonaConfig model."""

    def test_persona_config_creation(self) -> None:
        """Test creating a PersonaConfig with all fields."""
        config = PersonaConfig(
            name="CTO",
            role="Chief Technology Officer",
            critique_focus=["architecture", "scalability", "tech_debt"],
            prompt_template="As CTO, evaluate this concept: {concept}",
        )
        assert config.name == "CTO"
        assert config.role == "Chief Technology Officer"
        assert "architecture" in config.critique_focus
        assert "scalability" in config.critique_focus
        assert "tech_debt" in config.critique_focus
        assert "{concept}" in config.prompt_template

    def test_persona_config_requires_name(self) -> None:
        """Test that PersonaConfig requires name field."""
        with pytest.raises(Exception):
            PersonaConfig(
                role="Test Role",
                critique_focus=["test"],
                prompt_template="Test",
            )  # type: ignore[call-arg]

    def test_persona_config_requires_role(self) -> None:
        """Test that PersonaConfig requires role field."""
        with pytest.raises(Exception):
            PersonaConfig(
                name="Test",
                critique_focus=["test"],
                prompt_template="Test",
            )  # type: ignore[call-arg]

    def test_persona_config_requires_critique_focus(self) -> None:
        """Test that PersonaConfig requires critique_focus field."""
        with pytest.raises(Exception):
            PersonaConfig(
                name="Test",
                role="Test Role",
                prompt_template="Test",
            )  # type: ignore[call-arg]

    def test_persona_config_requires_prompt_template(self) -> None:
        """Test that PersonaConfig requires prompt_template field."""
        with pytest.raises(Exception):
            PersonaConfig(
                name="Test",
                role="Test Role",
                critique_focus=["test"],
            )  # type: ignore[call-arg]

    def test_persona_config_format_prompt(self) -> None:
        """Test that prompt_template can be formatted with concept."""
        config = PersonaConfig(
            name="CTO",
            role="Chief Technology Officer",
            critique_focus=["architecture"],
            prompt_template="As CTO, evaluate this concept:\n\n{concept}\n\nProvide feedback.",
        )
        formatted = config.prompt_template.format(concept="Build a todo app")
        assert "Build a todo app" in formatted
        assert "As CTO" in formatted


class TestPersonaConfigCustomization:
    """Test PersonaConfig customization options."""

    def test_persona_config_with_description(self) -> None:
        """Test PersonaConfig with optional description."""
        config = PersonaConfig(
            name="CustomPersona",
            role="Custom Role",
            critique_focus=["custom_focus"],
            prompt_template="Custom template: {concept}",
            description="A custom persona for specialized critiques",
        )
        assert config.description == "A custom persona for specialized critiques"

    def test_persona_config_with_system_prompt(self) -> None:
        """Test PersonaConfig with optional system_prompt."""
        config = PersonaConfig(
            name="CustomPersona",
            role="Custom Role",
            critique_focus=["custom_focus"],
            prompt_template="Custom template: {concept}",
            system_prompt="You are a custom expert persona.",
        )
        assert config.system_prompt == "You are a custom expert persona."

    def test_persona_config_default_values(self) -> None:
        """Test PersonaConfig default values for optional fields."""
        config = PersonaConfig(
            name="MinimalPersona",
            role="Minimal Role",
            critique_focus=["focus"],
            prompt_template="Template: {concept}",
        )
        assert config.description is None
        assert config.system_prompt is None


# -----------------------------------------------------------------------------
# PersonaCritique Tests
# -----------------------------------------------------------------------------


class TestPersonaCritique:
    """Test PersonaCritique model."""

    def test_persona_critique_creation(self) -> None:
        """Test creating a PersonaCritique with all fields."""
        critique = PersonaCritique(
            persona_name="CTO",
            concerns=["Scalability may be an issue with monolithic design"],
            recommendations=[
                "Consider microservices architecture",
                "Add caching layer",
            ],
            questions=["What is the expected load?"],
            severity=CritiqueSeverity.MEDIUM,
            summary="Good concept but needs architectural review",
        )
        assert critique.persona_name == "CTO"
        assert len(critique.concerns) == 1
        assert len(critique.recommendations) == 2
        assert len(critique.questions) == 1
        assert critique.severity == CritiqueSeverity.MEDIUM
        assert "architectural" in critique.summary

    def test_persona_critique_severity_levels(self) -> None:
        """Test all CritiqueSeverity enum values."""
        assert CritiqueSeverity.LOW == "low"
        assert CritiqueSeverity.MEDIUM == "medium"
        assert CritiqueSeverity.HIGH == "high"
        assert CritiqueSeverity.CRITICAL == "critical"

    def test_persona_critique_empty_lists(self) -> None:
        """Test PersonaCritique with empty lists."""
        critique = PersonaCritique(
            persona_name="UX",
            concerns=[],
            recommendations=[],
            questions=[],
            severity=CritiqueSeverity.LOW,
            summary="No major concerns",
        )
        assert critique.concerns == []
        assert critique.recommendations == []
        assert critique.questions == []

    def test_persona_critique_requires_persona_name(self) -> None:
        """Test that PersonaCritique requires persona_name."""
        with pytest.raises(Exception):
            PersonaCritique(
                concerns=[],
                recommendations=[],
                questions=[],
                severity=CritiqueSeverity.LOW,
                summary="Test",
            )  # type: ignore[call-arg]

    def test_persona_critique_requires_summary(self) -> None:
        """Test that PersonaCritique requires summary."""
        with pytest.raises(Exception):
            PersonaCritique(
                persona_name="CTO",
                concerns=[],
                recommendations=[],
                questions=[],
                severity=CritiqueSeverity.LOW,
            )  # type: ignore[call-arg]


class TestPersonaCritiqueFormatting:
    """Test PersonaCritique formatting methods."""

    def test_critique_to_markdown(self) -> None:
        """Test converting critique to markdown format."""
        critique = PersonaCritique(
            persona_name="CTO",
            concerns=["Scalability concern"],
            recommendations=["Use caching"],
            questions=["Expected load?"],
            severity=CritiqueSeverity.MEDIUM,
            summary="Needs review",
        )
        markdown = critique.to_markdown()
        assert "## CTO Critique" in markdown
        assert "Scalability concern" in markdown
        assert "Use caching" in markdown
        assert "Expected load?" in markdown
        assert "medium" in markdown.lower()

    def test_critique_to_dict(self) -> None:
        """Test converting critique to dict format."""
        critique = PersonaCritique(
            persona_name="Security",
            concerns=["Auth vulnerability"],
            recommendations=["Add MFA"],
            questions=[],
            severity=CritiqueSeverity.CRITICAL,
            summary="Critical security issues",
        )
        as_dict = critique.model_dump()
        assert as_dict["persona_name"] == "Security"
        assert as_dict["severity"] == "critical"
        assert "Auth vulnerability" in as_dict["concerns"]


# -----------------------------------------------------------------------------
# Default Persona Tests
# -----------------------------------------------------------------------------


class TestCTOPersona:
    """Test CTO_PERSONA default persona."""

    def test_cto_persona_exists(self) -> None:
        """Test that CTO_PERSONA is defined."""
        assert CTO_PERSONA is not None
        assert isinstance(CTO_PERSONA, PersonaConfig)

    def test_cto_persona_name(self) -> None:
        """Test CTO persona name and role."""
        assert CTO_PERSONA.name == "CTO"
        assert "Technology" in CTO_PERSONA.role

    def test_cto_persona_focus_areas(self) -> None:
        """Test CTO persona critique focus areas."""
        focus = [f.lower() for f in CTO_PERSONA.critique_focus]
        assert "architecture" in focus
        assert "scalability" in focus
        assert "tech_debt" in focus or "tech debt" in " ".join(focus)
        assert "maintainability" in focus

    def test_cto_persona_prompt_template(self) -> None:
        """Test CTO persona prompt template contains key elements."""
        template = CTO_PERSONA.prompt_template.lower()
        assert "{concept}" in CTO_PERSONA.prompt_template
        assert "architecture" in template or "technical" in template


class TestUXPersona:
    """Test UX_PERSONA default persona."""

    def test_ux_persona_exists(self) -> None:
        """Test that UX_PERSONA is defined."""
        assert UX_PERSONA is not None
        assert isinstance(UX_PERSONA, PersonaConfig)

    def test_ux_persona_name(self) -> None:
        """Test UX persona name and role."""
        assert UX_PERSONA.name == "UX"
        assert "User" in UX_PERSONA.role or "Experience" in UX_PERSONA.role

    def test_ux_persona_focus_areas(self) -> None:
        """Test UX persona critique focus areas."""
        focus = [f.lower() for f in UX_PERSONA.critique_focus]
        assert "usability" in focus
        assert "accessibility" in focus
        assert "user_flows" in focus or "user flows" in " ".join(focus)
        assert "onboarding" in focus

    def test_ux_persona_prompt_template(self) -> None:
        """Test UX persona prompt template contains key elements."""
        template = UX_PERSONA.prompt_template.lower()
        assert "{concept}" in UX_PERSONA.prompt_template
        assert "user" in template or "experience" in template


class TestSecurityPersona:
    """Test SECURITY_PERSONA default persona."""

    def test_security_persona_exists(self) -> None:
        """Test that SECURITY_PERSONA is defined."""
        assert SECURITY_PERSONA is not None
        assert isinstance(SECURITY_PERSONA, PersonaConfig)

    def test_security_persona_name(self) -> None:
        """Test Security persona name and role."""
        assert SECURITY_PERSONA.name == "Security"
        assert "Security" in SECURITY_PERSONA.role

    def test_security_persona_focus_areas(self) -> None:
        """Test Security persona critique focus areas."""
        focus = [f.lower() for f in SECURITY_PERSONA.critique_focus]
        assert "vulnerabilities" in focus
        assert "compliance" in focus
        assert "data_protection" in focus or "data protection" in " ".join(focus)
        assert "authentication" in focus

    def test_security_persona_prompt_template(self) -> None:
        """Test Security persona prompt template contains key elements."""
        template = SECURITY_PERSONA.prompt_template.lower()
        assert "{concept}" in SECURITY_PERSONA.prompt_template
        assert "security" in template or "vulnerability" in template


# -----------------------------------------------------------------------------
# PersonaRegistry Tests
# -----------------------------------------------------------------------------


class TestPersonaRegistry:
    """Test PersonaRegistry class."""

    def test_registry_initialization(self) -> None:
        """Test PersonaRegistry initializes with default personas."""
        registry = PersonaRegistry()
        assert registry is not None

    def test_registry_has_default_personas(self) -> None:
        """Test registry includes CTO, UX, and Security personas."""
        registry = PersonaRegistry()
        persona_names = registry.list_personas()
        assert "CTO" in persona_names
        assert "UX" in persona_names
        assert "Security" in persona_names

    def test_registry_get_persona_by_name(self) -> None:
        """Test getting a persona by name."""
        registry = PersonaRegistry()
        cto = registry.get_persona("CTO")
        assert cto is not None
        assert cto.name == "CTO"

    def test_registry_get_persona_case_insensitive(self) -> None:
        """Test getting persona is case insensitive."""
        registry = PersonaRegistry()
        cto_lower = registry.get_persona("cto")
        cto_upper = registry.get_persona("CTO")
        assert cto_lower is not None
        assert cto_upper is not None
        assert cto_lower.name == cto_upper.name

    def test_registry_get_unknown_persona(self) -> None:
        """Test getting unknown persona returns None."""
        registry = PersonaRegistry()
        unknown = registry.get_persona("Unknown")
        assert unknown is None

    def test_registry_register_custom_persona(self) -> None:
        """Test registering a custom persona."""
        registry = PersonaRegistry()
        custom = PersonaConfig(
            name="CustomExpert",
            role="Custom Expert Role",
            critique_focus=["custom_focus"],
            prompt_template="Custom: {concept}",
        )
        registry.register(custom)
        retrieved = registry.get_persona("CustomExpert")
        assert retrieved is not None
        assert retrieved.name == "CustomExpert"

    def test_registry_get_all_personas(self) -> None:
        """Test getting all registered personas."""
        registry = PersonaRegistry()
        all_personas = registry.get_all()
        assert len(all_personas) >= 3  # At least CTO, UX, Security
        names = [p.name for p in all_personas]
        assert "CTO" in names
        assert "UX" in names
        assert "Security" in names

    def test_registry_unregister_persona(self) -> None:
        """Test unregistering a persona."""
        registry = PersonaRegistry()
        custom = PersonaConfig(
            name="Temporary",
            role="Temporary Role",
            critique_focus=["temp"],
            prompt_template="Temp: {concept}",
        )
        registry.register(custom)
        assert registry.get_persona("Temporary") is not None
        registry.unregister("Temporary")
        assert registry.get_persona("Temporary") is None


# -----------------------------------------------------------------------------
# RoundtableSession Tests
# -----------------------------------------------------------------------------


class TestRoundtableSessionInitialization:
    """Test RoundtableSession initialization."""

    def test_session_initialization(self) -> None:
        """Test RoundtableSession initializes correctly."""
        mock_router = MagicMock(spec=ModelRouter)
        session = RoundtableSession(model_router=mock_router)
        assert session is not None
        assert session._model_router == mock_router

    def test_session_with_custom_registry(self) -> None:
        """Test RoundtableSession with custom registry."""
        mock_router = MagicMock(spec=ModelRouter)
        registry = PersonaRegistry()
        session = RoundtableSession(model_router=mock_router, registry=registry)
        assert session._registry == registry

    def test_session_uses_default_registry(self) -> None:
        """Test RoundtableSession uses default registry if not provided."""
        mock_router = MagicMock(spec=ModelRouter)
        session = RoundtableSession(model_router=mock_router)
        assert session._registry is not None
        assert isinstance(session._registry, PersonaRegistry)


class TestRoundtableSessionGetPersona:
    """Test RoundtableSession.get_persona method."""

    def test_get_persona_by_name(self) -> None:
        """Test getting persona by name."""
        mock_router = MagicMock(spec=ModelRouter)
        session = RoundtableSession(model_router=mock_router)
        persona = session.get_persona("CTO")
        assert persona is not None
        assert persona.name == "CTO"

    def test_get_unknown_persona(self) -> None:
        """Test getting unknown persona returns None."""
        mock_router = MagicMock(spec=ModelRouter)
        session = RoundtableSession(model_router=mock_router)
        persona = session.get_persona("NonExistent")
        assert persona is None


class TestRoundtableSessionRunCritique:
    """Test RoundtableSession.run_critique method."""

    @pytest.fixture
    def session(self) -> RoundtableSession:
        """Create a RoundtableSession with mocked router."""
        mock_router = MagicMock(spec=ModelRouter)
        return RoundtableSession(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_run_critique_returns_persona_critique(
        self, session: RoundtableSession
    ) -> None:
        """Test run_critique returns PersonaCritique."""
        mock_response = """
        {
            "concerns": ["Architecture may not scale"],
            "recommendations": ["Consider microservices"],
            "questions": ["What is the expected load?"],
            "severity": "medium",
            "summary": "Needs architectural review"
        }
        """
        session._model_router.route = AsyncMock(return_value=mock_response)

        persona = session.get_persona("CTO")
        assert persona is not None
        critique = await session.run_critique(persona, "Build a todo app")

        assert isinstance(critique, PersonaCritique)
        assert critique.persona_name == "CTO"

    @pytest.mark.asyncio
    async def test_run_critique_calls_model_router(
        self, session: RoundtableSession
    ) -> None:
        """Test run_critique calls model router with correct parameters."""
        mock_response = """
        {
            "concerns": [],
            "recommendations": [],
            "questions": [],
            "severity": "low",
            "summary": "Looks good"
        }
        """
        session._model_router.route = AsyncMock(return_value=mock_response)

        persona = session.get_persona("UX")
        assert persona is not None
        await session.run_critique(persona, "Build a mobile app")

        session._model_router.route.assert_called_once()
        call_args = session._model_router.route.call_args
        # Verify messages contain the concept
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else None)
        assert messages is not None

    @pytest.mark.asyncio
    async def test_run_critique_handles_malformed_response(
        self, session: RoundtableSession
    ) -> None:
        """Test run_critique handles malformed JSON response."""
        session._model_router.route = AsyncMock(return_value="Not valid JSON")

        persona = session.get_persona("Security")
        assert persona is not None
        # Should handle gracefully and return a critique with error indication
        critique = await session.run_critique(persona, "Test concept")
        assert isinstance(critique, PersonaCritique)
        # Should have some indication of the issue
        assert critique.summary != ""


class TestRoundtableSessionRunRoundtable:
    """Test RoundtableSession.run_roundtable method."""

    @pytest.fixture
    def session(self) -> RoundtableSession:
        """Create a RoundtableSession with mocked router."""
        mock_router = MagicMock(spec=ModelRouter)
        return RoundtableSession(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_run_roundtable_returns_all_critiques(
        self, session: RoundtableSession
    ) -> None:
        """Test run_roundtable returns critiques from all personas."""
        mock_response = """
        {
            "concerns": ["Some concern"],
            "recommendations": ["Some recommendation"],
            "questions": [],
            "severity": "low",
            "summary": "Overall good"
        }
        """
        session._model_router.route = AsyncMock(return_value=mock_response)

        critiques = await session.run_roundtable("Build an e-commerce platform")

        assert isinstance(critiques, list)
        assert len(critiques) >= 3  # At least CTO, UX, Security
        persona_names = [c.persona_name for c in critiques]
        assert "CTO" in persona_names
        assert "UX" in persona_names
        assert "Security" in persona_names

    @pytest.mark.asyncio
    async def test_run_roundtable_with_specific_personas(
        self, session: RoundtableSession
    ) -> None:
        """Test run_roundtable with specific persona subset."""
        mock_response = """
        {
            "concerns": [],
            "recommendations": [],
            "questions": [],
            "severity": "low",
            "summary": "OK"
        }
        """
        session._model_router.route = AsyncMock(return_value=mock_response)

        critiques = await session.run_roundtable(
            "Build a chat app", persona_names=["CTO", "Security"]
        )

        assert len(critiques) == 2
        persona_names = [c.persona_name for c in critiques]
        assert "CTO" in persona_names
        assert "Security" in persona_names
        assert "UX" not in persona_names

    @pytest.mark.asyncio
    async def test_run_roundtable_handles_partial_failure(
        self, session: RoundtableSession
    ) -> None:
        """Test run_roundtable handles partial failures gracefully."""
        call_count = 0

        async def mock_route(*args: Any, **kwargs: Any) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Network error")
            return """
            {
                "concerns": [],
                "recommendations": [],
                "questions": [],
                "severity": "low",
                "summary": "OK"
            }
            """

        session._model_router.route = mock_route  # type: ignore[method-assign]

        # Should still return critiques for successful personas
        critiques = await session.run_roundtable("Test concept")
        assert len(critiques) >= 2  # At least 2 should succeed


class TestRoundtableSessionSynthesizeFeedback:
    """Test RoundtableSession.synthesize_feedback method."""

    @pytest.fixture
    def session(self) -> RoundtableSession:
        """Create a RoundtableSession with mocked router."""
        mock_router = MagicMock(spec=ModelRouter)
        return RoundtableSession(model_router=mock_router)

    def test_synthesize_feedback_combines_concerns(
        self, session: RoundtableSession
    ) -> None:
        """Test synthesize_feedback combines concerns from all critiques."""
        critiques = [
            PersonaCritique(
                persona_name="CTO",
                concerns=["Scalability issue"],
                recommendations=["Use caching"],
                questions=[],
                severity=CritiqueSeverity.MEDIUM,
                summary="Architecture review needed",
            ),
            PersonaCritique(
                persona_name="Security",
                concerns=["Auth vulnerability"],
                recommendations=["Add MFA"],
                questions=[],
                severity=CritiqueSeverity.HIGH,
                summary="Security concerns",
            ),
        ]

        synthesis = session.synthesize_feedback(critiques)

        assert "Scalability issue" in synthesis.all_concerns
        assert "Auth vulnerability" in synthesis.all_concerns

    def test_synthesize_feedback_combines_recommendations(
        self, session: RoundtableSession
    ) -> None:
        """Test synthesize_feedback combines recommendations."""
        critiques = [
            PersonaCritique(
                persona_name="CTO",
                concerns=[],
                recommendations=["Use caching"],
                questions=[],
                severity=CritiqueSeverity.LOW,
                summary="OK",
            ),
            PersonaCritique(
                persona_name="UX",
                concerns=[],
                recommendations=["Add onboarding"],
                questions=[],
                severity=CritiqueSeverity.LOW,
                summary="OK",
            ),
        ]

        synthesis = session.synthesize_feedback(critiques)

        assert "Use caching" in synthesis.all_recommendations
        assert "Add onboarding" in synthesis.all_recommendations

    def test_synthesize_feedback_highest_severity(
        self, session: RoundtableSession
    ) -> None:
        """Test synthesize_feedback returns highest severity."""
        critiques = [
            PersonaCritique(
                persona_name="CTO",
                concerns=[],
                recommendations=[],
                questions=[],
                severity=CritiqueSeverity.LOW,
                summary="OK",
            ),
            PersonaCritique(
                persona_name="Security",
                concerns=["Critical issue"],
                recommendations=[],
                questions=[],
                severity=CritiqueSeverity.CRITICAL,
                summary="Critical security issue",
            ),
        ]

        synthesis = session.synthesize_feedback(critiques)

        assert synthesis.highest_severity == CritiqueSeverity.CRITICAL

    def test_synthesize_feedback_combined_summary(
        self, session: RoundtableSession
    ) -> None:
        """Test synthesize_feedback creates combined summary."""
        critiques = [
            PersonaCritique(
                persona_name="CTO",
                concerns=["Scalability"],
                recommendations=[],
                questions=[],
                severity=CritiqueSeverity.MEDIUM,
                summary="Technical review needed",
            ),
        ]

        synthesis = session.synthesize_feedback(critiques)

        assert synthesis.combined_summary != ""
        assert len(synthesis.combined_summary) > 0


class TestRoundtableSessionIntegration:
    """Integration tests for RoundtableSession."""

    @pytest.fixture
    def session(self) -> RoundtableSession:
        """Create a RoundtableSession with mocked router."""
        mock_router = MagicMock(spec=ModelRouter)
        return RoundtableSession(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_full_roundtable_workflow(
        self, session: RoundtableSession
    ) -> None:
        """Test complete roundtable workflow: run -> synthesize."""
        mock_response = """
        {
            "concerns": ["Test concern"],
            "recommendations": ["Test recommendation"],
            "questions": ["Test question?"],
            "severity": "medium",
            "summary": "Test summary"
        }
        """
        session._model_router.route = AsyncMock(return_value=mock_response)

        # Run roundtable
        critiques = await session.run_roundtable("Build a SaaS platform")

        # Synthesize feedback
        synthesis = session.synthesize_feedback(critiques)

        # Verify synthesis contains data from all personas
        assert len(synthesis.all_concerns) >= 3  # At least one per persona
        assert len(synthesis.all_recommendations) >= 3
        assert synthesis.combined_summary != ""


class TestPersonaPromptTemplates:
    """Test persona prompt templates."""

    def test_cto_prompt_covers_architecture(self) -> None:
        """Test CTO prompt template covers architecture topics."""
        template = CTO_PERSONA.prompt_template.lower()
        assert "architecture" in template or "technical" in template
        assert "scalab" in template  # scalability or scalable

    def test_ux_prompt_covers_accessibility(self) -> None:
        """Test UX prompt template covers accessibility."""
        template = UX_PERSONA.prompt_template.lower()
        assert "access" in template or "usab" in template

    def test_security_prompt_covers_vulnerabilities(self) -> None:
        """Test Security prompt template covers vulnerabilities."""
        template = SECURITY_PERSONA.prompt_template.lower()
        assert "security" in template or "vulnerab" in template


class TestCritiqueExtraction:
    """Test extracting critique from LLM responses."""

    @pytest.fixture
    def session(self) -> RoundtableSession:
        """Create a RoundtableSession with mocked router."""
        mock_router = MagicMock(spec=ModelRouter)
        return RoundtableSession(model_router=mock_router)

    @pytest.mark.asyncio
    async def test_extract_json_critique(self, session: RoundtableSession) -> None:
        """Test extracting critique from JSON response."""
        json_response = """
        ```json
        {
            "concerns": ["Performance concern"],
            "recommendations": ["Add indexing"],
            "questions": [],
            "severity": "high",
            "summary": "Performance needs attention"
        }
        ```
        """
        session._model_router.route = AsyncMock(return_value=json_response)

        persona = session.get_persona("CTO")
        assert persona is not None
        critique = await session.run_critique(persona, "Test concept")

        assert "Performance concern" in critique.concerns

    @pytest.mark.asyncio
    async def test_extract_plain_json_critique(
        self, session: RoundtableSession
    ) -> None:
        """Test extracting critique from plain JSON response."""
        plain_json = """
        {
            "concerns": ["Plain JSON concern"],
            "recommendations": [],
            "questions": [],
            "severity": "low",
            "summary": "All good"
        }
        """
        session._model_router.route = AsyncMock(return_value=plain_json)

        persona = session.get_persona("UX")
        assert persona is not None
        critique = await session.run_critique(persona, "Test")

        assert "Plain JSON concern" in critique.concerns
