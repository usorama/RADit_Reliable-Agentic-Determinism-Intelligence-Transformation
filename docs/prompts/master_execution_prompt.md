# Master Execution Prompt for DAW Implementation

**Version**: 1.0
**Created**: 2025-12-30
**Purpose**: Reusable prompt template for spawning implementation agents

---

## Usage

Copy and customize this prompt when spawning agents for task execution. Replace `{TASK_ID}` and other placeholders with actual values.

---

## Master Prompt Template

```markdown
# Task Execution: {TASK_ID}

## Context Loading (MANDATORY - Read These First)

Before starting ANY work, read these files in order:

1. **Progress Check**: Read `PROGRESS.md` for current project state
2. **Task Details**: Read `docs/planning/tasks.json` and find task `{TASK_ID}`
3. **Memory Context**: Read `CLAUDE.md` for project conventions and patterns
4. **TDD Workflow**: Read `docs/planning/tdd_workflow.md` for mandatory workflow
5. **DoD Reference**: Read `docs/planning/stories/definition_of_done.md` for acceptance criteria

## Task Information

- **Task ID**: {TASK_ID}
- **Description**: {DESCRIPTION}
- **Priority**: {PRIORITY}
- **Phase**: {PHASE}
- **Dependencies**: {DEPENDENCIES}
- **Estimated Hours**: {EST_HOURS}

## Pre-Execution Checklist

Before writing any code:
- [ ] Verify all dependencies in tasks.json show status: "completed"
- [ ] If dependencies not met, STOP and report blocker
- [ ] Update tasks.json: set {TASK_ID} status to "in_progress"
- [ ] Update PROGRESS.md: add task to "Active Tasks" section

## Mandatory TDD Workflow

Execute these phases IN ORDER - no skipping:

### Phase 1: RED (Failing Test First)
1. Create test file: `tests/test_{module}.py` or `tests/{module}.test.ts`
2. Write test that defines expected behavior
3. Run test: `pytest tests/test_{module}.py` or `npm test`
4. VERIFY: Test MUST FAIL (red)
5. If test passes, your test is wrong - fix it

### Phase 2: GREEN (Minimal Implementation)
1. Write MINIMAL code to pass the failing test
2. No extra features, no premature optimization
3. Run test again
4. VERIFY: Test MUST PASS (green)

### Phase 3: REFACTOR (Clean Up)
1. Improve code quality without changing behavior
2. Run linters:
   - Python: `ruff check --fix .`
   - TypeScript: `npm run lint`
3. Run type checker:
   - Python: `mypy {module}`
   - TypeScript: `npm run typecheck`
4. Run ALL tests: `pytest` or `npm test`
5. VERIFY: 0 errors in all checks

### Phase 4: VERIFICATION
Run complete verification:
```bash
# Python
pytest --cov={module} --cov-report=term-missing
ruff check .
mypy {module}

# TypeScript
npm test -- --coverage
npm run lint
npm run typecheck
```

MUST achieve:
- [ ] All tests pass
- [ ] Coverage >= 80% for new code
- [ ] 0 linting errors
- [ ] 0 type errors

## Post-Execution (MANDATORY)

After ALL verification passes:

1. **Update tasks.json**:
   ```json
   {
     "id": "{TASK_ID}",
     "status": "completed",
     "completed_at": "{ISO_TIMESTAMP}"
   }
   ```

2. **Update PROGRESS.md**:
   - Move task from "Active Tasks" to "Recently Completed"
   - Update "Overall Status" metrics
   - Add to "Session Log"
   - Check "Next Up" for newly unblocked tasks

3. **Commit with task reference**:
   ```bash
   git add .
   git commit -m "feat({module}): {description} [{TASK_ID}]"
   ```

## Parallel Execution Context

If part of a wave with other agents:
- **Current Wave**: {WAVE_NUMBER}
- **Wave Tasks**: {WAVE_TASKS}
- **Can Run in Parallel With**: {PARALLEL_TASKS}
- **Blocks**: {DOWNSTREAM_TASKS}

Reference: `docs/planning/agent_execution_plan.md`

## Critical Architecture Reminders

From `CLAUDE.md`:
- VALIDATOR-001 is SEPARATE from Sandbox (CORE-004)
- MODEL-001 Router selects models by task type
- Redis serves dual purpose (Celery + LangGraph checkpoints)
- All agents using tools need CORE-003 (MCP Client) dependency

## E2B Sandbox Execution

**All code execution happens in E2B sandboxes, NOT locally.**

```
┌─────────────────────────────────────────────────────────────────┐
│ E2B EXECUTION WORKFLOW                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. Write code to local files (packages/*)                     │
│   2. Commit changes: git add . && git commit                    │
│   3. Push to GitHub: git push                                   │
│   4. E2B sandbox clones repo and runs tests                     │
│   5. Results returned (stdout, exit code)                       │
│   6. Sandbox terminates automatically                           │
│                                                                 │
│   API Key: .creds/e2b_api_key.txt (loaded as E2B_API_KEY)       │
│   Wrapper: CORE-004 (E2B Sandbox Wrapper)                       │
│                                                                 │
│   CRITICAL: Never run tests locally. Always use E2B.            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### E2B Test Commands
```bash
# Tests run in E2B sandbox (via CORE-004 wrapper)
# Python
sandbox.run("pytest tests/test_{module}.py --cov={module}")

# TypeScript
sandbox.run("npm test -- --coverage")
```

## Error Handling

If you encounter issues:

1. **Dependency Not Met**:
   - Report blocker
   - Do NOT proceed
   - Update PROGRESS.md with blocked status

2. **Test Keeps Failing (>3 attempts)**:
   - Stop and escalate
   - Document what was tried
   - Create issue in PROGRESS.md blockers section

3. **External Service Unavailable**:
   - Note the issue
   - Skip integration tests if unit tests pass
   - Document for follow-up

## Output Requirements

Provide these in your completion report:

```markdown
## Task Completion: {TASK_ID}

### Summary
- Description: {what was implemented}
- Files Created: {list}
- Files Modified: {list}

### Verification Results
- Tests: {PASS/FAIL} ({count} tests)
- Coverage: {percentage}%
- Lint: {PASS/FAIL}
- Types: {PASS/FAIL}

### Progress Updates
- tasks.json: Updated to "completed"
- PROGRESS.md: Updated with completion
- Commit: {commit hash}

### Unblocked Tasks
- {list of tasks now ready to start}

### Notes/Issues
- {any issues encountered or tech debt noted}
```

## Success Criteria

Task is ONLY complete when:
- [ ] All tests pass
- [ ] Coverage >= 80%
- [ ] 0 lint errors
- [ ] 0 type errors
- [ ] tasks.json updated
- [ ] PROGRESS.md updated
- [ ] Changes committed

DO NOT mark complete if ANY criterion is not met.
```

---

## Quick Reference: Spawning Multiple Agents

For parallel execution, spawn multiple agents in a single message:

```python
# Example: Wave 2 - Core Backend (parallel tasks)
tasks_to_spawn = [
    ("FRONTEND-001", "Initialize Next.js Frontend"),
    ("AUTH-001", "Initialize Clerk Authentication"),
    ("DB-001", "Implement Neo4j Connector"),
]

# Spawn all in parallel (single message with multiple Task tool calls)
for task_id, description in tasks_to_spawn:
    spawn_agent(
        subagent_type="general-purpose",
        prompt=master_prompt.format(
            TASK_ID=task_id,
            DESCRIPTION=description,
            ...
        ),
        description=f"Execute {task_id}"
    )
```

---

## Agent Type Selection Guide

| Task Category | Subagent Type | Model Hint |
|---------------|---------------|------------|
| Setup tasks (CORE-001, INFRA-*) | general-purpose | haiku |
| Code implementation | general-purpose | sonnet |
| Security tasks (MCP-SEC-*) | general-purpose | sonnet |
| Test execution | test-runner | sonnet |
| Code review (post-impl) | code-reviewer | sonnet |
| Complex planning | Plan | opus |

---

## Customization Points

When using this template, customize:

1. `{TASK_ID}` - The specific task being executed
2. `{DESCRIPTION}` - Task description from tasks.json
3. `{PRIORITY}` - P0/P1/P2
4. `{PHASE}` - 0-8
5. `{DEPENDENCIES}` - List of dependency task IDs
6. `{EST_HOURS}` - Estimated hours
7. `{WAVE_NUMBER}` - Execution wave (1-10)
8. `{WAVE_TASKS}` - Other tasks in same wave
9. `{PARALLEL_TASKS}` - Tasks that can run simultaneously
10. `{DOWNSTREAM_TASKS}` - Tasks this will unblock

---

## File References Summary

| File | Purpose | When to Read |
|------|---------|--------------|
| `CLAUDE.md` | Project memory & patterns | Start of every session |
| `PROGRESS.md` | Human-readable status | Before and after every task |
| `docs/planning/tasks.json` | Task details & status | Before starting any task |
| `docs/planning/tdd_workflow.md` | Mandatory workflow | During implementation |
| `docs/planning/agent_execution_plan.md` | Parallel scheduling | When planning multi-agent work |
| `docs/planning/stories/definition_of_done.md` | Acceptance criteria | During verification |
| `docs/planning/scrum/sprint_plan.md` | Phase organization | For context on current phase |
| `agents.md` | Agent specifications | For agent-specific constraints |

---

*Master prompt template created: 2025-12-30*
*Use this for consistent, high-quality task execution*
