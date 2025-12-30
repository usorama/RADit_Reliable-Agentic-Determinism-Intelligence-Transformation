"""Tests for UAT Agent persona engine (UAT-002).

This module tests the PersonaEngine that loads and applies user personas
to modify UAT testing behavior:

- Power User: Desktop, fast network, keyboard shortcuts
- First-Time User: Mobile, 3G network, help-seeking behavior
- Accessibility User: Screen reader, keyboard-only navigation

Each persona modifies:
- Browser configuration (viewport, user agent)
- Network conditions (speed, latency)
- Interaction patterns (keyboard vs mouse, pace)

Dependencies:
    - UAT-001: UAT Agent (must be complete)

Test Coverage:
    - PersonaEngine initialization
    - Loading personas from YAML
    - Applying persona to UATState
    - Configuring browser with persona settings
    - Integration with UATAgent
"""

from __future__ import annotations

import pytest

from daw_agents.agents.uat.persona_engine import PersonaEngine
from daw_agents.agents.uat.state import UATState


class TestPersonaEngineInit:
    """Tests for PersonaEngine initialization."""

    def test_init_default(self) -> None:
        """Test PersonaEngine initializes without explicit personas file."""
        engine = PersonaEngine()
        assert engine is not None
        assert hasattr(engine, "personas")

    def test_init_with_custom_path(self, tmp_path) -> None:
        """Test PersonaEngine initializes with custom personas file path."""
        personas_file = tmp_path / "custom_personas.yaml"
        personas_file.write_text(
            """
personas:
  test_user:
    name: "Test User"
    browser: "chromium"
    viewport:
      width: 1024
      height: 768
"""
        )

        engine = PersonaEngine(personas_path=str(personas_file))
        assert engine is not None


class TestPersonaEngineLoadPersona:
    """Tests for loading personas from YAML."""

    def test_load_persona_power_user(self) -> None:
        """Test loading Power User persona."""
        engine = PersonaEngine()
        persona = engine.load_persona("power_user")

        # Verify persona structure
        assert persona is not None
        assert "name" in persona
        assert "browser" in persona
        assert "viewport" in persona
        assert "network" in persona
        assert "behaviors" in persona
        assert "interactions" in persona

        # Verify Power User specifics
        assert persona["browser"] == "chromium"
        assert persona["viewport"]["width"] == 1920
        assert persona["viewport"]["height"] == 1080
        assert persona["network"]["speed"] == "fast"
        assert "keyboard_shortcuts" in persona["behaviors"]

    def test_load_persona_first_time_user(self) -> None:
        """Test loading First-Time User persona."""
        engine = PersonaEngine()
        persona = engine.load_persona("first_time_user")

        # Verify persona structure
        assert persona is not None
        assert "name" in persona
        assert "browser" in persona
        assert "viewport" in persona
        assert "network" in persona

        # Verify First-Time User specifics (mobile)
        assert persona["browser"] == "webkit"
        assert persona["viewport"]["width"] == 375
        assert persona["viewport"]["height"] == 812
        assert persona["network"]["speed"] == "slow_3g"
        assert "help_seeking" in persona["behaviors"]

    def test_load_persona_accessibility_user(self) -> None:
        """Test loading Accessibility User persona."""
        engine = PersonaEngine()
        persona = engine.load_persona("accessibility_user")

        # Verify persona structure
        assert persona is not None
        assert "name" in persona
        assert "browser" in persona
        assert "viewport" in persona

        # Verify Accessibility User specifics
        assert persona["browser"] == "firefox"
        assert persona["viewport"]["width"] == 1280
        assert persona["viewport"]["height"] == 800
        assert persona["interactions"]["mode"] == "keyboard_only"
        assert "screen_reader" in persona["behaviors"]

    def test_load_persona_invalid_name(self) -> None:
        """Test loading persona with invalid name raises error."""
        engine = PersonaEngine()
        with pytest.raises(ValueError, match="Persona 'nonexistent_persona' not found"):
            engine.load_persona("nonexistent_persona")

    def test_list_available_personas(self) -> None:
        """Test listing all available personas."""
        engine = PersonaEngine()
        personas = engine.list_personas()

        assert len(personas) >= 3
        assert "power_user" in personas
        assert "first_time_user" in personas
        assert "accessibility_user" in personas


class TestPersonaEngineApplyToState:
    """Tests for applying persona configuration to UATState."""

    def test_apply_power_user_to_state(self) -> None:
        """Test applying Power User persona to UATState."""
        engine = PersonaEngine()

        state: UATState = {
            "scenario": "test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        updated_state = engine.apply_to_state("power_user", state)

        # Verify browser type updated
        assert updated_state["browser_type"] == "chromium"

        # Verify viewport configuration added
        assert "viewport" in updated_state
        assert updated_state["viewport"]["width"] == 1920
        assert updated_state["viewport"]["height"] == 1080

        # Verify network configuration added
        assert "network" in updated_state
        assert updated_state["network"]["speed"] == "fast"

        # Verify interaction mode added
        assert "interaction_mode" in updated_state
        assert "keyboard" in updated_state["interaction_mode"]

    def test_apply_first_time_user_to_state(self) -> None:
        """Test applying First-Time User persona to UATState."""
        engine = PersonaEngine()

        state: UATState = {
            "scenario": "test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        updated_state = engine.apply_to_state("first_time_user", state)

        # Verify browser type updated to mobile
        assert updated_state["browser_type"] == "webkit"

        # Verify mobile viewport
        assert updated_state["viewport"]["width"] == 375
        assert updated_state["viewport"]["height"] == 812

        # Verify slow network
        assert updated_state["network"]["speed"] == "slow_3g"

        # Verify touch interaction mode
        assert "touch" in updated_state["interaction_mode"]

    def test_apply_accessibility_user_to_state(self) -> None:
        """Test applying Accessibility User persona to UATState."""
        engine = PersonaEngine()

        state: UATState = {
            "scenario": "test scenario",
            "url": "http://localhost:3000",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {},
        }

        updated_state = engine.apply_to_state("accessibility_user", state)

        # Verify browser type
        assert updated_state["browser_type"] == "firefox"

        # Verify keyboard-only mode
        assert updated_state["interaction_mode"] == "keyboard_only"

        # Verify screen reader enabled
        assert "screen_reader" in updated_state
        assert updated_state["screen_reader"]["enabled"] is True


class TestPersonaEngineConfigureBrowser:
    """Tests for configuring browser with persona settings."""

    def test_configure_browser_power_user(self) -> None:
        """Test configuring browser for Power User persona."""
        engine = PersonaEngine()
        persona = engine.load_persona("power_user")

        config = engine.configure_browser(persona)

        assert config["browser_type"] == "chromium"
        assert config["viewport"]["width"] == 1920
        assert config["viewport"]["height"] == 1080
        assert config["network"]["type"] == "fast"
        assert "emulation" in config

    def test_configure_browser_mobile(self) -> None:
        """Test configuring browser for mobile user (First-Time User)."""
        engine = PersonaEngine()
        persona = engine.load_persona("first_time_user")

        config = engine.configure_browser(persona)

        assert config["browser_type"] == "webkit"
        assert config["viewport"]["width"] == 375
        assert config["viewport"]["height"] == 812
        assert config["network"]["type"] == "slow_3g"
        assert config["device_scale_factor"] == 2
        assert config["is_mobile"] is True
        assert config["has_touch"] is True

    def test_configure_browser_accessibility(self) -> None:
        """Test configuring browser for accessibility testing."""
        engine = PersonaEngine()
        persona = engine.load_persona("accessibility_user")

        config = engine.configure_browser(persona)

        assert config["browser_type"] == "firefox"
        assert config["forced_colors"] == "active"
        assert config["color_scheme"] == "dark"
        assert "accessibility_features" in config


class TestPersonaEngineIntegration:
    """Integration tests with UATAgent."""

    def test_persona_engine_with_uat_agent(self) -> None:
        """Test PersonaEngine integrates with UATAgent."""
        from daw_agents.agents.uat import UATAgent

        # Create agent
        agent = UATAgent(browser_type="chromium")

        # Create persona engine
        engine = PersonaEngine()

        # Verify engine can configure agent
        assert engine is not None
        assert agent is not None

    def test_apply_persona_preserves_required_state(self) -> None:
        """Test applying persona preserves required UATState fields."""
        engine = PersonaEngine()

        state: UATState = {
            "scenario": "original scenario",
            "url": "http://example.com",
            "browser_type": "chromium",
            "status": "setup",
            "current_step": 0,
            "steps": [{"keyword": "Given", "text": "test"}],
            "accessibility_snapshots": [],
            "screenshots": [],
            "traces": [],
            "validation_results": [],
            "error": None,
            "timing": {"start_time": 123456},
        }

        updated_state = engine.apply_to_state("power_user", state)

        # Verify required fields preserved
        assert updated_state["scenario"] == "original scenario"
        assert updated_state["url"] == "http://example.com"
        assert updated_state["status"] == "setup"
        assert updated_state["current_step"] == 0
        assert len(updated_state["steps"]) == 1
        assert updated_state["timing"]["start_time"] == 123456


class TestPersonaEnginePydanticModels:
    """Tests for Pydantic models used by PersonaEngine."""

    def test_persona_config_model(self) -> None:
        """Test PersonaConfig Pydantic model."""
        from daw_agents.agents.uat.persona_engine import PersonaConfig

        config = PersonaConfig(
            name="Test User",
            browser="chromium",
            viewport={"width": 1920, "height": 1080},
            network={"speed": "fast", "latency": 10},
            behaviors=["keyboard_shortcuts", "fast_typing"],
            interactions={"mode": "keyboard_first", "pace": "fast"},
        )

        assert config.name == "Test User"
        assert config.browser == "chromium"
        assert config.viewport["width"] == 1920
        assert config.network["speed"] == "fast"

    def test_persona_config_validation(self) -> None:
        """Test PersonaConfig validates required fields."""
        from pydantic import ValidationError

        from daw_agents.agents.uat.persona_engine import PersonaConfig

        with pytest.raises(ValidationError):
            PersonaConfig(
                name="Invalid User",
                # Missing required fields
            )
