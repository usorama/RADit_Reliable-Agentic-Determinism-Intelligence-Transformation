# Test Strategy: Deterministic Agentic Workbench

**Goal**: Ensure the *Workbench itself* is reliable, so it can build reliable software for others.

## 1. Testing Pyramid

### Level 1: Unit Tests (Python/Jest)
-   **Scope**: Individual Functions (e.g., `parse_prd_to_json`, `validate_mcp_schema`).
-   **Tool**: `pytest` (Backend), `jest` (Frontend).
-   **Coverage Target**: 80%.

### Level 2: Integration Tests (Agent Workflows)
-   **Scope**: Testing the LangGraph state transitions.
-   **Method**: "Mocked LLM" testing. We record the LLM responses (using **VCR.py** or **pytest-recording**) and replay them to test the *graph logic* without spending tokens.
-   **Key Scenarios**:
-   **Key Scenarios**:
    -   Happy Path: Plan -> Code -> Test -> Pass.
    -   Failure Path: Plan -> Code -> Test -> Fail -> Retry -> Fail -> Human Help.

### Level 3: System Tests (E2B Sandboxing)
-   **Scope**: verifying the sandbox integration.
-   **Method**: Live calls to E2B (tagged `slow`).
-   **Scenario**: Spin up sandbox, install `numpy`, run script, verify output.

### Level 4: UAT (The "Dogfood" Test)
-   **Scope**: End-to-End User Journey.
-   **Method**: Use the Workbench *to build a feature for the Workbench*.
-   **Scenario**: Ask the "Planner Agent" to design a new "Settings Page" for the dashboard, and see if the "Executor" can build it.

## 2. CI/CD Pipeline
-   **Pre-Commit**: Linting (Ruff/Birome), Type Check (Pyright).
-   **Pull Request**: Unit Tests + Mocked Integration Tests.
-   **Nightly**: Full System Tests (Real E2B + Real OpenAI calls).

## 3. Test Data Strategy
-   **Synthetic PRDs**: A set of "Golden PRDs" (e.g., "Build a Calculator", "Build a ToDo App") used to benchmark agent performance.
-   **Eval Set**: A repo of "Bad Code" patterns to test the "Reviewer Agent's" ability to catch bugs.

---

## 4. Eval Protocol (Agent Performance Benchmarking)

The Eval Protocol provides systematic measurement of agent quality, enabling regression detection and objective release criteria. This directly addresses the research paper requirement (Line 251): "Eval Protocol scores agent performance against benchmarks."

### 4.1 Golden PRD Benchmarks

Maintain a suite of 10-20 representative PRDs covering diverse complexity levels:

| Benchmark | Complexity | Key Patterns Tested |
|-----------|------------|---------------------|
| Calculator | Low | Basic arithmetic, TDD enforcement |
| ToDo App | Low-Medium | CRUD operations, state management |
| E-commerce Checkout | Medium | Multi-step workflow, validation |
| REST API Server | Medium | Endpoint routing, auth middleware |
| Real-time Chat | Medium-High | WebSocket handling, message queuing |
| Data Pipeline | High | ETL patterns, error recovery |
| ML Feature Store | High | Schema evolution, versioning |

**Golden Reference Structure**:
```
eval/benchmarks/{benchmark_name}/
├── prd.md                    # Input PRD
├── expected/
│   ├── tasks.json            # Expected task decomposition
│   ├── complexity_analysis.json  # Expected complexity scores
│   ├── tests/                # Expected test files
│   └── src/                  # Expected implementation
├── rubric.yaml               # Scoring criteria
└── metadata.json             # Benchmark metadata
```

**Acceptance Criteria**: Agent must achieve >= 85% similarity score on golden outputs.

### 4.2 Performance Metrics

| Metric | Definition | Threshold | Gate Level |
|--------|------------|-----------|------------|
| pass@1 | First attempt success rate | >= 85% | **Release blocking** |
| Task Completion Rate | % of tasks reaching "complete" state | >= 90% | **Release blocking** |
| pass^8 | Success rate over 8 independent trials | >= 60% | Warning |
| Cost per Task | Average token cost per atomic task | < $0.50 | Advisory |
| Time to Complete | Wall-clock time per task | < 5 min avg | Advisory |
| Retry Rate | Average retries before success | < 2.0 | Warning |

**Metric Collection**:
- All metrics collected per-task and aggregated per-benchmark
- Historical trends tracked for regression detection
- Percentile breakdowns (p50, p90, p99) for latency metrics

### 4.3 Eval Harness Implementation

Use **DeepEval** or **Braintrust** as the evaluation framework:

```python
# Example eval harness configuration
eval_config:
  framework: "deepeval"  # or "braintrust"

  benchmarks:
    - name: "calculator"
      prd_path: "eval/benchmarks/calculator/prd.md"
      golden_path: "eval/benchmarks/calculator/expected/"
      trials: 8  # For pass^8 measurement

  metrics:
    - name: "pass@1"
      type: "binary_success"
      threshold: 0.85

    - name: "similarity_score"
      type: "semantic_similarity"
      model: "text-embedding-3-small"
      threshold: 0.85

    - name: "code_correctness"
      type: "ast_comparison"
      tolerance: 0.1

  alerts:
    regression_threshold: 0.05  # 5% degradation triggers alert
    notification_channels:
      - "slack:#agent-eval"
      - "pagerduty:critical"
```

### 4.4 Similarity Scoring

**Textual Outputs** (PRD, documentation):
- Use embedding-based semantic similarity (OpenAI text-embedding-3-small or equivalent)
- Cosine similarity threshold: >= 0.85

**Code Outputs**:
- AST-based structural comparison
- Normalize formatting, variable names
- Compare control flow graphs
- Test coverage comparison

**Structured Outputs** (tasks.json, complexity_analysis.json):
- JSON schema validation (100% required)
- Field-by-field comparison with weighted scoring
- Dependency graph isomorphism checking

### 4.5 CI Integration

**Nightly Eval Runs**:
```yaml
# .github/workflows/eval-nightly.yml
name: Nightly Agent Evaluation
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Eval Suite
        run: |
          python -m eval.harness \
            --benchmarks all \
            --trials 8 \
            --output eval_results/$(date +%Y%m%d).json

      - name: Check Regression
        run: |
          python -m eval.regression_check \
            --current eval_results/$(date +%Y%m%d).json \
            --baseline eval_results/baseline.json \
            --threshold 0.05

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: eval_results/
```

**Release Gating**:
- pass@1 < 85% → Block release
- Task Completion Rate < 90% → Block release
- Regression > 5% from baseline → Require explicit approval

### 4.6 Results Storage and Reporting

**Storage Structure**:
```
eval_results/
├── baseline.json              # Current release baseline
├── 20241230.json              # Daily run results
├── 20241229.json
├── reports/
│   ├── weekly_summary.md      # Auto-generated weekly report
│   └── regression_alerts.md   # Historical regression incidents
└── trends/
    └── metrics_history.csv    # Time-series for dashboards
```

**Weekly Report Contents**:
- Aggregate pass@1 and completion rates
- Benchmark-by-benchmark breakdown
- Cost analysis (total tokens, $ spent)
- Top failure patterns (for agent improvement)
- Comparison to previous week and baseline

---

## 5. Prompt Regression Testing

All prompts are treated as code artifacts with dedicated regression testing.

### 5.1 Golden Input/Output Pairs

```
tests/prompts/goldens/
├── planner/
│   ├── prd_generator/
│   │   ├── input_01.yaml     # Input: user request
│   │   ├── output_01.yaml    # Expected: structured PRD
│   │   └── rubric_01.yaml    # Scoring criteria
│   └── task_decomposer/
│       └── ...
├── executor/
│   └── code_generator/
│       └── ...
└── validator/
    └── test_reviewer/
        └── ...
```

### 5.2 Prompt Regression Test Execution

```python
# tests/prompts/test_prompt_regression.py
import pytest
from eval.prompt_harness import PromptHarness

@pytest.mark.parametrize("prompt_name,golden_set", [
    ("prd_generator_v1.0", "goldens/planner/prd_generator/"),
    ("code_generator_v1.0", "goldens/executor/code_generator/"),
])
def test_prompt_regression(prompt_name, golden_set):
    harness = PromptHarness(prompt_name)
    results = harness.evaluate_against_goldens(golden_set)

    assert results.similarity_score >= 0.85, \
        f"Prompt {prompt_name} regressed: {results.similarity_score}"
    assert results.schema_valid, \
        f"Output schema validation failed: {results.schema_errors}"
```

### 5.3 Prompt Drift Metrics

Track over time:
- Output length variance (sudden changes indicate drift)
- Token efficiency (tokens per successful output)
- Error rate by prompt version
- Semantic similarity to baseline outputs

---

## 6. UAT Test Strategy (Playwright-Based)

Automated User Acceptance Testing using Playwright MCP for browser automation.

### 6.1 UAT Agent Architecture

The UAT Agent operates on **accessibility snapshots** (not screenshots) for:
- Deterministic element identification
- Faster execution (no image processing)
- Better accessibility compliance testing

### 6.2 Persona-Based Test Suites

| Persona | Device | Network | Interaction Style |
|---------|--------|---------|-------------------|
| Power User | Desktop | Fast | Keyboard shortcuts, bulk actions |
| First-Time User | Mobile | 3G | Help-seeking, slow navigation |
| Accessibility User | Desktop | Fast | Screen reader, keyboard-only |

### 6.3 Business Journey Validation

PRD acceptance criteria translated to Gherkin scenarios:

```gherkin
# uat/scenarios/planner_workflow.feature
Feature: Planner Agent PRD Generation

  @P0 @blocking
  Scenario: Generate PRD from user request
    Given I am logged in as a Product Manager
    When I describe "Build a todo app with due dates"
    And I complete the Taskmaster interview
    Then I should see a generated PRD
    And the PRD should contain all required sections
    And the complexity analysis should be available

  @P1 @warning
  Scenario: Roundtable critique session
    Given I have a draft PRD
    When I initiate the Concept Roundtable
    Then I should see feedback from CTO persona
    And I should see feedback from Security persona
    And I can accept or reject each suggestion
```

### 6.4 Visual Regression Thresholds

| UI Component | Max Allowed Diff | Baseline Update Policy |
|--------------|------------------|------------------------|
| Critical (login, checkout) | 0.05% | Manual approval required |
| Standard (dashboards) | 0.1% | Auto-update on feature merge |
| Cosmetic (marketing pages) | 0.5% | Auto-update weekly |

### 6.5 UAT Release Gating

| Journey Priority | Pass Requirement | Gate Level |
|------------------|------------------|------------|
| P0 (Core flows) | 100% pass | **Block production deploy** |
| P1 (Important flows) | >= 90% pass | Warning, require approval |
| P2 (Nice-to-have) | >= 80% pass | Advisory only |
