"""
Evolution module for self-learning foundation.

This module provides:
- ExperienceLogger: Store and query task completion experiences
- Schemas: Pydantic models for Experience, Skill, Artifact, Insight
"""

from daw_agents.evolution.experience_logger import ExperienceLogger
from daw_agents.evolution.schemas import (
    Artifact,
    ArtifactType,
    Experience,
    ExperienceQuery,
    Insight,
    Skill,
    SuccessRate,
    TaskType,
)

__all__ = [
    "ExperienceLogger",
    "Experience",
    "ExperienceQuery",
    "Skill",
    "Artifact",
    "ArtifactType",
    "Insight",
    "SuccessRate",
    "TaskType",
]
