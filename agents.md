# Agent Specifications

This document defines the specific "Persona," "Model," "Tools," and "Workflow" for each agent in the **Deterministic Agentic Workbench**.

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
*   **Sandboxing**: ALL code execution happens in E2B. No local execution.

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
