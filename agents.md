# Agent Specifications

This document defines the specific "Persona," "Model," "Tools," and "Workflow" for each agent in the **Deterministic Agentic Workbench**.

---

## Execution Plan Reference

For parallel agent execution strategy, see: `docs/planning/agent_execution_plan.md`

**Key Points:**
- 10 execution waves with up to 8 concurrent agents
- Critical path: ~33.5 hours (irreducible)
- Total with parallelization: ~41 hours
- TDD workflow mandatory: `docs/planning/tdd_workflow.md`

---

## Codebase Map (MANDATORY PRE-STEP)

**Location**: `docs/codebase_map.json`
**Schema**: `docs/codebase_map.schema.json`
**Updater**: `python scripts/gather_codebase_map.py`

### ALL Agents MUST Consult Before Implementation

```
╔══════════════════════════════════════════════════════════════════════════════╗
║   MANDATORY PRE-IMPLEMENTATION CHECKLIST FOR ALL AGENTS:                     ║
║                                                                              ║
║   1. READ docs/codebase_map.json                                            ║
║   2. SEARCH for existing:                                                    ║
║      - Classes with similar names or purposes                               ║
║      - Functions that might already implement needed logic                  ║
║      - Types/Enums that should be reused                                    ║
║      - Integration patterns (MCP tools, LangGraph workflows)               ║
║   3. VERIFY no duplication before creating new elements                     ║
║   4. UPDATE the map after implementation:                                   ║
║      python scripts/gather_codebase_map.py                                  ║
║                                                                              ║
║   VIOLATIONS RESULT IN TECHNICAL DEBT - ENFORCE STRICTLY                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### What to Look For (by Agent Type)

| Agent | Key Map Sections to Check |
|-------|--------------------------|
| Planner | `capabilities`, `integration_points.langgraph_workflows` |
| Executor | `packages.daw-agents.domains`, existing class patterns |
| Validator | `packages.daw-agents.domains.agents.validator`, existing types |
| Healer | `packages.daw-agents.domains.memory` (error resolution RAG) |

### Codebase Map Taxonomy

| Level | Element | Description |
|-------|---------|-------------|
| L0 | Package | Monorepo package (daw-agents, daw-frontend) |
| L1 | Domain | Logical namespace (agents, models, auth, mcp) |
| L2 | Module | Source file with classes, functions, types |
| L3 | Class/Function/Type | Code element definitions |
| L4 | Method/Property | Class members |

---

## E2B Sandbox

```
API Key:  .creds/e2b_api_key.txt (E2B_API_KEY)
Wrapper:  CORE-004
Users:    Executor, Test Runner, Healer
Pattern:  Write → Commit → Push → E2B executes → Results
```

---

## VPS Infrastructure (Hostinger)

```
Neo4j:    bolt://72.60.204.156:7687 (creds: .creds/neo4j_vps.txt)
SSH:      root@72.60.204.156 (creds: .creds/hostinger_vps.txt)
Access:   Both local dev and E2B connect over public internet
```

---

## 1. The Planner Agent ("The Taskmaster")
**Role**: Senior Product Manager & Architect
**Model**: High-Reasoning (e.g., `o1`, `claude-3-5-sonnet`)
**Responsibility**: Converts vague human intent into a rigorous `tasks.json`.

### Capabilities (Tools)
*   `interview_user`: Ask clarifying questions to scope the request.
*   `consult_knowledge_base`: Search docs/web for best practices (RAG).
*   `simulate_roundtable`: Spawn synthetic "CTO" and "UX" personas to critique the plan.
*   `write_spec`: Generate `prd.md` and `architecture.md`.
*   `decompose_tasks`: Parse specs into atomic `tasks.json`.

### Workflow Constraints
*   **No Code**: The Planner NEVER writes code. It only writes Specs and Tasks.
*   **Approval Gate**: Output must be approved by the Human User before downstream agents activate.

---

## 2. The Executor Agent ("The Developer")
**Role**: Senior Software Engineer (TDD Specialist)
**Model**: Balanced High-Speed (e.g., `gpt-4o`, `claude-3-5-sonnet`)
**Responsibility**: Executes atomic tasks from `tasks.json` using Red-Green-Refactor.

### Capabilities (Tools)
*   `read_file` / `write_file`: File system access (scoped via `.mcpignore`).
*   `run_command`: Execute shell commands (in E2B Sandbox).
*   `run_test`: Execute `pytest` or `npm test` (in E2B Sandbox).
*   `git_commit`: Commit changes to version control.

### Workflow Constraints
*   **Red Phase**: MUST create a failing test file (`tests/test_foo.py`) before modifying `src/`.
*   **Green Phase**: MUST write minimal code to pass the test.
*   **Refactor**: MUST run linters (`ruff`, `eslint`) before committing.
*   **Sandboxing**: ALL code execution happens in E2B (see E2B Sandbox section above).

---

## 3. The Monitor Agent ("The Watchdog")
**Role**: SRE / DevOps Engineer
**Model**: Fast & Cheap (e.g., `claude-3-haiku`, `gpt-4o-mini`)
**Responsibility**: Observes the `Executor`'s trace stream for anomalies.

### Capabilities (Tools)
*   `analyze_trace`: Read the current LangGraph state history.
*   `kill_process`: Terminate a stuck agent loop.
*   `log_anomaly`: Record a warning to the dashboard.

### Workflow Constraints
*   **Passive-Active**: Runs in parallel to the Executor.
*   **Drift Detection**: Triggers if Executor retries the same step > 3 times or uses > $1.00 in tokens for a minor task.

---

## 4. The Healer Agent ("The Fixer")
**Role**: Senior Debugger
**Model**: High-Reasoning (e.g., `o1`, `claude-3-5-sonnet`)
**Responsibility**: Fixes broken builds/tests when the Executor gets stuck.

### Capabilities (Tools)
*   `search_stackoverflow` (via Brave Search MCP): Find solutions to error messages.
*   `read_error_log`: Parse stack traces.
*   `patch_code`: Apply a targeted fix to the codebase.
*   `verify_fix`: Run the failing test again.

### Workflow Constraints
*   **Invoked By**: Monitor Agent or Executor (after N failures).
*   **Zero-Copy**: Experiments in a fork/branch before merging back to main.

---

## 5. The Validator Agent ("The QA Lead")
**Role**: Quality Assurance & Security Reviewer
**Model**: DIFFERENT from Executor (e.g., if Executor uses Claude, Validator uses GPT-4o)
**Responsibility**: Independent validation of code quality, security, and compliance.

### Capabilities (Tools)
*   `run_tests`: Execute test suites and interpret results
*   `security_scan`: Run SAST/SCA analysis (Snyk, SonarQube)
*   `policy_check`: Validate against organizational policies
*   `generate_report`: Produce actionable feedback

### Workflow Constraints
*   **Model Separation**: MUST use different model than Executor to prevent bias
*   **Multi-Model Validation**: Critical validations use 2+ models with consensus
*   **Retry Logic**: Fixable failures route back to Executor (max 3 retries)
*   **Escalation**: Critical/unfixable issues escalate to human reviewers

---

## 6. The Learner (Self-Evolution Foundation)
**Role**: Experience Collector & Pattern Analyzer
**Model**: Fast & Cheap (e.g., `claude-3-haiku`, `gpt-4o-mini`)
**Responsibility**: Stores task outcomes and extracts learnings for future improvement.

### Components

#### 6.1 Experience Logger (EVOLVE-001)
**Purpose**: Store structured records of task executions in Neo4j.

**Capabilities**:
*   `log_success`: Record successful task completion with metrics
*   `log_failure`: Record failed task with error details
*   `query_similar`: Find past experiences matching current task
*   `get_success_rate`: Calculate success rates by task type, model, prompt version

**Neo4j Schema**:
```cypher
(:Experience {task_type, success, prompt_version, model_used, tokens_used, cost_usd, duration_ms, retries})
  -[:USED_SKILL]->(:Skill {name, pattern, success_rate, usage_count})
  -[:PRODUCED]->(:Artifact {type, path, lines_added, test_coverage})
```

**Workflow Constraints**:
*   **Non-Blocking**: Logging happens asynchronously, < 100ms latency
*   **All Tasks**: Every task completion (success or failure) gets logged
*   **RAG Retrieval**: Similar experiences are queried before starting new tasks

#### 6.2 Reflection Hook (EVOLVE-002)
**Purpose**: Extract learnings after task completion.

**Capabilities**:
*   `reflect`: Generate insights from task outcome (async, non-blocking)
*   `store_insight`: Save learnings to Neo4j
*   `query_insights`: Retrieve relevant past insights

**Reflection Depth Modes**:
| Mode | Latency | Trigger | Output |
|------|---------|---------|--------|
| `quick` | < 100ms | Always | Metrics only (no LLM call) |
| `standard` | < 3s | Default | LLM-generated insight |
| `deep` | < 15s | Significant events | Multi-model consensus |

**Workflow Constraints**:
*   **Non-Blocking**: Main workflow continues immediately after reflection trigger
*   **Configurable**: Depth mode selected based on task significance
*   **LangGraph Integration**: Fires as callback after task completion node

### Future Evolution Capabilities (Phase 2-3)
*   **Skill Library** (EVOLVE-003): Extract reusable code patterns from successful experiences (Voyager pattern)
*   **Prompt Optimizer** (EVOLVE-005): DSPy-style automatic prompt improvement based on success metrics
*   **Constitutional Safety** (EVOLVE-006): RLAIF constraints for safe self-modification

---

## Agent Interaction Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT ORCHESTRATION FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   USER ───────► PLANNER ───────► EXECUTOR ◄───────► MONITOR                 │
│                    │                 │                   │                   │
│                    │                 ▼                   │                   │
│                    │            VALIDATOR ◄──────────────┘                   │
│                    │                 │                                       │
│                    │                 ▼                                       │
│                    │             HEALER (on failure)                         │
│                    │                 │                                       │
│                    ▼                 ▼                                       │
│              ┌─────────────────────────────────────┐                        │
│              │           LEARNER                    │                        │
│              │  ┌─────────────┐ ┌─────────────────┐│                        │
│              │  │ Experience  │ │ Reflection Hook ││                        │
│              │  │   Logger    │ │  (post-task)    ││                        │
│              │  └─────────────┘ └─────────────────┘│                        │
│              │              ↓                       │                        │
│              │         Neo4j Graph                  │                        │
│              │     (Experiences, Skills,            │                        │
│              │      Artifacts, Insights)            │                        │
│              └─────────────────────────────────────┘                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

*Document last updated: 2025-12-31*
*Self-Evolution Foundation (Epic 11) added per FR-07*
