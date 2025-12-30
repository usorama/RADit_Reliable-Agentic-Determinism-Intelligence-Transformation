# CLAUDE.md - Project Memory & Context

**Project**: RADit - Reliable Agentic Determinism Intelligence Transformation
**AKA**: DAW - Deterministic Agentic Workbench
**Last Updated**: 2025-12-30

---

## Quick Context

This is a **greenfield project** building an AI agent workbench that enforces:
- **Deterministic SDLC**: Every agent follows strict TDD workflow
- **Multi-Agent Orchestration**: Planner → Executor → Validator pipeline
- **MCP Integration**: Secure tool access via Model Context Protocol

---

## Critical Architecture Decisions

### 1. VALIDATOR-001 is SEPARATE from Sandbox
```
WRONG:  Validator depends on CORE-004 (Sandbox)
RIGHT:  Validator depends on CORE-002, MODEL-001, CORE-003

The Validator Agent is architecturally DISTINCT from the E2B Sandbox.
They serve different purposes and must use different models.
```

### 2. Model Router (MODEL-001) is Critical Path
```
Planning tasks    → o1 / Claude Opus (high reasoning)
Coding tasks      → Claude Sonnet / GPT-4o (balanced)
Validation tasks  → GPT-4o (different from Executor)
Fast tasks        → Claude Haiku / GPT-4o-mini (speed)
```

### 3. Redis Serves Dual Purpose
```
1. Celery message broker for background tasks
2. LangGraph checkpoint persistence for state recovery
```

---

## Progress Tracking Files

| File | Purpose | Format |
|------|---------|--------|
| `docs/planning/tasks.json` | Machine-readable task state | JSON with status field |
| `PROGRESS.md` | Human-readable progress | Markdown dashboard |

### Task Status Values
- `pending` - Not started, waiting for dependencies
- `in_progress` - Currently being worked on
- `completed` - Done and verified
- `blocked` - Has unmet dependencies or blockers

---

## TDD Workflow (Mandatory for All Tasks)

```
PHASE 0: PRE-CHECK   → Read tasks.json, verify deps met
PHASE 1: RED         → Write failing test FIRST
PHASE 2: GREEN       → Minimal implementation to pass
PHASE 3: REFACTOR    → Clean up, lint, type check
PHASE 4: VERIFY      → Full verification checklist
PHASE 5: UPDATE      → Mark progress, commit
```

**NEVER skip phases. NEVER mark complete without verification.**

---

## Agent Execution Plan

### Parallel Execution Waves (10 waves, ~41 hours total)
```
Wave 1:  Foundation        (CORE-001, INFRA-*)
Wave 2:  Core Backend      (CORE-002, FRONTEND-001, AUTH-001)
Wave 3:  Security          (AUTH-002, MCP-SEC-*)
Wave 4:  Core Agents       (CORE-004/005/006, OPS-001)
Wave 5:  Planner           (PLANNER-*, COMPLEXITY-001)
Wave 6:  Executor          (EXECUTOR-001, OPS-002, RULES-001)
Wave 7:  Validator         (VALIDATOR-*, POLICY-*)
Wave 8:  Frontend & UAT    (FRONTEND-*, STREAMING-001)
Wave 9:  Eval & Ops        (EVAL-*, UAT-*, DRIFT-*)
Wave 10: Orchestrator      (ORCHESTRATOR-001 - final integration)
```

### Critical Path (Cannot Parallelize)
```
CORE-001 → CORE-002 → MODEL-001 → PLANNER-001 → EXECUTOR-001 → VALIDATOR-001 → ORCHESTRATOR-001
```

---

## Key Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Task Definitions | `docs/planning/tasks.json` | 50 tasks with deps, phases |
| PRD | `docs/planning/prd/` | Functional requirements FR-01 to FR-06 |
| Architecture | `docs/planning/architecture/` | Tech stack, patterns, deployment |
| Agent Specs | `agents.md` | Agent personas, tools, constraints |
| Definition of Done | `docs/planning/stories/definition_of_done.md` | 34 stories, 291 DoD items |
| TDD Workflow | `docs/planning/tdd_workflow.md` | Mandatory implementation workflow |
| Execution Plan | `docs/planning/agent_execution_plan.md` | Parallel agent scheduling |
| Analysis Report | `docs/planning/task_reprioritization_analysis.md` | Gap analysis, dependency fixes |

---

## Dependency Quick Reference

### Orphan Tasks (No Dependencies)
- CORE-001 (start here)

### Bottleneck Tasks (Many Dependents)
- CORE-002: 9 tasks depend on this
- EXECUTOR-001: 5 tasks depend on this
- VALIDATOR-001: 5 tasks depend on this

### Tasks with MCP Dependency (CORE-003)
- PLANNER-001, EXECUTOR-001, OPS-002, COMPLEXITY-001, UAT-001

---

## Verification Standards

### Per-Task Checklist
- [ ] TypeScript/Python: 0 compile errors
- [ ] Linting: 0 errors (ruff/eslint)
- [ ] Tests: All pass
- [ ] Coverage: >= 80% new code
- [ ] Integration: Deps work together
- [ ] Progress: tasks.json + PROGRESS.md updated

### Blocking Quality Gates
- Test coverage < 80% new code → BLOCKED
- Any SAST critical finding → BLOCKED
- TypeScript strict mode violations → BLOCKED
- 0 linting errors required

---

## Common Patterns

### LangGraph State Machine Pattern
```python
from langgraph.graph import StateGraph

graph = StateGraph(AgentState)
graph.add_node("step_1", step_1_fn)
graph.add_node("step_2", step_2_fn)
graph.add_edge("step_1", "step_2")
graph.set_entry_point("step_1")
```

### MCP Tool Call Pattern
```python
from daw_agents.mcp.client import MCPClient

client = MCPClient(server_url="...")
result = await client.call_tool("git_status", params={})
```

### TDD Guard Pattern
```python
# Enforced by CORE-005
if not test_file_exists(target_file):
    raise TDDViolation("Write test first!")
if not test_fails(test_file):
    raise TDDViolation("Test must fail before implementation!")
```

---

## Environment Setup

### Required Services (docker-compose)
- Neo4j (memory/knowledge graph)
- Redis (Celery broker + LangGraph checkpoints)
- MCP Servers (git, filesystem, postgres)

### Required API Keys
- Clerk (authentication)
- OpenAI / Anthropic (LLM providers)
- Helicone (observability)
- E2B (sandbox execution)

---

## Session Continuity

When starting a new session:
1. Read `PROGRESS.md` for current state
2. Read `docs/planning/tasks.json` for task details
3. Check which tasks are `in_progress` or ready to start
4. Continue from where previous session left off

When ending a session:
1. Update `tasks.json` with current status
2. Update `PROGRESS.md` with what was done
3. Note any blockers or issues
4. Commit progress

---

*This file is the canonical memory for Claude Code sessions on this project.*
