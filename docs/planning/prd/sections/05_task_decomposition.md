# 05. Task Decomposition Strategy

## Overview
To ensure deterministic execution, the PRD is not consumed directly by the Executor Agent. Instead, it is parsed into a linear, atomic list of operations: `tasks.json`.

## The `tasks.json` Schema
The `tasks.json` file serves as the "Instruction Tape" for the agent.

```json
[
  {
    "id": "TASK-001",
    "type": "setup",
    "description": "Initialize a new FastAPI project structure",
    "dependencies": [],
    "verification": {
      "type": "file_exists",
      "path": "backend/main.py"
    }
  },
  {
    "id": "TASK-002",
    "type": "code",
    "description": "Implement Health Check Endpoint",
    "dependencies": ["TASK-001"],
    "context_files": ["backend/main.py"],
    "verification": {
      "type": "test_pass",
      "command": "pytest tests/test_health.py"
    }
  }
]
```

## Parsing Rules
1.  **Atomicity**: Each task must be verifiable by a single command or file check.
2.  **Context Relevance**: Each task must list specific files it needs to modify, preventing the agent from reading the entire codebase.
3.  **Dependency Graph**: Tasks must explicitly state their blockers.

## Generation Workflow
1.  **Input**: `prd.md` + `system_architecture.md`.
2.  **Process**: "Senior PM" agent breaks down features into stories, then stories into tasks.
3.  **Output**: `tasks.json`.
4.  **Audit**: Human Reviewer approves `tasks.json` before any code is written.
