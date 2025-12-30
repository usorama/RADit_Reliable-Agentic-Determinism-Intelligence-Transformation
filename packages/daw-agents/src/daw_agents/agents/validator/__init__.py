"""Validator Agent module (VALIDATOR-001, VALIDATOR-002).

This module exports the Validator Agent and related models for code validation.
The Validator Agent is architecturally DISTINCT from the Sandbox (CORE-004):
- Validator: Reviews code using LLM for correctness, security, style
- Sandbox: Executes code in isolated E2B environment

CRITICAL ARCHITECTURE DECISION:
The Validator MUST use TaskType.VALIDATION for model routing to ensure
cross-validation with a different model than the Executor (TaskType.CODING).

Public API (VALIDATOR-001):
- ValidatorAgent: Main agent class with validate() method
- ValidationResult: Pydantic model for validation outcomes
- ValidationState: TypedDict for LangGraph state
- SecurityFinding: Individual security vulnerability
- StyleIssue: Code style/linting issue
- TestResult: Test execution results

Public API (VALIDATOR-002 - Multi-Model Ensemble):
- ValidationEnsemble: Ensemble validation with 2+ models
- EnsembleConfig: Configuration for ensemble behavior
- EnsembleResult: Aggregated result with consensus status
- ModelVote: Individual model validation result
- VotingStrategy: Enum for voting strategies (majority, unanimous, weighted)
- ValidationType: Enum for validation context types
- ConsensusStatus: Enum for consensus outcomes
"""

from daw_agents.agents.validator.agent import ValidatorAgent
from daw_agents.agents.validator.ensemble import (
    ConsensusStatus,
    EnsembleConfig,
    EnsembleResult,
    ModelVote,
    ValidationEnsemble,
    ValidationType,
    VotingStrategy,
)
from daw_agents.agents.validator.models import (
    SecurityFinding,
    StyleIssue,
    TestResult,
    ValidationResult,
)
from daw_agents.agents.validator.state import ValidationState

__all__ = [
    # VALIDATOR-001
    "ValidatorAgent",
    "ValidationResult",
    "ValidationState",
    "SecurityFinding",
    "StyleIssue",
    "TestResult",
    # VALIDATOR-002 - Multi-Model Ensemble
    "ValidationEnsemble",
    "EnsembleConfig",
    "EnsembleResult",
    "ModelVote",
    "VotingStrategy",
    "ValidationType",
    "ConsensusStatus",
]
