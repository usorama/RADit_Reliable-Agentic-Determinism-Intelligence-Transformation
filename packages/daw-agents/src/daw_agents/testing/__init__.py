"""Testing module for prompt regression testing harness.

This module provides the PromptHarness for testing prompts against golden
input/output pairs with semantic similarity scoring and JSON schema validation.

Part of PROMPT-GOV-002: Implement Prompt Regression Testing Harness.
"""

from daw_agents.testing.prompt_harness import (
    GoldenPair,
    PromptDriftReport,
    PromptHarness,
    PromptTestConfig,
    PromptTestResult,
    PromptTestSuiteResult,
    SchemaValidationResult,
    SimilarityScore,
    calculate_structural_similarity,
    extract_json_from_text,
    normalize_json,
)

__all__ = [
    "GoldenPair",
    "PromptDriftReport",
    "PromptHarness",
    "PromptTestConfig",
    "PromptTestResult",
    "PromptTestSuiteResult",
    "SchemaValidationResult",
    "SimilarityScore",
    "calculate_structural_similarity",
    "extract_json_from_text",
    "normalize_json",
]
