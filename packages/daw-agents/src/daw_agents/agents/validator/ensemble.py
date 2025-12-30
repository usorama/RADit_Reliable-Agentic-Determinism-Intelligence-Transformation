"""Multi-Model Validation Ensemble for VALIDATOR-002.

This module implements ensemble validation using 2+ LLM models for critical validations.
The ensemble ensures higher validation quality through consensus mechanism.

Key Features:
- Uses multiple LLM models for validation (e.g., GPT-4o + Claude)
- Voting/consensus mechanism for pass/fail decisions
- Configurable voting strategies: majority, unanimous, weighted
- Configurable thresholds for pass/fail decisions
- Support for security-critical and production deployment validation

Based on FR-04.2: Multi-Model Validation Ensemble
- Use 2+ models for critical validations
- Voting/consensus mechanism for pass/fail decisions
- Configurable: which validations require ensemble
- Security-critical and production deployments require ensemble

Public API:
- ValidationEnsemble: Main class for ensemble validation
- EnsembleConfig: Configuration for ensemble behavior
- EnsembleResult: Aggregated result with consensus status
- ModelVote: Individual model validation result
- VotingStrategy: Enum for voting strategies
- ValidationType: Enum for validation context types
- ConsensusStatus: Enum for consensus outcomes
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class VotingStrategy(str, Enum):
    """Voting strategies for ensemble consensus.

    - MAJORITY: More than 50% must agree (default)
    - UNANIMOUS: All models must agree
    - WEIGHTED: Models have different weights in voting
    """

    MAJORITY = "majority"
    UNANIMOUS = "unanimous"
    WEIGHTED = "weighted"


class ValidationType(str, Enum):
    """Types of validation that may require ensemble.

    - STANDARD: Normal validation, ensemble optional
    - SECURITY: Security-critical validation, ensemble recommended
    - PRODUCTION: Production deployment, ensemble required
    """

    STANDARD = "standard"
    SECURITY = "security"
    PRODUCTION = "production"


class ConsensusStatus(str, Enum):
    """Status of consensus among models.

    - CONSENSUS_PASS: All/majority models agree code passes
    - CONSENSUS_FAIL: All/majority models agree code fails
    - SPLIT: Models disagree (requires human review)
    """

    CONSENSUS_PASS = "consensus_pass"
    CONSENSUS_FAIL = "consensus_fail"
    SPLIT = "split"


class ModelVote(BaseModel):
    """Individual model's validation result.

    Represents a single model's vote in the ensemble validation.
    Includes the model's decision, confidence, and reasoning.

    Attributes:
        model_id: Identifier of the model that produced this vote
        passed: Whether the model believes the code passes validation
        confidence: Confidence score (0.0 to 1.0)
        reasoning: Explanation for the decision
        issues_found: List of issues identified by the model
        validation_time_ms: Time taken for validation in milliseconds
        tokens_used: Number of tokens used for the validation
    """

    model_id: str
    passed: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    issues_found: list[str] = Field(default_factory=list)
    validation_time_ms: int = 0
    tokens_used: int = 0


class EnsembleConfig(BaseModel):
    """Configuration for validation ensemble.

    Controls how the ensemble operates including which models to use,
    voting strategy, and thresholds.

    Attributes:
        models: List of model identifiers to use (minimum 2)
        voting_strategy: How to aggregate votes (majority, unanimous, weighted)
        threshold: Pass threshold for majority voting (default 0.5)
        model_weights: Weights for weighted voting (optional)
        require_ensemble_for: Which validation types require ensemble
        min_confidence: Minimum confidence to avoid human review
    """

    models: list[str] = Field(
        default_factory=lambda: ["gpt-4o", "claude-3-5-sonnet-20241022"]
    )
    voting_strategy: VotingStrategy = VotingStrategy.MAJORITY
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    model_weights: dict[str, float] = Field(default_factory=dict)
    require_ensemble_for: list[ValidationType] = Field(
        default_factory=lambda: [ValidationType.SECURITY, ValidationType.PRODUCTION]
    )
    min_confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator("models")
    @classmethod
    def validate_minimum_models(cls, v: list[str]) -> list[str]:
        """Ensure at least 2 models are specified for ensemble."""
        if len(v) < 2:
            raise ValueError("Ensemble requires at least 2 models")
        return v


class EnsembleResult(BaseModel):
    """Aggregated result from ensemble validation.

    Contains the consensus decision, all individual votes, and metadata
    about the validation process.

    Attributes:
        consensus_status: Overall consensus status
        final_decision: Final pass/fail decision
        votes: List of individual model votes
        consensus_confidence: Aggregated confidence score
        reasoning: Explanation of the consensus decision
        aggregated_issues: Deduplicated list of all issues found
        requires_human_review: Whether human review is needed
    """

    consensus_status: ConsensusStatus
    final_decision: bool
    votes: list[ModelVote]
    consensus_confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    aggregated_issues: list[str] = Field(default_factory=list)
    requires_human_review: bool = False


class ValidationEnsemble:
    """Multi-model validation ensemble for critical validations.

    The ValidationEnsemble runs validation through multiple LLM models
    and aggregates their results using a configurable consensus mechanism.
    This ensures higher quality validation by leveraging diverse model
    perspectives and avoiding single-model blind spots.

    Example:
        ```python
        from daw_agents.agents.validator.ensemble import (
            ValidationEnsemble,
            EnsembleConfig,
        )
        from daw_agents.models.router import ModelRouter

        router = ModelRouter()
        config = EnsembleConfig(
            models=["gpt-4o", "claude-3-5-sonnet-20241022"],
            voting_strategy=VotingStrategy.MAJORITY,
        )
        ensemble = ValidationEnsemble(model_router=router, config=config)

        result = await ensemble.validate_with_ensemble(
            code="def hello(): return 'hello'",
            tests="def test_hello(): assert hello() == 'hello'",
            policies=["security", "style"],
        )

        if result.final_decision:
            print("Code passed ensemble validation!")
        else:
            print(f"Issues: {result.aggregated_issues}")
        ```

    Attributes:
        model_router: Router for LLM model selection
        config: Ensemble configuration
    """

    def __init__(
        self,
        model_router: Any,
        config: EnsembleConfig | None = None,
    ) -> None:
        """Initialize the ValidationEnsemble.

        Args:
            model_router: ModelRouter instance for LLM calls
            config: Optional ensemble configuration. If None, uses defaults.
        """
        self.model_router = model_router
        self.config = config or EnsembleConfig()

        logger.info(
            "ValidationEnsemble initialized with %d models: %s",
            len(self.config.models),
            ", ".join(self.config.models),
        )

    async def validate_with_ensemble(
        self,
        code: str,
        tests: str,
        policies: list[str],
    ) -> EnsembleResult:
        """Run validation through multiple models and aggregate results.

        Executes validation in parallel across all configured models,
        then aggregates the results using the configured voting strategy.

        Args:
            code: Source code to validate
            tests: Test code to validate against
            policies: List of policy categories to check (e.g., ["security", "style"])

        Returns:
            EnsembleResult with consensus decision and all votes
        """
        logger.info(
            "Starting ensemble validation with %d models",
            len(self.config.models),
        )

        # Run validation in parallel across all models
        validation_tasks = [
            self._validate_with_model(model_id, code, tests, policies)
            for model_id in self.config.models
        ]

        votes = await asyncio.gather(*validation_tasks)

        # Aggregate votes and determine consensus
        result = self.aggregate_votes(list(votes))

        logger.info(
            "Ensemble validation complete: %s (confidence: %.2f)",
            result.consensus_status.value,
            result.consensus_confidence,
        )

        return result

    async def _validate_with_model(
        self,
        model_id: str,
        code: str,
        tests: str,
        policies: list[str],
    ) -> ModelVote:
        """Run validation using a specific model.

        Args:
            model_id: Identifier of the model to use
            code: Source code to validate
            tests: Test code to validate against
            policies: List of policy categories to check

        Returns:
            ModelVote with the model's validation result
        """
        import time

        start_time = time.time()

        # Build validation prompt
        prompt = self._build_validation_prompt(code, tests, policies)

        try:
            # Call the model through the router
            response = await self.model_router.route(
                task_type="validation",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a code validation expert. Analyze the provided code "
                            "and tests. Respond with a JSON object containing: "
                            '"passed": boolean, "confidence": float 0-1, '
                            '"reasoning": string, "issues": list of strings'
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                metadata={"model_override": model_id},
            )

            # Parse the response
            vote = self._parse_model_response(model_id, response)

        except Exception as e:
            logger.error("Model %s validation failed: %s", model_id, str(e))
            # On error, vote to fail with low confidence
            vote = ModelVote(
                model_id=model_id,
                passed=False,
                confidence=0.0,
                reasoning=f"Validation error: {str(e)}",
                issues_found=[f"Model error: {str(e)}"],
            )

        # Record timing
        elapsed_ms = int((time.time() - start_time) * 1000)
        vote.validation_time_ms = elapsed_ms

        logger.debug(
            "Model %s vote: passed=%s, confidence=%.2f",
            model_id,
            vote.passed,
            vote.confidence,
        )

        return vote

    def _build_validation_prompt(
        self,
        code: str,
        tests: str,
        policies: list[str],
    ) -> str:
        """Build the validation prompt for LLM models.

        Args:
            code: Source code to validate
            tests: Test code to validate against
            policies: List of policy categories to check

        Returns:
            Formatted prompt string
        """
        policy_str = ", ".join(policies) if policies else "general"

        return f"""Please validate the following code against the provided tests and policies.

## Code to Validate
```python
{code}
```

## Test Code
```python
{tests}
```

## Policies to Check
{policy_str}

## Instructions
1. Analyze the code for correctness, security, and style
2. Check if the code would pass the tests
3. Identify any issues or concerns
4. Provide your assessment

Respond with a JSON object:
{{
    "passed": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Your analysis",
    "issues": ["issue1", "issue2"]
}}"""

    def _parse_model_response(self, model_id: str, response: str) -> ModelVote:
        """Parse the model's response into a ModelVote.

        Args:
            model_id: Identifier of the model
            response: Raw response from the model

        Returns:
            Parsed ModelVote
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
                return ModelVote(
                    model_id=model_id,
                    passed=bool(data.get("passed", False)),
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=str(data.get("reasoning", "No reasoning provided")),
                    issues_found=list(data.get("issues", [])),
                )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse model response: %s", str(e))

        # Fallback: analyze response text
        passed = "pass" in response.lower() and "fail" not in response.lower()
        return ModelVote(
            model_id=model_id,
            passed=passed,
            confidence=0.5,
            reasoning=response[:500],
            issues_found=[],
        )

    def aggregate_votes(self, votes: list[ModelVote]) -> EnsembleResult:
        """Aggregate individual model votes into ensemble result.

        Uses the configured voting strategy to determine consensus.

        Args:
            votes: List of individual model votes

        Returns:
            EnsembleResult with consensus decision
        """
        if not votes:
            return EnsembleResult(
                consensus_status=ConsensusStatus.CONSENSUS_FAIL,
                final_decision=False,
                votes=[],
                consensus_confidence=0.0,
                reasoning="No votes received",
                requires_human_review=True,
            )

        # Determine consensus based on voting strategy
        final_decision = self.determine_consensus(votes)

        # Calculate consensus confidence
        pass_votes = [v for v in votes if v.passed]
        fail_votes = [v for v in votes if not v.passed]

        if len(pass_votes) == len(votes):
            consensus_status = ConsensusStatus.CONSENSUS_PASS
            consensus_confidence = sum(v.confidence for v in votes) / len(votes)
        elif len(fail_votes) == len(votes):
            consensus_status = ConsensusStatus.CONSENSUS_FAIL
            consensus_confidence = sum(v.confidence for v in votes) / len(votes)
        else:
            consensus_status = ConsensusStatus.SPLIT
            consensus_confidence = 0.5  # Split decision has low confidence

        # Aggregate issues (deduplicated)
        all_issues: set[str] = set()
        for vote in votes:
            all_issues.update(vote.issues_found)

        # Determine if human review is needed
        requires_human_review = (
            consensus_status == ConsensusStatus.SPLIT
            or consensus_confidence < self.config.min_confidence
        )

        # Build reasoning
        if consensus_status == ConsensusStatus.SPLIT:
            reasoning = (
                f"Models disagree: {len(pass_votes)} passed, {len(fail_votes)} failed. "
                "Conservative decision applied."
            )
        elif final_decision:
            reasoning = f"Consensus reached: {len(pass_votes)}/{len(votes)} models passed."
        else:
            reasoning = f"Consensus reached: {len(fail_votes)}/{len(votes)} models failed."

        return EnsembleResult(
            consensus_status=consensus_status,
            final_decision=final_decision,
            votes=votes,
            consensus_confidence=consensus_confidence,
            reasoning=reasoning,
            aggregated_issues=list(all_issues),
            requires_human_review=requires_human_review,
        )

    def determine_consensus(self, votes: list[ModelVote]) -> bool:
        """Determine the final consensus decision based on voting strategy.

        Args:
            votes: List of individual model votes

        Returns:
            True if consensus is to pass, False otherwise
        """
        if not votes:
            return False

        strategy = self.config.voting_strategy

        if strategy == VotingStrategy.UNANIMOUS:
            return self._unanimous_vote(votes)
        elif strategy == VotingStrategy.WEIGHTED:
            return self._weighted_vote(votes)
        else:  # MAJORITY (default)
            return self._majority_vote(votes)

    def _majority_vote(self, votes: list[ModelVote]) -> bool:
        """Apply majority voting strategy.

        Args:
            votes: List of individual model votes

        Returns:
            True if more than threshold% pass
        """
        pass_count = sum(1 for v in votes if v.passed)
        pass_ratio = pass_count / len(votes)
        return pass_ratio >= self.config.threshold

    def _unanimous_vote(self, votes: list[ModelVote]) -> bool:
        """Apply unanimous voting strategy.

        Args:
            votes: List of individual model votes

        Returns:
            True only if ALL models pass
        """
        return all(v.passed for v in votes)

    def _weighted_vote(self, votes: list[ModelVote]) -> bool:
        """Apply weighted voting strategy.

        Uses model weights from config, defaulting to 1.0.

        Args:
            votes: List of individual model votes

        Returns:
            True if weighted pass votes exceed weighted fail votes
        """
        pass_weight = 0.0
        fail_weight = 0.0

        for vote in votes:
            weight = self.config.model_weights.get(vote.model_id, 1.0)
            if vote.passed:
                pass_weight += weight
            else:
                fail_weight += weight

        # Pass if pass weight meets threshold of total weight
        total_weight = pass_weight + fail_weight
        if total_weight == 0:
            return False
        return (pass_weight / total_weight) >= self.config.threshold


# Export all public types
__all__ = [
    "ValidationEnsemble",
    "EnsembleConfig",
    "EnsembleResult",
    "ModelVote",
    "VotingStrategy",
    "ValidationType",
    "ConsensusStatus",
]
