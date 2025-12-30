"""Persona Engine for UAT Agent (UAT-002).

This module implements the PersonaEngine that loads and applies user personas
to modify UAT testing behavior. Each persona represents a different type of user
with unique characteristics and interaction patterns.

Personas:
    - Power User: Desktop, fast network, keyboard shortcuts
    - First-Time User: Mobile, 3G network, help-seeking behavior
    - Accessibility User: Screen reader, keyboard-only navigation

The PersonaEngine modifies UATState with persona-specific configurations:
    - Browser type (Chromium, Firefox, WebKit)
    - Viewport dimensions
    - Network conditions (speed, latency)
    - Interaction modes (keyboard, touch, mouse)
    - Behavioral patterns

Dependencies:
    - UAT-001: UAT Agent (base implementation)

Example:
    from daw_agents.agents.uat.persona_engine import PersonaEngine
    from daw_agents.agents.uat.state import UATState

    engine = PersonaEngine()
    state: UATState = {...}

    # Apply Power User persona
    updated_state = engine.apply_to_state("power_user", state)

    # Configure browser with persona settings
    persona = engine.load_persona("power_user")
    browser_config = engine.configure_browser(persona)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from daw_agents.agents.uat.state import UATState

logger = logging.getLogger(__name__)


class PersonaConfig(BaseModel):
    """Pydantic model for persona configuration.

    Attributes:
        name: Display name of the persona
        browser: Browser type (chromium, firefox, webkit)
        viewport: Viewport dimensions (width, height)
        network: Network configuration (speed, latency, bandwidth)
        behaviors: List of behavioral patterns for this persona
        interactions: Interaction configuration (mode, pace)
        description: Human-readable description (optional)
    """

    name: str = Field(description="Display name of the persona")
    browser: str = Field(description="Browser type")
    viewport: dict[str, int] = Field(description="Viewport dimensions")
    network: dict[str, Any] = Field(description="Network configuration")
    behaviors: list[str] = Field(description="Behavioral patterns")
    interactions: dict[str, str] = Field(description="Interaction configuration")
    description: str | None = Field(default=None, description="Description")


class PersonaEngine:
    """Engine for loading and applying user personas to UAT testing.

    The PersonaEngine reads persona definitions from a YAML file and applies them
    to UATState objects to modify testing behavior. Each persona represents a
    different user archetype with unique characteristics.

    Attributes:
        personas_path: Path to the personas YAML file
        personas: Dictionary of loaded persona configurations

    Example:
        engine = PersonaEngine()

        # List available personas
        available = engine.list_personas()

        # Load specific persona
        persona = engine.load_persona("power_user")

        # Apply to state
        state: UATState = {...}
        updated_state = engine.apply_to_state("power_user", state)
    """

    def __init__(self, personas_path: str | None = None) -> None:
        """Initialize the PersonaEngine.

        Args:
            personas_path: Optional path to personas YAML file.
                          If None, uses default personas.yaml in uat package.

        Raises:
            FileNotFoundError: If personas file doesn't exist
            ValueError: If personas file is invalid YAML
        """
        if personas_path is None:
            # Default to personas.yaml in same directory as this module
            personas_path = str(Path(__file__).parent / "personas.yaml")

        self.personas_path = personas_path
        self.personas: dict[str, dict[str, Any]] = {}

        self._load_personas()

        logger.info(
            "PersonaEngine initialized with %d personas from %s",
            len(self.personas),
            self.personas_path,
        )

    def _load_personas(self) -> None:
        """Load personas from YAML file.

        Raises:
            FileNotFoundError: If personas file doesn't exist
            ValueError: If YAML is invalid or doesn't contain personas section
        """
        personas_file = Path(self.personas_path)

        if not personas_file.exists():
            raise FileNotFoundError(
                f"Personas file not found: {self.personas_path}"
            )

        try:
            with open(personas_file) as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict) or "personas" not in data:
                raise ValueError(
                    f"Invalid personas file: missing 'personas' section in {self.personas_path}"
                )

            self.personas = data["personas"]

            logger.debug("Loaded %d personas: %s", len(self.personas), list(self.personas.keys()))

        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file {self.personas_path}: {e}") from e

    def load_persona(self, persona_name: str) -> dict[str, Any]:
        """Load a specific persona by name.

        Args:
            persona_name: Name of the persona to load
                         (e.g., "power_user", "first_time_user")

        Returns:
            Dictionary containing persona configuration

        Raises:
            ValueError: If persona_name is not found
        """
        if persona_name not in self.personas:
            available = ", ".join(sorted(self.personas.keys()))
            raise ValueError(
                f"Persona '{persona_name}' not found. "
                f"Available personas: {available}"
            )

        persona = self.personas[persona_name]
        logger.debug("Loaded persona: %s (%s)", persona_name, persona.get("name"))

        return persona

    def list_personas(self) -> list[str]:
        """List all available persona names.

        Returns:
            List of persona names
        """
        return list(self.personas.keys())

    def apply_to_state(
        self,
        persona_name: str,
        state: UATState,
    ) -> UATState:
        """Apply a persona configuration to a UATState.

        Modifies the state with persona-specific settings:
        - browser_type: Updated based on persona
        - viewport: Added with persona's viewport dimensions
        - network: Added with persona's network configuration
        - interaction_mode: Added with persona's interaction style
        - screen_reader: Added if persona requires screen reader

        Args:
            persona_name: Name of persona to apply
            state: UATState to modify

        Returns:
            Updated UATState with persona configuration applied

        Raises:
            ValueError: If persona_name is not found
        """
        persona = self.load_persona(persona_name)

        # Create a copy of the state to avoid mutating the original
        updated_state = dict(state)

        # Apply browser type
        if "browser" in persona:
            updated_state["browser_type"] = persona["browser"]

        # Apply viewport configuration
        if "viewport" in persona:
            updated_state["viewport"] = persona["viewport"]

        # Apply network configuration
        if "network" in persona:
            updated_state["network"] = persona["network"]

        # Apply interaction mode
        if "interactions" in persona:
            interaction_mode = persona["interactions"].get("mode", "mixed")
            updated_state["interaction_mode"] = interaction_mode

        # Apply screen reader settings if applicable
        if "screen_reader" in persona.get("behaviors", []):
            updated_state["screen_reader"] = {
                "enabled": True,
                "type": persona.get("screen_reader_type", "nvda"),
            }

        # Apply behavioral flags
        if "behaviors" in persona:
            updated_state["persona_behaviors"] = persona["behaviors"]

        logger.info(
            "Applied persona '%s' to state (browser: %s, viewport: %s)",
            persona_name,
            updated_state.get("browser_type"),
            updated_state.get("viewport"),
        )

        return updated_state  # type: ignore[return-value]

    def configure_browser(self, persona: dict[str, Any]) -> dict[str, Any]:
        """Configure browser settings based on persona.

        Generates browser configuration suitable for Playwright MCP based on
        the persona's characteristics.

        Args:
            persona: Persona configuration dictionary

        Returns:
            Dictionary with browser configuration:
                - browser_type: Browser to use
                - viewport: Viewport dimensions
                - network: Network emulation settings
                - device_scale_factor: For mobile devices
                - is_mobile: Mobile mode flag
                - has_touch: Touch events support
                - forced_colors: Accessibility color mode
                - color_scheme: Light/dark mode
                - emulation: Additional emulation settings
        """
        config: dict[str, Any] = {
            "browser_type": persona.get("browser", "chromium"),
            "viewport": persona.get("viewport", {"width": 1920, "height": 1080}),
        }

        # Network configuration
        network = persona.get("network", {})
        speed = network.get("speed", "fast")

        config["network"] = {
            "type": speed,
            "latency": self._get_latency_for_speed(speed),
            "download": self._get_download_for_speed(speed),
            "upload": self._get_upload_for_speed(speed),
        }

        # Mobile device configuration
        viewport = config["viewport"]
        is_mobile = viewport["width"] <= 768

        if is_mobile:
            config["device_scale_factor"] = 2
            config["is_mobile"] = True
            config["has_touch"] = True
            config["user_agent"] = (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            )
        else:
            config["device_scale_factor"] = 1
            config["is_mobile"] = False
            config["has_touch"] = False

        # Accessibility configuration
        behaviors = persona.get("behaviors", [])
        if "screen_reader" in behaviors:
            config["forced_colors"] = "active"
            config["color_scheme"] = "dark"
            config["accessibility_features"] = {
                "reduced_motion": True,
                "high_contrast": True,
            }

        # Emulation settings
        config["emulation"] = {
            "geolocation": None,
            "timezone": "America/New_York",
            "locale": "en-US",
        }

        logger.debug(
            "Configured browser for persona: %s (mobile: %s, network: %s)",
            persona.get("name"),
            is_mobile,
            speed,
        )

        return config

    def _get_latency_for_speed(self, speed: str) -> int:
        """Get network latency in ms for speed setting.

        Args:
            speed: Network speed (fast, slow_3g, etc.)

        Returns:
            Latency in milliseconds
        """
        latency_map = {
            "fast": 10,
            "4g": 50,
            "slow_3g": 400,
            "3g": 200,
            "2g": 800,
            "offline": 0,
        }
        return latency_map.get(speed, 10)

    def _get_download_for_speed(self, speed: str) -> int:
        """Get download speed in Kbps for speed setting.

        Args:
            speed: Network speed (fast, slow_3g, etc.)

        Returns:
            Download speed in Kbps
        """
        download_map = {
            "fast": 100000,  # 100 Mbps
            "4g": 20000,  # 20 Mbps
            "slow_3g": 750,  # 750 Kbps
            "3g": 3000,  # 3 Mbps
            "2g": 250,  # 250 Kbps
            "offline": 0,
        }
        return download_map.get(speed, 100000)

    def _get_upload_for_speed(self, speed: str) -> int:
        """Get upload speed in Kbps for speed setting.

        Args:
            speed: Network speed (fast, slow_3g, etc.)

        Returns:
            Upload speed in Kbps
        """
        upload_map = {
            "fast": 50000,  # 50 Mbps
            "4g": 10000,  # 10 Mbps
            "slow_3g": 250,  # 250 Kbps
            "3g": 1000,  # 1 Mbps
            "2g": 100,  # 100 Kbps
            "offline": 0,
        }
        return upload_map.get(speed, 50000)
