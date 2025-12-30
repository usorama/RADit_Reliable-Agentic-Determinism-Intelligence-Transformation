# TDD Implementation Workflow with Progress Tracking

**Version**: 1.0
**Created**: 2025-12-30
**Purpose**: Define the mandatory TDD workflow for all task implementation including progress verification

---

## Overview

This workflow enforces Test-Driven Development (TDD) with integrated progress tracking. Every task MUST follow this workflow - no exceptions.

---

## The TDD + Progress Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 0: PRE-IMPLEMENTATION CHECK                                  │
│  ├── Read tasks.json for task details                              │
│  ├── Read PROGRESS.md for current state                            │
│  ├── Verify dependencies are completed                             │
│  └── Mark task status: "in_progress" in tasks.json                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: RED (Write Failing Test First)                           │
│  ├── Create test file in tests/ directory                          │
│  ├── Write test that defines expected behavior                     │
│  ├── Run test → MUST FAIL (red)                                    │
│  ├── If test passes → You wrote test wrong, fix it                 │
│  └── Update PROGRESS.md: "Task X: Red phase complete"              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2: GREEN (Minimal Implementation)                           │
│  ├── Write MINIMAL code to pass the test                           │
│  ├── No extra features, no premature optimization                  │
│  ├── Run test → MUST PASS (green)                                  │
│  ├── If test fails → Fix implementation, not test                  │
│  └── Update PROGRESS.md: "Task X: Green phase complete"            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 3: REFACTOR (Clean Up)                                      │
│  ├── Improve code quality without changing behavior                │
│  ├── Run linters (ruff/eslint) → MUST PASS                        │
│  ├── Run type checker (mypy/tsc) → 0 errors                       │
│  ├── Run all tests → ALL MUST PASS                                 │
│  └── Update PROGRESS.md: "Task X: Refactor phase complete"         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 4: VERIFICATION (Thorough Check)                            │
│  ├── Run full test suite for affected modules                      │
│  ├── Check test coverage (must meet threshold)                     │
│  ├── Run integration tests if applicable                           │
│  ├── Verify task acceptance criteria from DoD                      │
│  └── Document any known issues or tech debt                        │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 5: PROGRESS UPDATE (Mark Complete)                          │
│  ├── Update tasks.json: status = "completed"                       │
│  ├── Update tasks.json: completed_at = timestamp                   │
│  ├── Update PROGRESS.md with completion details                    │
│  ├── Check if this unblocks other tasks                           │
│  └── Commit changes with task ID in message                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Mandatory Verification Checklist

### Per-Task Verification (MUST pass ALL before marking complete)

```markdown
## Task Verification: [TASK-ID]

### Code Quality
- [ ] TypeScript/Python compiles with 0 errors
- [ ] Linting passes (ruff/eslint) with 0 errors
- [ ] No `any` types used (TypeScript strict mode)
- [ ] No TODO/FIXME comments left unaddressed

### Testing
- [ ] Test file exists in tests/ directory
- [ ] Test covers primary functionality
- [ ] Test covers edge cases
- [ ] All tests pass
- [ ] Coverage >= 80% for new code

### Integration
- [ ] Dependencies properly imported
- [ ] No circular dependencies introduced
- [ ] API contracts maintained
- [ ] Environment variables documented

### Documentation
- [ ] Code has appropriate docstrings/comments
- [ ] README updated if public API changed
- [ ] PROGRESS.md updated

### Progress Files
- [ ] tasks.json status updated to "completed"
- [ ] tasks.json completed_at timestamp added
- [ ] PROGRESS.md updated with task completion
- [ ] Dependent tasks checked for unblocking
```

---

## Progress File Specifications

### tasks.json (Primary - Machine Readable)

Each task should have these execution fields:

```json
{
  "id": "TASK-001",
  "status": "pending",          // pending | in_progress | completed | blocked
  "started_at": null,           // ISO timestamp when started
  "completed_at": null,         // ISO timestamp when completed
  "agent_id": null,             // Agent that worked on it
  "wave": 1,                    // Execution wave (1-10)
  "estimated_hours": 2,         // Estimated hours
  "actual_hours": null,         // Actual hours taken
  "blockers": [],               // List of blocking issues
  "verification": {
    "tests_pass": false,
    "lint_pass": false,
    "coverage_met": false,
    "integration_verified": false
  }
}
```

### PROGRESS.md (Secondary - Human Readable)

Updated after each task state change:

```markdown
# Project Progress

**Last Updated**: 2025-12-30T15:30:00Z
**Current Wave**: 2
**Overall Progress**: 12/50 tasks (24%)

## Active Tasks
| Task ID | Description | Status | Started | Assignee |
|---------|-------------|--------|---------|----------|
| CORE-003 | MCP Client | in_progress | 14:00 | Agent-A1 |

## Completed Today
- [x] CORE-001: Initialize Monorepo (30min)
- [x] CORE-002: Python Backend (1hr)

## Blocked
| Task ID | Blocked By | Issue |
|---------|------------|-------|
| None | - | - |

## Next Up (Ready to Start)
- [ ] DB-001: Neo4j Connector (deps met)
- [ ] MODEL-001: Model Router (deps met)
```

---

## Pre-Task Dependency Check

Before starting any task, run this check:

```python
def check_dependencies(task_id: str, tasks: list[dict]) -> tuple[bool, list[str]]:
    """
    Check if all dependencies for a task are completed.
    Returns (can_start, missing_deps)
    """
    task = next(t for t in tasks if t["id"] == task_id)
    dependencies = task.get("dependencies", [])

    missing = []
    for dep_id in dependencies:
        dep_task = next(t for t in tasks if t["id"] == dep_id)
        if dep_task.get("status") != "completed":
            missing.append(dep_id)

    return len(missing) == 0, missing
```

---

## Enforcement Rules

### BLOCKING Rules (Cannot Proceed)

1. **No implementation without failing test**
   - `src/` writes blocked until `tests/` file exists and fails

2. **No completion without all tests passing**
   - Status cannot be "completed" if any test fails

3. **No completion without lint passing**
   - 0 linting errors required

4. **No starting blocked tasks**
   - Dependencies must all be "completed"

### WARNING Rules (Log but Allow)

1. **Coverage below threshold**
   - Log warning if < 80% coverage on new code

2. **Long-running task**
   - Alert if task exceeds 2x estimated_hours

3. **Many retries**
   - Escalate if > 3 test failures on same code

---

## Example Workflow Execution

```bash
# PHASE 0: Pre-Implementation Check
read tasks.json  # Get task CORE-003 details
read PROGRESS.md  # Current state
# Verify CORE-002 is completed (dependency)
# Update tasks.json: CORE-003 status = "in_progress"

# PHASE 1: RED
write tests/test_mcp_client.py  # Create test file
run pytest tests/test_mcp_client.py  # Should FAIL
# Update PROGRESS.md: "CORE-003: Red phase complete"

# PHASE 2: GREEN
write packages/daw-agents/src/mcp/client.py  # Minimal impl
run pytest tests/test_mcp_client.py  # Should PASS
# Update PROGRESS.md: "CORE-003: Green phase complete"

# PHASE 3: REFACTOR
run ruff check --fix .
run mypy packages/daw-agents/
run pytest  # All tests
# Update PROGRESS.md: "CORE-003: Refactor phase complete"

# PHASE 4: VERIFICATION
run pytest --cov=packages/daw-agents/src/mcp  # Coverage check
# Verify against DoD checklist

# PHASE 5: PROGRESS UPDATE
# Update tasks.json: CORE-003 status = "completed"
# Update tasks.json: CORE-003 completed_at = now()
# Update PROGRESS.md: Task completed
# Check what tasks are now unblocked
git commit -m "feat(mcp): Implement MCP client interface [CORE-003]"
```

---

## Integration with Claude Code

When spawning agents for task execution:

```python
prompt = f"""
Execute task {task_id} following the TDD workflow:

1. PRE-CHECK: Read tasks.json, verify dependencies completed
2. RED: Create failing test first
3. GREEN: Write minimal implementation
4. REFACTOR: Clean up, run linters
5. VERIFY: Run full verification checklist
6. UPDATE: Mark progress in tasks.json and PROGRESS.md

Task Details:
{task_details}

DoD Checklist:
{dod_checklist}

CRITICAL: Do not mark complete until ALL verification passes.
"""
```

---

## References

- Task definitions: `docs/planning/tasks.json`
- Progress tracking: `PROGRESS.md`
- DoD per story: `docs/planning/stories/definition_of_done.md`
- Agent execution plan: `docs/planning/agent_execution_plan.md`

---

*Workflow created: 2025-12-30*
