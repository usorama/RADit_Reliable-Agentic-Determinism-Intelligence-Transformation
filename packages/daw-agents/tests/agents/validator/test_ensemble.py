"""
Tests for the Multi-Model Validation Ensemble (VALIDATOR-002).

These tests verify the ensemble validation implementation:
1. EnsembleConfig - Configuration for ensemble (models, threshold, voting_strategy)
2. ModelVote - Individual model validation result
3. EnsembleResult - Aggregated result with consensus status
4. ValidationEnsemble class with methods:
   - validate_with_ensemble() - Run validation through multiple models
   - aggregate_votes() - Combine model results
   - determine_consensus() - Apply voting strategy
5. Voting strategies: majority, unanimous, weighted
6. Model disagreement handling
7. Configurable thresholds
8. Different model combinations (Claude + GPT-4o)

Based on FR-04.2: Multi-Model Validation Ensemble
- Use 2+ models for critical validations
- Voting/consensus mechanism for pass/fail decisions
- Configurable: which validations require ensemble
- Security-critical and production deployments require ensemble
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestEnsembleConfig:
    """Test the EnsembleConfig configuration model."""

    def test_ensemble_config_import(self) -> None:
        """Test that EnsembleConfig can be imported."""
        from daw_agents.agents.validator.ensemble import EnsembleConfig

        assert EnsembleConfig is not None

    def test_ensemble_config_with_defaults(self) -> None:
        """Test creating EnsembleConfig with default values."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            VotingStrategy,
        )

        config = EnsembleConfig()

        # Default should use at least 2 models
        assert len(config.models) >= 2
        # Default voting strategy should be majority
        assert config.voting_strategy == VotingStrategy.MAJORITY
        # Default threshold should be reasonable (e.g., 0.5 for majority)
        assert 0.0 <= config.threshold <= 1.0

    def test_ensemble_config_custom_models(self) -> None:
        """Test creating EnsembleConfig with custom models."""
        from daw_agents.agents.validator.ensemble import EnsembleConfig

        config = EnsembleConfig(
            models=["gpt-4o", "claude-3-5-sonnet-20241022", "gemini-pro"]
        )

        assert len(config.models) == 3
        assert "gpt-4o" in config.models
        assert "claude-3-5-sonnet-20241022" in config.models

    def test_ensemble_config_voting_strategies(self) -> None:
        """Test that all voting strategies are supported."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            VotingStrategy,
        )

        # Majority voting
        config_majority = EnsembleConfig(voting_strategy=VotingStrategy.MAJORITY)
        assert config_majority.voting_strategy == VotingStrategy.MAJORITY

        # Unanimous voting
        config_unanimous = EnsembleConfig(voting_strategy=VotingStrategy.UNANIMOUS)
        assert config_unanimous.voting_strategy == VotingStrategy.UNANIMOUS

        # Weighted voting
        config_weighted = EnsembleConfig(voting_strategy=VotingStrategy.WEIGHTED)
        assert config_weighted.voting_strategy == VotingStrategy.WEIGHTED

    def test_ensemble_config_weighted_models(self) -> None:
        """Test weighted voting configuration."""
        from daw_agents.agents.validator.ensemble import EnsembleConfig

        weights = {
            "gpt-4o": 1.0,
            "claude-3-5-sonnet-20241022": 1.2,  # Higher weight for Claude
        }
        config = EnsembleConfig(
            models=["gpt-4o", "claude-3-5-sonnet-20241022"],
            model_weights=weights,
        )

        assert config.model_weights["claude-3-5-sonnet-20241022"] > config.model_weights["gpt-4o"]

    def test_ensemble_config_requires_minimum_models(self) -> None:
        """Test that ensemble requires at least 2 models."""
        from pydantic import ValidationError

        from daw_agents.agents.validator.ensemble import EnsembleConfig

        with pytest.raises(ValidationError):
            EnsembleConfig(models=["gpt-4o"])  # Only 1 model

    def test_ensemble_config_validation_types(self) -> None:
        """Test configuration for which validation types require ensemble."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ValidationType,
        )

        config = EnsembleConfig(
            require_ensemble_for=[
                ValidationType.SECURITY,
                ValidationType.PRODUCTION,
            ]
        )

        assert ValidationType.SECURITY in config.require_ensemble_for
        assert ValidationType.PRODUCTION in config.require_ensemble_for


class TestModelVote:
    """Test the ModelVote model for individual model results."""

    def test_model_vote_import(self) -> None:
        """Test that ModelVote can be imported."""
        from daw_agents.agents.validator.ensemble import ModelVote

        assert ModelVote is not None

    def test_model_vote_creation_pass(self) -> None:
        """Test creating a passing ModelVote."""
        from daw_agents.agents.validator.ensemble import ModelVote

        vote = ModelVote(
            model_id="gpt-4o",
            passed=True,
            confidence=0.95,
            reasoning="Code follows best practices and passes all validation checks.",
            issues_found=[],
        )

        assert vote.model_id == "gpt-4o"
        assert vote.passed is True
        assert vote.confidence == 0.95
        assert len(vote.issues_found) == 0

    def test_model_vote_creation_fail(self) -> None:
        """Test creating a failing ModelVote."""
        from daw_agents.agents.validator.ensemble import ModelVote

        vote = ModelVote(
            model_id="claude-3-5-sonnet-20241022",
            passed=False,
            confidence=0.88,
            reasoning="Found potential SQL injection vulnerability.",
            issues_found=["SQL injection in query function"],
        )

        assert vote.passed is False
        assert len(vote.issues_found) == 1
        assert "SQL injection" in vote.issues_found[0]

    def test_model_vote_validation_details(self) -> None:
        """Test that ModelVote includes validation details."""
        from daw_agents.agents.validator.ensemble import ModelVote

        vote = ModelVote(
            model_id="gpt-4o",
            passed=True,
            confidence=0.92,
            reasoning="All security checks pass.",
            issues_found=[],
            validation_time_ms=250,
            tokens_used=1500,
        )

        assert vote.validation_time_ms == 250
        assert vote.tokens_used == 1500


class TestEnsembleResult:
    """Test the EnsembleResult aggregated result model."""

    def test_ensemble_result_import(self) -> None:
        """Test that EnsembleResult can be imported."""
        from daw_agents.agents.validator.ensemble import EnsembleResult

        assert EnsembleResult is not None

    def test_ensemble_result_consensus_pass(self) -> None:
        """Test EnsembleResult with consensus pass."""
        from daw_agents.agents.validator.ensemble import (
            ConsensusStatus,
            EnsembleResult,
            ModelVote,
        )

        votes = [
            ModelVote(model_id="gpt-4o", passed=True, confidence=0.95, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="claude-3-5-sonnet-20241022", passed=True, confidence=0.92, reasoning="Pass", issues_found=[]),
        ]

        result = EnsembleResult(
            consensus_status=ConsensusStatus.CONSENSUS_PASS,
            final_decision=True,
            votes=votes,
            consensus_confidence=0.935,
            reasoning="Both models agree: code passes validation.",
        )

        assert result.consensus_status == ConsensusStatus.CONSENSUS_PASS
        assert result.final_decision is True
        assert len(result.votes) == 2

    def test_ensemble_result_consensus_fail(self) -> None:
        """Test EnsembleResult with consensus fail."""
        from daw_agents.agents.validator.ensemble import (
            ConsensusStatus,
            EnsembleResult,
            ModelVote,
        )

        votes = [
            ModelVote(model_id="gpt-4o", passed=False, confidence=0.90, reasoning="Security issue found", issues_found=["SQL injection"]),
            ModelVote(model_id="claude-3-5-sonnet-20241022", passed=False, confidence=0.88, reasoning="Vulnerability detected", issues_found=["SQL injection"]),
        ]

        result = EnsembleResult(
            consensus_status=ConsensusStatus.CONSENSUS_FAIL,
            final_decision=False,
            votes=votes,
            consensus_confidence=0.89,
            reasoning="Both models agree: code fails validation due to SQL injection.",
        )

        assert result.consensus_status == ConsensusStatus.CONSENSUS_FAIL
        assert result.final_decision is False

    def test_ensemble_result_split_decision(self) -> None:
        """Test EnsembleResult with split (disagreement) decision."""
        from daw_agents.agents.validator.ensemble import (
            ConsensusStatus,
            EnsembleResult,
            ModelVote,
        )

        votes = [
            ModelVote(model_id="gpt-4o", passed=True, confidence=0.75, reasoning="Looks okay", issues_found=[]),
            ModelVote(model_id="claude-3-5-sonnet-20241022", passed=False, confidence=0.82, reasoning="Potential issue", issues_found=["Minor concern"]),
        ]

        result = EnsembleResult(
            consensus_status=ConsensusStatus.SPLIT,
            final_decision=False,  # Conservative: fail on split
            votes=votes,
            consensus_confidence=0.5,
            reasoning="Models disagree. Conservative decision: fail.",
            requires_human_review=True,
        )

        assert result.consensus_status == ConsensusStatus.SPLIT
        assert result.requires_human_review is True

    def test_ensemble_result_aggregated_issues(self) -> None:
        """Test that EnsembleResult aggregates issues from all models."""
        from daw_agents.agents.validator.ensemble import (
            ConsensusStatus,
            EnsembleResult,
            ModelVote,
        )

        votes = [
            ModelVote(model_id="gpt-4o", passed=False, confidence=0.9, reasoning="Issues found", issues_found=["Issue A", "Issue B"]),
            ModelVote(model_id="claude-3-5-sonnet-20241022", passed=False, confidence=0.85, reasoning="Issues found", issues_found=["Issue B", "Issue C"]),
        ]

        result = EnsembleResult(
            consensus_status=ConsensusStatus.CONSENSUS_FAIL,
            final_decision=False,
            votes=votes,
            consensus_confidence=0.875,
            reasoning="Multiple issues found.",
            aggregated_issues=["Issue A", "Issue B", "Issue C"],
        )

        # Should have deduplicated issues
        assert len(result.aggregated_issues) == 3


class TestVotingStrategy:
    """Test the VotingStrategy enum."""

    def test_voting_strategy_import(self) -> None:
        """Test that VotingStrategy can be imported."""
        from daw_agents.agents.validator.ensemble import VotingStrategy

        assert VotingStrategy is not None

    def test_voting_strategy_values(self) -> None:
        """Test that all voting strategies exist."""
        from daw_agents.agents.validator.ensemble import VotingStrategy

        assert hasattr(VotingStrategy, "MAJORITY")
        assert hasattr(VotingStrategy, "UNANIMOUS")
        assert hasattr(VotingStrategy, "WEIGHTED")


class TestValidationType:
    """Test the ValidationType enum for ensemble requirements."""

    def test_validation_type_import(self) -> None:
        """Test that ValidationType can be imported."""
        from daw_agents.agents.validator.ensemble import ValidationType

        assert ValidationType is not None

    def test_validation_type_values(self) -> None:
        """Test that validation types exist."""
        from daw_agents.agents.validator.ensemble import ValidationType

        assert hasattr(ValidationType, "SECURITY")
        assert hasattr(ValidationType, "PRODUCTION")
        assert hasattr(ValidationType, "STANDARD")


class TestConsensusStatus:
    """Test the ConsensusStatus enum."""

    def test_consensus_status_import(self) -> None:
        """Test that ConsensusStatus can be imported."""
        from daw_agents.agents.validator.ensemble import ConsensusStatus

        assert ConsensusStatus is not None

    def test_consensus_status_values(self) -> None:
        """Test that consensus status values exist."""
        from daw_agents.agents.validator.ensemble import ConsensusStatus

        assert hasattr(ConsensusStatus, "CONSENSUS_PASS")
        assert hasattr(ConsensusStatus, "CONSENSUS_FAIL")
        assert hasattr(ConsensusStatus, "SPLIT")


class TestValidationEnsemble:
    """Test the ValidationEnsemble class."""

    def test_validation_ensemble_import(self) -> None:
        """Test that ValidationEnsemble can be imported."""
        from daw_agents.agents.validator.ensemble import ValidationEnsemble

        assert ValidationEnsemble is not None

    def test_validation_ensemble_initialization(self) -> None:
        """Test ValidationEnsemble initialization with ModelRouter."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ValidationEnsemble,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig()
        ensemble = ValidationEnsemble(model_router=router, config=config)

        assert ensemble.model_router is router
        assert ensemble.config is config

    def test_validation_ensemble_default_config(self) -> None:
        """Test ValidationEnsemble with default configuration."""
        from daw_agents.agents.validator.ensemble import ValidationEnsemble
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        ensemble = ValidationEnsemble(model_router=router)

        assert ensemble.config is not None
        assert len(ensemble.config.models) >= 2


class TestValidateWithEnsemble:
    """Test the validate_with_ensemble method."""

    @pytest.fixture
    def mock_router(self) -> MagicMock:
        """Create a mock ModelRouter."""
        router = MagicMock()
        router.route = AsyncMock(return_value="Code passes all validation checks.")
        return router

    @pytest.mark.asyncio
    async def test_validate_with_ensemble_calls_multiple_models(
        self, mock_router: MagicMock
    ) -> None:
        """Test that validate_with_ensemble calls multiple models."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ValidationEnsemble,
        )

        config = EnsembleConfig(models=["gpt-4o", "claude-3-5-sonnet-20241022"])
        ensemble = ValidationEnsemble(model_router=mock_router, config=config)

        await ensemble.validate_with_ensemble(
            code="def hello(): return 'hello'",
            tests="def test_hello(): assert hello() == 'hello'",
            policies=["security", "style"],
        )

        # Should have called router for each model
        assert mock_router.route.call_count >= 2

    @pytest.mark.asyncio
    async def test_validate_with_ensemble_returns_ensemble_result(
        self, mock_router: MagicMock
    ) -> None:
        """Test that validate_with_ensemble returns EnsembleResult."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            EnsembleResult,
            ValidationEnsemble,
        )

        config = EnsembleConfig(models=["gpt-4o", "claude-3-5-sonnet-20241022"])
        ensemble = ValidationEnsemble(model_router=mock_router, config=config)

        result = await ensemble.validate_with_ensemble(
            code="def hello(): return 'hello'",
            tests="def test_hello(): assert hello() == 'hello'",
            policies=["security"],
        )

        assert isinstance(result, EnsembleResult)

    @pytest.mark.asyncio
    async def test_validate_with_ensemble_parallel_execution(
        self, mock_router: MagicMock
    ) -> None:
        """Test that model calls are executed in parallel."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ValidationEnsemble,
        )

        # Track call timing
        call_times: list[float] = []

        async def mock_route(*args: Any, **kwargs: Any) -> str:
            import time
            call_times.append(time.time())
            await asyncio.sleep(0.1)  # Simulate model latency
            return "Validation passed"

        mock_router.route = mock_route

        config = EnsembleConfig(models=["model1", "model2", "model3"])
        ensemble = ValidationEnsemble(model_router=mock_router, config=config)

        await ensemble.validate_with_ensemble(
            code="code",
            tests="tests",
            policies=[],
        )

        # All calls should have started within a small window (parallel)
        if len(call_times) >= 2:
            time_diff = max(call_times) - min(call_times)
            assert time_diff < 0.05, "Model calls should be parallel, not sequential"


class TestAggregateVotes:
    """Test the aggregate_votes method."""

    def test_aggregate_votes_all_pass(self) -> None:
        """Test aggregating votes when all models pass."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ModelVote,
            ValidationEnsemble,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig()
        ensemble = ValidationEnsemble(model_router=router, config=config)

        votes = [
            ModelVote(model_id="gpt-4o", passed=True, confidence=0.95, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="claude-3-5-sonnet-20241022", passed=True, confidence=0.92, reasoning="Pass", issues_found=[]),
        ]

        result = ensemble.aggregate_votes(votes)

        assert result.final_decision is True
        assert result.consensus_confidence > 0.9

    def test_aggregate_votes_all_fail(self) -> None:
        """Test aggregating votes when all models fail."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ModelVote,
            ValidationEnsemble,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig()
        ensemble = ValidationEnsemble(model_router=router, config=config)

        votes = [
            ModelVote(model_id="gpt-4o", passed=False, confidence=0.90, reasoning="Fail", issues_found=["Issue 1"]),
            ModelVote(model_id="claude-3-5-sonnet-20241022", passed=False, confidence=0.88, reasoning="Fail", issues_found=["Issue 2"]),
        ]

        result = ensemble.aggregate_votes(votes)

        assert result.final_decision is False

    def test_aggregate_votes_split_decision(self) -> None:
        """Test aggregating votes with split decision."""
        from daw_agents.agents.validator.ensemble import (
            ConsensusStatus,
            EnsembleConfig,
            ModelVote,
            ValidationEnsemble,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig()
        ensemble = ValidationEnsemble(model_router=router, config=config)

        votes = [
            ModelVote(model_id="gpt-4o", passed=True, confidence=0.75, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="claude-3-5-sonnet-20241022", passed=False, confidence=0.80, reasoning="Fail", issues_found=["Issue"]),
        ]

        result = ensemble.aggregate_votes(votes)

        assert result.consensus_status == ConsensusStatus.SPLIT


class TestDetermineConsensus:
    """Test the determine_consensus method with different voting strategies."""

    @pytest.fixture
    def ensemble_with_majority(self) -> Any:
        """Create ensemble with majority voting."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ValidationEnsemble,
            VotingStrategy,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig(voting_strategy=VotingStrategy.MAJORITY)
        return ValidationEnsemble(model_router=router, config=config)

    @pytest.fixture
    def ensemble_with_unanimous(self) -> Any:
        """Create ensemble with unanimous voting."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ValidationEnsemble,
            VotingStrategy,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig(voting_strategy=VotingStrategy.UNANIMOUS)
        return ValidationEnsemble(model_router=router, config=config)

    def test_majority_voting_pass(self, ensemble_with_majority: Any) -> None:
        """Test majority voting passes when >50% pass."""
        from daw_agents.agents.validator.ensemble import ModelVote

        votes = [
            ModelVote(model_id="m1", passed=True, confidence=0.9, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="m2", passed=True, confidence=0.8, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="m3", passed=False, confidence=0.7, reasoning="Fail", issues_found=["Issue"]),
        ]

        result = ensemble_with_majority.determine_consensus(votes)
        assert result is True  # 2/3 passed

    def test_majority_voting_fail(self, ensemble_with_majority: Any) -> None:
        """Test majority voting fails when <50% pass."""
        from daw_agents.agents.validator.ensemble import ModelVote

        votes = [
            ModelVote(model_id="m1", passed=True, confidence=0.9, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="m2", passed=False, confidence=0.8, reasoning="Fail", issues_found=["A"]),
            ModelVote(model_id="m3", passed=False, confidence=0.7, reasoning="Fail", issues_found=["B"]),
        ]

        result = ensemble_with_majority.determine_consensus(votes)
        assert result is False  # 1/3 passed

    def test_unanimous_voting_pass(self, ensemble_with_unanimous: Any) -> None:
        """Test unanimous voting passes when all pass."""
        from daw_agents.agents.validator.ensemble import ModelVote

        votes = [
            ModelVote(model_id="m1", passed=True, confidence=0.9, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="m2", passed=True, confidence=0.85, reasoning="Pass", issues_found=[]),
        ]

        result = ensemble_with_unanimous.determine_consensus(votes)
        assert result is True

    def test_unanimous_voting_fail(self, ensemble_with_unanimous: Any) -> None:
        """Test unanimous voting fails when any model fails."""
        from daw_agents.agents.validator.ensemble import ModelVote

        votes = [
            ModelVote(model_id="m1", passed=True, confidence=0.9, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="m2", passed=False, confidence=0.85, reasoning="Fail", issues_found=["Issue"]),
        ]

        result = ensemble_with_unanimous.determine_consensus(votes)
        assert result is False

    def test_weighted_voting_with_weights(self) -> None:
        """Test weighted voting considers model weights."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ModelVote,
            ValidationEnsemble,
            VotingStrategy,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        # Claude has higher weight (1.5) than GPT-4o (1.0)
        config = EnsembleConfig(
            models=["gpt-4o", "claude-3-5-sonnet-20241022"],
            voting_strategy=VotingStrategy.WEIGHTED,
            model_weights={
                "gpt-4o": 1.0,
                "claude-3-5-sonnet-20241022": 1.5,
            },
        )
        ensemble = ValidationEnsemble(model_router=router, config=config)

        # GPT-4o passes (weight 1.0), Claude fails (weight 1.5)
        votes = [
            ModelVote(model_id="gpt-4o", passed=True, confidence=0.9, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="claude-3-5-sonnet-20241022", passed=False, confidence=0.85, reasoning="Fail", issues_found=["Issue"]),
        ]

        result = ensemble.determine_consensus(votes)
        # Claude's vote (1.5) > GPT-4o's vote (1.0), so fail
        assert result is False


class TestThresholdConfiguration:
    """Test configurable threshold behavior."""

    def test_custom_threshold(self) -> None:
        """Test ensemble with custom pass threshold."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ModelVote,
            ValidationEnsemble,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        # Require 75% threshold instead of 50%
        config = EnsembleConfig(threshold=0.75)
        ensemble = ValidationEnsemble(model_router=router, config=config)

        # 2/3 = 67% pass - should fail with 75% threshold
        votes = [
            ModelVote(model_id="m1", passed=True, confidence=0.9, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="m2", passed=True, confidence=0.85, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="m3", passed=False, confidence=0.8, reasoning="Fail", issues_found=["Issue"]),
        ]

        result = ensemble.aggregate_votes(votes)
        assert result.final_decision is False  # 67% < 75%

    def test_low_threshold(self) -> None:
        """Test ensemble with low threshold (33%)."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ModelVote,
            ValidationEnsemble,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig(threshold=0.33)
        ensemble = ValidationEnsemble(model_router=router, config=config)

        # 1/3 = 33% pass - should pass with 33% threshold
        votes = [
            ModelVote(model_id="m1", passed=True, confidence=0.9, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="m2", passed=False, confidence=0.85, reasoning="Fail", issues_found=["A"]),
            ModelVote(model_id="m3", passed=False, confidence=0.8, reasoning="Fail", issues_found=["B"]),
        ]

        result = ensemble.aggregate_votes(votes)
        assert result.final_decision is True  # 33% >= 33%


class TestDisagreementHandling:
    """Test model disagreement handling."""

    def test_disagreement_requires_human_review(self) -> None:
        """Test that split decisions flag for human review."""
        from daw_agents.agents.validator.ensemble import (
            ConsensusStatus,
            EnsembleConfig,
            ModelVote,
            ValidationEnsemble,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig()
        ensemble = ValidationEnsemble(model_router=router, config=config)

        votes = [
            ModelVote(model_id="gpt-4o", passed=True, confidence=0.7, reasoning="Pass", issues_found=[]),
            ModelVote(model_id="claude-3-5-sonnet-20241022", passed=False, confidence=0.75, reasoning="Fail", issues_found=["Concern"]),
        ]

        result = ensemble.aggregate_votes(votes)

        if result.consensus_status == ConsensusStatus.SPLIT:
            assert result.requires_human_review is True

    def test_low_confidence_triggers_review(self) -> None:
        """Test that low confidence scores trigger review."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ModelVote,
            ValidationEnsemble,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig(min_confidence=0.8)
        ensemble = ValidationEnsemble(model_router=router, config=config)

        # Both pass but with low confidence
        votes = [
            ModelVote(model_id="m1", passed=True, confidence=0.6, reasoning="Maybe pass", issues_found=[]),
            ModelVote(model_id="m2", passed=True, confidence=0.65, reasoning="Maybe pass", issues_found=[]),
        ]

        result = ensemble.aggregate_votes(votes)

        # Low confidence should flag for review even if consensus pass
        if result.consensus_confidence < 0.8:
            assert result.requires_human_review is True


class TestModelCombinations:
    """Test different model combinations for ensemble."""

    @pytest.mark.asyncio
    async def test_claude_and_gpt_combination(self) -> None:
        """Test ensemble with Claude and GPT-4o combination."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ValidationEnsemble,
        )

        router = MagicMock()
        router.route = AsyncMock(return_value="Code validated successfully.")

        config = EnsembleConfig(
            models=["gpt-4o", "claude-3-5-sonnet-20241022"]
        )
        ensemble = ValidationEnsemble(model_router=router, config=config)

        result = await ensemble.validate_with_ensemble(
            code="def add(a, b): return a + b",
            tests="test code",
            policies=[],
        )

        assert result is not None
        assert len(result.votes) == 2

    @pytest.mark.asyncio
    async def test_three_model_combination(self) -> None:
        """Test ensemble with three models."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ValidationEnsemble,
        )

        router = MagicMock()
        router.route = AsyncMock(return_value="Validation result.")

        config = EnsembleConfig(
            models=["gpt-4o", "claude-3-5-sonnet-20241022", "gemini-pro"]
        )
        ensemble = ValidationEnsemble(model_router=router, config=config)

        result = await ensemble.validate_with_ensemble(
            code="code",
            tests="tests",
            policies=[],
        )

        assert len(result.votes) == 3


class TestEnsembleIntegration:
    """Integration tests for ValidationEnsemble."""

    def test_ensemble_integrates_with_validator_agent(self) -> None:
        """Test that ensemble can be used by ValidatorAgent."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            ValidationEnsemble,
        )
        from daw_agents.models.router import ModelRouter

        # ValidatorAgent should be able to use ValidationEnsemble
        router = ModelRouter()
        config = EnsembleConfig()
        ensemble = ValidationEnsemble(model_router=router, config=config)

        assert ensemble is not None
        assert hasattr(ensemble, "validate_with_ensemble")
        assert hasattr(ensemble, "aggregate_votes")
        assert hasattr(ensemble, "determine_consensus")

    def test_ensemble_config_serialization(self) -> None:
        """Test that EnsembleConfig can be serialized/deserialized."""
        from daw_agents.agents.validator.ensemble import (
            EnsembleConfig,
            VotingStrategy,
        )

        config = EnsembleConfig(
            models=["gpt-4o", "claude-3-5-sonnet-20241022"],
            voting_strategy=VotingStrategy.WEIGHTED,
            threshold=0.75,
        )

        # Should be serializable to dict
        config_dict = config.model_dump()
        assert "models" in config_dict
        assert "voting_strategy" in config_dict

        # Should be deserializable from dict
        restored = EnsembleConfig.model_validate(config_dict)
        assert restored.models == config.models


class TestEnsembleExports:
    """Test module exports and public API."""

    def test_public_api_exports(self) -> None:
        """Test that public API is properly exported."""
        from daw_agents.agents.validator.ensemble import (
            ConsensusStatus,
            EnsembleConfig,
            EnsembleResult,
            ModelVote,
            ValidationEnsemble,
            ValidationType,
            VotingStrategy,
        )

        assert ValidationEnsemble is not None
        assert EnsembleConfig is not None
        assert EnsembleResult is not None
        assert ModelVote is not None
        assert VotingStrategy is not None
        assert ValidationType is not None
        assert ConsensusStatus is not None
