# 02. Project Structure

```
deterministic-agent-workbench/
├── .gemini/                  # Local LLM/Agent artifacts
├── apps/
│   ├── web/                  # Next.js Frontend (Dashboard) (Auth: Clerk)
│   └── server/               # FastAPI Backend (LangGraph Host) (Queues: Celery)
├── packages/
│   ├── daw-agents/           # LangGraph Agent Definitions
│   │   ├── planner/          # SDD Agents (PM, Architect)
│   │   ├── developer/        # TDD Agents (Coder, Reviewer)
│   │   └── ops/              # Ops Agents (Monitor, Healer)
│   ├── daw-mcp/              # Custom MCP Servers
│   │   ├── git-mcp/          # Git Operations
│   │   └── graph-memory/     # Neo4j Access
│   └── daw-protocol/         # Shared Types/Schemas (Pydantic/Zod)
├── docker/                   # Deployment containers
├── docs/                     # Documentation (Architecture, PRDs)
└── scripts/                  # Setup and Maintenance
```

## Epic to Architecture Mapping

| Epic | Architecture Component |
| :--- | :--- |
| **1. Spec Generation** | **Module: `daw-agents/planner`**. Uses "Taskmaster" pattern. Persists approved Specs to Neo4j Graph. |
| **2. Build Loop** | **Module: `daw-agents/developer`**. Implements the *Red-Green-Refactor* graph. Connects to **E2B** for running `pytest`. |
| **3. Safety** | **Module: `daw-mcp`**. "Guardrails" implemented as Middleware in the MCP Server. Checks `.mcpignore` rules. |
| **4. Ops/Healing** | **Module: `daw-agents/ops`**. "Monitor Agent" subscribes to execution traces (Helicone); triggers "Healer" on failure. |
