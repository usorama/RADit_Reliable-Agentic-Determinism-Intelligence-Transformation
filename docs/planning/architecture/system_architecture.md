# Architecture: Deterministic Agentic Workbench (DAW)

**Status**: Draft (Verified)
**Derived From**: *Deterministic SSDLC* & *BMAD Method*

## Overview
DAW is a micro-agent architecture orchestrated by **LangGraph** (Python), utilizing **Neo4j** for deterministic memory and **E2B** for secure code execution.

## Documentation Map
This architecture document is sharded into:

- **[01_executive_summary_decisions.md](./sections/01_executive_summary_decisions.md)**: High-level overview and key tech decisions (Clerk, Helicone, Celery).
- **[02_project_structure.md](./sections/02_project_structure.md)**: Monorepo layout and container strategy.
- **[03_tech_stack_details.md](./sections/03_tech_stack_details.md)**: Detailed component breakdown (LangGraph, MCP, Neo4j).
- **[04_implementation_patterns.md](./sections/04_implementation_patterns.md)**: "Double Entry" verification and "Context Compaction".
- **[05_deployment.md](./sections/05_deployment.md)**: Docker/K8s setup and CI/CD pipelines.
- **[06_epic13_plus_components.md](./sections/06_epic13_plus_components.md)**: Epic 13+ new components: Orchestrator states, API endpoints, frontend components, MCP servers.

## Tech Stack Highlights
*   **Orchestration**: LangGraph
*   **Auth**: Clerk
*   **Observability**: Helicone (Zero Markup, Caching)
*   **Queues**: Celery + Redis
*   **Memory**: Neo4j (Graph + Vector)
