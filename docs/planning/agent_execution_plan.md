# Agent-Parallelism Execution Plan

**Version**: 1.1
**Created**: 2025-12-30
**Updated**: 2025-12-31
**Purpose**: Define dependency-aware parallel agent execution strategy for DAW implementation

---

## Executive Summary

This plan optimizes task execution using **multi-agent parallelism** where the bottleneck is **dependency chains**, not human availability.

| Metric | Human Teams (3 streams) | Agent Parallelism |
|--------|------------------------|-------------------|
| Elapsed Time | ~35 hours | ~8-12 hours |
| Bottleneck | Human availability | Dependency chains |
| Parallelism | 3 concurrent | Up to 8 concurrent |
| Context Switching | High overhead | Zero overhead |

---

## Dependency Graph Analysis

### Critical Path (Sequential - Cannot Parallelize)
```
CORE-001 (30min)
    ↓
CORE-002 (1hr)
    ↓
MODEL-001 (4hr) ←── This is the key enabler
    ↓
PLANNER-001 (6hr)
    ↓
EXECUTOR-001 (6hr)
    ↓
VALIDATOR-001 (8hr)
    ↓
ORCHESTRATOR-001 (8hr)

Critical Path Total: ~33.5 hours (irreducible minimum)
```

### Parallelization Opportunities

```
Phase 0 (After CORE-001 completes):
├── INFRA-001 ─────┐
├── INFRA-002 ─────┼── All 3 in parallel (2hr max)
└── PROMPT-GOV-001 ┘

Phase 1 (After CORE-002 completes):
├── FRONTEND-001 ──┐
├── AUTH-001 ──────┼── All 4 in parallel (3hr max)
├── DB-001 ────────┤
└── CORE-003 ──────┘

Phase 2 (After AUTH-002 completes):
├── MCP-SEC-001 ───┐
├── MCP-SEC-002 ───┼── Security tasks (4hr max)
├── MCP-SEC-003 ───┤
└── MCP-SEC-004 ───┘

Phase 3 (After CORE-002 completes):
├── CORE-004 ──────┐
├── CORE-005 ──────┼── Core infra (3hr max)
├── CORE-006 ──────┤
└── OPS-001 ───────┘
```

---

## Agent Execution Waves

### Wave 1: Foundation (Hour 0-1.5)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | CORE-001 | 30min | None | 1 |
| A2 | INFRA-001 | 2hr | CORE-001 | 2 |
| A3 | INFRA-002 | 1hr | CORE-001 | 2 |
| A4 | PROMPT-GOV-001 | 1hr | CORE-001 | 2 |

**Max Concurrent Agents**: 3

### Wave 2: Core Backend (Hour 1.5-5)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | CORE-002 | 1hr | CORE-001 | 1 |
| A2 | FRONTEND-001 | 30min | CORE-001 | 2 |
| A3 | AUTH-001 | 1hr | CORE-001 | 2 |
| A4 | DB-001 | 2hr | CORE-002 | 3 |
| A5 | CORE-003 | 3hr | CORE-002 | 3 |
| A6 | MODEL-001 | 4hr | CORE-002 | 3 |

**Max Concurrent Agents**: 5

### Wave 3: Security & Auth (Hour 5-9)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | AUTH-002 | 2hr | CORE-002, AUTH-001 | 1 |
| A2 | MCP-SEC-001 | 4hr | CORE-003, AUTH-002 | 2 |
| A3 | MCP-SEC-002 | 3hr | MCP-SEC-001 | 3 |
| A4 | MCP-SEC-003 | 3hr | MCP-SEC-001 | 3 |
| A5 | MCP-SEC-004 | 3hr | MCP-SEC-001 | 3 |
| A6 | PROMPT-GOV-002 | 4hr | PROMPT-GOV-001, CORE-002 | 2 |

**Max Concurrent Agents**: 4

### Wave 4: Core Agents + Evolution Foundation (Hour 5-11)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | CORE-004 | 3hr | CORE-002 | 1 |
| A2 | CORE-005 | 2hr | CORE-002 | 1 |
| A3 | CORE-006 | 3hr | CORE-002, DB-001 | 1 |
| A4 | OPS-001 | 2hr | CORE-002 | 1 |
| A5 | **EVOLVE-001** | 3hr | CORE-006, DB-001 | 2 |

**Max Concurrent Agents**: 5

> **New**: EVOLVE-001 (Experience Logger) runs after CORE-006 completes, establishing the self-learning data foundation (FR-07.1).

### Wave 5: Planner (Hour 9-15)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | PLANNER-001 | 6hr | CORE-002, DB-001, CORE-003, MODEL-001 | 1 |
| A2 | PLANNER-002 | 3hr | PLANNER-001 | 2 |
| A3 | COMPLEXITY-001 | 4hr | PLANNER-001, CORE-003 | 2 |
| A4 | TASK-DECOMP-001 | 4hr | PLANNER-001, COMPLEXITY-001 | 3 |
| A5 | PRD-OUTPUT-001 | 3hr | PLANNER-001 | 2 |

**Max Concurrent Agents**: 4

### Wave 6: Executor (Hour 15-21)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | EXECUTOR-001 | 6hr | CORE-005, CORE-004, CORE-003, MODEL-001 | 1 |
| A2 | OPS-002 | 4hr | EXECUTOR-001, DB-001, CORE-003 | 2 |
| A3 | RULES-001 | 3hr | EXECUTOR-001 | 2 |

**Max Concurrent Agents**: 2

### Wave 7: Validator (Hour 21-29)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | VALIDATOR-001 | 8hr | CORE-002, MODEL-001, CORE-003 | 1 |
| A2 | VALIDATOR-002 | 4hr | VALIDATOR-001 | 2 |
| A3 | POLICY-001 | 6hr | VALIDATOR-001 | 2 |
| A4 | POLICY-002 | 4hr | DB-001, POLICY-001 | 3 |

**Max Concurrent Agents**: 3

### Wave 8: Frontend & UAT (Hour 21-33)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | API-001 | 4hr | CORE-002, AUTH-002 | 1 |
| A2 | STREAMING-001 | 4hr | CORE-002, FRONTEND-001 | 1 |
| A3 | FRONTEND-AUTH-001 | 3hr | FRONTEND-001, AUTH-001 | 1 |
| A4 | FRONTEND-002 | 4hr | FRONTEND-001, STREAMING-001 | 2 |
| A5 | FRONTEND-003 | 4hr | FRONTEND-001, STREAMING-001 | 2 |
| A6 | INFRA-003 | 3hr | INFRA-002 | 1 |

**Max Concurrent Agents**: 6

### Wave 9: Eval & Operations + Reflection (Hour 29-37)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | EVAL-001 | 3hr | PLANNER-001, EXECUTOR-001 | 1 |
| A2 | EVAL-002 | 6hr | EVAL-001, VALIDATOR-001 | 2 |
| A3 | EVAL-003 | 3hr | EVAL-002 | 3 |
| A4 | UAT-001 | 6hr | VALIDATOR-001, FRONTEND-002, CORE-003 | 2 |
| A5 | UAT-002 | 3hr | UAT-001 | 3 |
| A6 | UAT-003 | 3hr | UAT-001 | 3 |
| A7 | DRIFT-001 | 4hr | OPS-001, EXECUTOR-001 | 2 |
| A8 | DRIFT-002 | 3hr | DRIFT-001 | 3 |
| A9 | **EVOLVE-002** | 2hr | DRIFT-001, EVOLVE-001 | 3 |

**Max Concurrent Agents**: 7

> **New**: EVOLVE-002 (Reflection Hook) runs after DRIFT-001 completes, enabling proactive learning after task completion (FR-07.2).

### Wave 10: Orchestrator (Hour 33-41)
| Agent ID | Task | Duration | Dependencies | Parallel Slots |
|----------|------|----------|--------------|----------------|
| A1 | ORCHESTRATOR-001 | 8hr | MODEL-001, PLANNER-001, EXECUTOR-001, VALIDATOR-001 | 1 |

**Max Concurrent Agents**: 1 (critical path task)

### Wave 11: Architecture Conformance Refactoring [Epic 12] (Hour 41-49)

> **Purpose**: Restructure codebase to align with documented architecture in `docs/planning/architecture/sections/02_project_structure.md`

| Agent ID | Task | Duration | Dependencies | Parallel Slots | Story Ref |
|----------|------|----------|--------------|----------------|-----------|
| A1 | REFACTOR-001 | 1hr | None | 1 | 12.1 |
| A2 | REFACTOR-002 | 3hr | REFACTOR-001 | 2 | 12.2 |
| A3 | REFACTOR-003 | 4hr | REFACTOR-001 | 2 | 12.3 |
| A4 | REFACTOR-005 | 2hr | REFACTOR-001 | 2 | 12.5 |
| A5 | REFACTOR-006 | 2hr | REFACTOR-001 | 2 | 12.6 |
| A6 | REFACTOR-004 | 2hr | REFACTOR-003 | 3 | 12.4 |
| A7 | REFACTOR-007 | 2hr | ALL above | 4 | 12.7 |

**Max Concurrent Agents**: 4
**Wave Duration**: ~8 hours (with parallelization)

#### Wave 11 Execution Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WAVE 11: ARCHITECTURE REFACTORING                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Hour 41: REFACTOR-001 (Create apps/ structure)                             │
│               │                                                              │
│               ▼                                                              │
│  Hour 42: ┌─ REFACTOR-002 (Frontend → apps/web/) ─────────────┐             │
│           ├─ REFACTOR-003 (Extract server → apps/server/) ────┼─ Parallel   │
│           ├─ REFACTOR-005 (Create daw-mcp/) ──────────────────┤             │
│           └─ REFACTOR-006 (Rename daw-shared → daw-protocol) ─┘             │
│               │                                                              │
│               ▼                                                              │
│  Hour 46: REFACTOR-004 (Clean daw-agents - after REFACTOR-003)              │
│               │                                                              │
│               ▼                                                              │
│  Hour 47: REFACTOR-007 (E2E Validation - BLOCKING)                          │
│               │                                                              │
│               ▼                                                              │
│  Hour 49: ✓ COMPLETE - Codebase aligned with architecture                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### REFACTOR Task Details

**REFACTOR-001: Create apps/ Directory Structure**
```
Input:  docs/planning/architecture/sections/02_project_structure.md
Output: apps/web/, apps/server/ directories created
        pnpm-workspace.yaml updated with 'apps/*'
        turbo.json updated (if exists)
Verify: pnpm install succeeds, directories exist
```

**REFACTOR-002: Migrate Frontend to apps/web/**
```
Input:  packages/daw-frontend/*
Output: apps/web/* (all files moved)
        package.json name updated to '@daw/web'
        All imports updated
Verify: pnpm dev runs, pnpm typecheck passes (0 errors)
        pnpm build succeeds
```

**REFACTOR-003: Extract FastAPI Server to apps/server/**
```
Input:  packages/daw-agents/src/daw_agents/{api,workers,auth,main.py}
Output: apps/server/* with pyproject.toml
        Server imports daw-agents as dependency
        uvicorn entry point configured
Verify: uvicorn main:app starts successfully
        All API endpoints respond (curl -f http://localhost:8000/health)
```

**REFACTOR-004: Clean daw-agents Package**
```
Input:  packages/daw-agents/src/daw_agents/*
Output: Keep ONLY: agents/, schemas/, prompts/, evolution/, core utilities
        Remove: api/, workers/, auth/, main.py (moved to apps/server)
        Updated __init__.py exports
Verify: Package importable as library
        pytest tests/agents/ passes
```

**REFACTOR-005: Create daw-mcp Package**
```
Input:  packages/daw-agents/src/daw_agents/mcp/* (if exists)
Output: packages/daw-mcp/ with pyproject.toml
        Subdirs: git-mcp/, graph-memory/
        MCP servers register with protocol
Verify: poetry install succeeds
        MCP servers start and respond
```

**REFACTOR-006: Rename daw-shared to daw-protocol**
```
Input:  packages/daw-shared/*
Output: packages/daw-protocol/* (renamed)
        All imports updated across codebase
        package.json/pyproject.toml name updated
Verify: pnpm install succeeds
        Full test suite passes (no import errors)
```

**REFACTOR-007: Comprehensive E2E Validation (BLOCKING)**
```
Input:  Entire codebase after refactoring
Verify:
  □ All unit tests pass (pytest, jest)
  □ All integration tests pass
  □ docker-compose build succeeds
  □ docker-compose up - all services healthy
  □ Frontend connects to backend
  □ Backend connects to Neo4j/Redis
  □ Smoke tests: auth, chat, agent trace
  □ No TypeScript errors (strict mode)
  □ No linting errors (ruff, eslint)

CRITICAL: This task BLOCKS merge. All checks must pass.
```

---

## Timeline Summary

```
Hour 0    ├── Wave 1: Foundation ──────────────┤
Hour 1.5  ├── Wave 2: Core Backend ────────────┤
Hour 5    ├── Wave 3: Security ─────┤ Wave 4: Core Agents ──┤
Hour 9    ├── Wave 5: Planner ─────────────────┤
Hour 15   ├── Wave 6: Executor ────────────────┤
Hour 21   ├── Wave 7: Validator ──┤ Wave 8: Frontend ──────┤
Hour 29   ├── Wave 9: Eval & Operations ───────┤
Hour 33   ├── Wave 10: Orchestrator ───────────┤
Hour 41   └── COMPLETE ────────────────────────┘
```

**Total Elapsed Time**: ~42 hours (with full parallelization)
**Critical Path Time**: ~33.5 hours (irreducible)
**Parallelization Savings**: ~25 hours vs single-threaded (~67hr)
**Self-Evolution Tasks**: 2 (EVOLVE-001, EVOLVE-002) - adds ~5 hours parallelized

---

## Agent Spawning Strategy

### For Claude Code Implementation

```python
# Spawn pattern for each wave
async def execute_wave(wave_tasks: list[Task]):
    """Execute tasks in parallel using Task tool with subagent_type."""

    # Group by dependency satisfaction
    ready_tasks = [t for t in wave_tasks if t.dependencies_met()]

    # Spawn all ready tasks in parallel (single message, multiple tool calls)
    results = await asyncio.gather(*[
        spawn_agent(
            subagent_type="general-purpose",
            prompt=build_task_prompt(task),
            description=f"Execute {task.id}"
        )
        for task in ready_tasks
    ])

    # Mark completed, check for next wave
    for task, result in zip(ready_tasks, results):
        task.mark_completed(result)
        update_progress_file()
```

### Recommended Agent Types by Task Category

| Category | Subagent Type | Model | Rationale |
|----------|---------------|-------|-----------|
| Setup (CORE-001, INFRA-*) | general-purpose | haiku | Fast, simple file operations |
| Code (MODEL-*, PLANNER-*) | general-purpose | sonnet | Complex implementation |
| Security (MCP-SEC-*) | general-purpose | sonnet | Security-critical code |
| Testing (EVAL-*, UAT-*) | test-runner | sonnet | Test execution expertise |
| Review (post-implementation) | code-reviewer | sonnet | Quality assurance |

---

## E2B Execution Environment

**All test execution and code verification happens in E2B sandboxes.**

### Configuration
```
API Key Location: .creds/e2b_api_key.txt
Environment Var:  E2B_API_KEY
Sandbox Task:     CORE-004 (E2B Sandbox Wrapper)
```

### Execution Pattern
```
┌───────────────────────────────────────────────────────────────┐
│                    E2B EXECUTION FLOW                         │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Agent writes code locally → Commits to git → Pushes          │
│                               ↓                               │
│  E2B sandbox spins up (~300ms)                                │
│                               ↓                               │
│  Sandbox clones repo from GitHub                              │
│                               ↓                               │
│  Tests/linters execute in isolation                           │
│                               ↓                               │
│  Results returned (stdout, stderr, exit code)                 │
│                               ↓                               │
│  Sandbox terminates (ephemeral)                               │
│                                                               │
│  CRITICAL: Code persists in git, NOT in sandbox               │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### Agent-E2B Integration
```python
# Agents using E2B (via CORE-004 wrapper)
AGENTS_USING_E2B = [
    "Executor Agent",    # Primary: runs tests in TDD workflow
    "Test Runner",       # Runs full test suites
    "Healer Agent",      # Debugs failures in isolated environment
]

# Agents NOT using E2B
AGENTS_NOT_USING_E2B = [
    "Planner Agent",     # No code execution
    "Validator Agent",   # Static analysis, no sandbox needed
    "Monitor Agent",     # Observes traces, no execution
]
```

### Pre-E2B Commit Requirement
```
BEFORE any test can run in E2B:
1. Code must be written to local files
2. Code must be committed: git add . && git commit
3. Code must be pushed: git push

E2B clones from GitHub - uncommitted code is invisible to E2B.
```

### E2B → VPS Neo4j Connection
```
┌─────────────────────────────────────────────────────────────────┐
│  E2B Cloud Sandbox ──────► bolt://72.60.204.156:7687 ──────► VPS│
│                            (public internet)                    │
│                                                                 │
│  Local Dev ──────────────► bolt://72.60.204.156:7687 ──────► VPS│
│                            (public internet)                    │
│                                                                 │
│  Same Neo4j instance for all environments.                      │
│  Credentials: .creds/neo4j_vps.txt                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Progress Tracking Protocol

### Primary Progress File: `tasks.json`
- Each task has `status` field: `pending` | `in_progress` | `completed` | `blocked`
- Each task has `agent_id` field when in_progress
- Each task has `completed_at` timestamp when done

### Human-Readable Progress: `PROGRESS.md`
- Updated after each task completion
- Shows wave progress, blockers, next actions
- Includes verification status

### Verification Checklist (Per Task)
1. [ ] Code compiles (TypeScript: 0 errors)
2. [ ] Tests pass (pytest/jest)
3. [ ] Lint passes (ruff/eslint)
4. [ ] Integration verified (if applicable)
5. [ ] Progress files updated

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Agent failure mid-task | Checkpoint state to Redis, resume capability |
| Dependency not actually met | Pre-execution verification step |
| Resource contention | Queue-based agent scheduling |
| Context window overflow | Summarize completed wave context |
| Flaky tests blocking | 3-retry policy before human escalation |

---

## References

- Task definitions: `docs/planning/tasks.json`
- Agent specifications: `agents.md`
- TDD workflow: `docs/planning/tdd_workflow.md`
- Progress tracking: `PROGRESS.md`

---

*Plan created: 2025-12-30*
*Estimated total time: 41 hours (parallelized) vs 65 hours (sequential)*
