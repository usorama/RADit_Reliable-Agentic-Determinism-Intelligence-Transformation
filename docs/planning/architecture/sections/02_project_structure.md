# 02. Project Structure

## Target Structure (Post-Epic 12 Refactoring)

```
deterministic-agent-workbench/
├── .gemini/                  # Local LLM/Agent artifacts
├── apps/
│   ├── web/                  # Next.js Frontend (Dashboard) (Auth: Clerk)
│   └── server/               # FastAPI Backend (LangGraph Host) (Queues: Celery)
├── packages/
│   ├── daw-agents/           # LangGraph Agent Definitions (library only)
│   │   └── src/daw_agents/
│   │       ├── agents/       # Agent implementations
│   │       │   ├── planner/  # SDD Agents (PM, Architect, Taskmaster)
│   │       │   ├── developer/# TDD Agents (Red-Green-Refactor)
│   │       │   ├── validator/# QA Agents (separate model from executor)
│   │       │   ├── healer/   # Self-healing agents
│   │       │   └── uat/      # User acceptance testing agents
│   │       ├── schemas/      # Pydantic models for agents
│   │       └── evolution/    # Self-learning components
│   │   └── prompts/          # Prompt templates (versioned, per-agent subdirs)
│   │       ├── planner/
│   │       ├── executor/
│   │       ├── validator/
│   │       └── healer/
│   ├── daw-mcp/              # Custom MCP Servers
│   │   ├── git-mcp/          # Git Operations
│   │   └── graph-memory/     # Neo4j Access
│   └── daw-protocol/         # Shared Types/Schemas (Pydantic/Zod)
├── docker/                   # Deployment containers
├── docs/                     # Documentation (Architecture, PRDs)
├── eval/                     # Evaluation benchmarks and golden outputs
├── scripts/                  # Setup and Maintenance
└── tests/                    # Integration tests
```

## Current Structure (Pre-Refactoring)

> **Note**: Epic 12 (REFACTOR-001 through REFACTOR-007) will migrate from current to target structure.

```
deterministic-agent-workbench/
├── packages/
│   ├── daw-agents/           # Contains BOTH agents AND server (to be separated)
│   ├── daw-frontend/         # Frontend (to be moved to apps/web/)
│   └── daw-shared/           # Shared types (to be renamed daw-protocol)
├── docs/
├── eval/
├── scripts/
└── tests/
```

## Epic to Architecture Mapping

| Epic | Architecture Component |
| :--- | :--- |
| **1. Spec Generation** | **Module: `daw-agents/planner`**. Uses "Taskmaster" pattern. Persists approved Specs to Neo4j Graph. |
| **2. Build Loop** | **Module: `daw-agents/developer`**. Implements the *Red-Green-Refactor* graph. Connects to **E2B** for running `pytest`. |
| **3. Safety** | **Module: `daw-mcp`**. "Guardrails" implemented as Middleware in the MCP Server. Checks `.mcpignore` rules. |
| **4. Ops/Healing** | **Module: `daw-agents/ops`**. "Monitor Agent" subscribes to execution traces (Helicone); triggers "Healer" on failure. |
