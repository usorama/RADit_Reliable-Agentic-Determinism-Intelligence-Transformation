# Eval Protocol: Golden Benchmark Suite

**Version**: 1.0.0
**Last Updated**: 2025-12-30
**Purpose**: Systematic evaluation of DAW agent performance against golden benchmarks

---

## Overview

This directory contains the evaluation infrastructure for the Deterministic Agentic Workbench (DAW). The eval protocol provides systematic measurement of agent quality, enabling regression detection and objective release criteria.

The system addresses the research paper requirement (Line 251): "Eval Protocol scores agent performance against benchmarks."

---

## Directory Structure

```
eval/
├── README.md                 # This file
├── benchmarks/               # Golden benchmark PRDs and expected outputs
│   ├── index.json            # Benchmark registry with metadata and scoring rubrics
│   ├── calculator/           # Low complexity benchmark
│   │   ├── prd.md            # Input PRD
│   │   ├── expected/         # Expected outputs
│   │   │   ├── tasks.json    # Expected task decomposition
│   │   │   ├── complexity_analysis.json
│   │   │   └── tests/        # Expected test patterns
│   │   ├── rubric.yaml       # Scoring criteria
│   │   └── metadata.json     # Benchmark metadata
│   ├── todo_app/             # Low-Medium complexity benchmark
│   └── ecommerce_checkout/   # Medium complexity benchmark
├── goldens/                  # Golden reference outputs for similarity scoring
└── results/                  # Evaluation run results
    ├── reports/              # Generated reports (weekly summaries)
    └── trends/               # Metrics time-series for dashboards
```

---

## Running Benchmarks

### Quick Start

```bash
# Run all benchmarks with default settings
python -m eval.harness --benchmarks all

# Run specific benchmark
python -m eval.harness --benchmarks calculator

# Run with multiple trials (for pass^8 measurement)
python -m eval.harness --benchmarks all --trials 8

# Output results to specific file
python -m eval.harness --benchmarks all --output eval/results/$(date +%Y%m%d).json
```

### CI/CD Integration

Nightly evaluation runs are configured in `.github/workflows/eval-nightly.yml`:

```yaml
# Runs at 2 AM UTC daily
python -m eval.harness \
  --benchmarks all \
  --trials 8 \
  --output eval_results/$(date +%Y%m%d).json
```

---

## Metrics and Thresholds

### Release-Blocking Metrics

| Metric | Definition | Threshold | Gate Level |
|--------|------------|-----------|------------|
| pass@1 | First attempt success rate | >= 85% | **Release blocking** |
| Task Completion Rate | % of tasks reaching "complete" state | >= 90% | **Release blocking** |

### Warning-Level Metrics

| Metric | Definition | Threshold | Gate Level |
|--------|------------|-----------|------------|
| pass^8 | Success rate over 8 independent trials | >= 60% | Warning |
| Retry Rate | Average retries before success | < 2.0 | Warning |

### Advisory Metrics

| Metric | Definition | Threshold | Gate Level |
|--------|------------|-----------|------------|
| Cost per Task | Average token cost per atomic task | < $0.50 | Advisory |
| Time to Complete | Wall-clock time per task | < 5 min avg | Advisory |

---

## Scoring Methodology

### 1. Task Decomposition Score (30%)

Measures how well the Planner agent decomposes PRDs into tasks:

- **Task count accuracy**: Within +/- 20% of expected count
- **Dependency correctness**: All critical dependencies identified
- **Priority alignment**: P0/P1/P2 distribution matches expected
- **Type distribution**: Correct mix of setup/code/test tasks

### 2. Code Quality Score (40%)

Measures the Executor agent's code generation quality:

- **Test coverage**: >= 80% on generated code
- **Linting pass**: 0 errors (ruff/eslint)
- **Type safety**: 0 TypeScript/mypy errors
- **Pattern adherence**: Follows expected architectural patterns

### 3. Semantic Similarity Score (30%)

Measures output similarity to golden references:

- **Textual outputs**: Embedding-based similarity >= 0.85
- **Code outputs**: AST comparison with normalized formatting
- **Structured outputs**: JSON field-by-field weighted comparison

---

## Benchmark Definitions

### Calculator (Low Complexity)

**Purpose**: Validate basic TDD workflow and arithmetic operations

**Key Patterns Tested**:
- Basic arithmetic operations (+, -, *, /)
- Input validation
- Error handling
- TDD red-green-refactor cycle

**Expected Task Count**: 6-8 tasks
**Expected Time**: < 10 minutes total

### ToDo App (Low-Medium Complexity)

**Purpose**: Validate CRUD operations and state management

**Key Patterns Tested**:
- Create, Read, Update, Delete operations
- State management patterns
- Data persistence
- Basic UI patterns

**Expected Task Count**: 12-15 tasks
**Expected Time**: < 20 minutes total

### E-commerce Checkout (Medium Complexity)

**Purpose**: Validate multi-step workflow and validation

**Key Patterns Tested**:
- Multi-step form workflow
- Cart management
- Payment validation
- Inventory integration
- Error recovery

**Expected Task Count**: 18-25 tasks
**Expected Time**: < 35 minutes total

---

## Regression Detection

### Baseline Management

- `eval/results/baseline.json` contains the current release baseline
- All nightly runs are compared against baseline
- Regression > 5% triggers alert and requires explicit approval

### Alert Thresholds

```yaml
regression_threshold: 0.05  # 5% degradation triggers alert
notification_channels:
  - "slack:#agent-eval"
  - "linear:agent-team"
```

### Regression Response

1. **< 5% regression**: Log warning, continue
2. **5-10% regression**: Alert team, require approval for release
3. **> 10% regression**: Block release, require investigation

---

## Adding New Benchmarks

### 1. Create Benchmark Directory

```bash
mkdir -p eval/benchmarks/{benchmark_name}/expected/tests
```

### 2. Create PRD Document

Write `eval/benchmarks/{benchmark_name}/prd.md` with:
- Clear feature description
- User stories
- Acceptance criteria
- Technical requirements

### 3. Create Expected Outputs

- `expected/tasks.json`: Expected task decomposition
- `expected/complexity_analysis.json`: Expected complexity scores
- `expected/tests/`: Example test patterns

### 4. Create Scoring Rubric

Write `eval/benchmarks/{benchmark_name}/rubric.yaml`:

```yaml
version: "1.0"
scoring:
  task_decomposition:
    weight: 0.30
    criteria:
      - name: task_count
        weight: 0.25
        tolerance: 0.20
      - name: dependency_accuracy
        weight: 0.40
      - name: priority_alignment
        weight: 0.35

  code_quality:
    weight: 0.40
    criteria:
      - name: test_coverage
        weight: 0.30
        threshold: 0.80
      - name: lint_pass
        weight: 0.25
        threshold: 1.00
      - name: type_safety
        weight: 0.25
        threshold: 1.00
      - name: pattern_adherence
        weight: 0.20

  similarity:
    weight: 0.30
    criteria:
      - name: semantic_similarity
        weight: 0.50
        threshold: 0.85
      - name: structural_similarity
        weight: 0.50
        threshold: 0.80
```

### 5. Register in Index

Add entry to `eval/benchmarks/index.json`

---

## Results Format

### Single Run Output

```json
{
  "run_id": "eval-20241230-001",
  "timestamp": "2025-12-30T02:00:00Z",
  "benchmarks": {
    "calculator": {
      "pass_at_1": true,
      "task_completion_rate": 1.0,
      "retry_rate": 0.5,
      "cost_usd": 0.23,
      "duration_seconds": 180,
      "scores": {
        "task_decomposition": 0.92,
        "code_quality": 0.88,
        "similarity": 0.91
      },
      "total_score": 0.90
    }
  },
  "aggregate": {
    "pass_at_1_rate": 0.87,
    "avg_completion_rate": 0.92,
    "total_cost_usd": 1.45,
    "total_duration_seconds": 720
  }
}
```

### Regression Report

```json
{
  "comparison": {
    "baseline_version": "1.2.0",
    "current_version": "1.3.0-beta",
    "metrics": {
      "pass_at_1_change": -0.02,
      "completion_rate_change": 0.01,
      "cost_change": -0.05
    },
    "status": "PASS",
    "requires_approval": false
  }
}
```

---

## References

- Test Strategy: `docs/planning/test_strategy/test_strategy.md`
- Definition of Done: `docs/planning/stories/definition_of_done.md`
- EVAL-002: Eval Harness Implementation
- EVAL-003: Agent Similarity Scoring

---

*Established as part of EVAL-001: Eval Protocol Golden Benchmark Suite*
