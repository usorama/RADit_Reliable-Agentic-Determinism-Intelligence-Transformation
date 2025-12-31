# Product Requirements Document (PRD): Deterministic Agentic Workbench

**Version**: 1.0
**Status**: Draft
**Derived From**: *Deterministic SSDLC* (Research) & *BMAD Method*

## Overview
The **Deterministic Agentic Workbench (DAW)** is an "Agent Operating System" designed to enforce rigorous engineering standards on Generative AI code generation. It replaces "vibe coding" with **Spec-Driven** and **Test-Driven** development.

## Documentation Map
This PRD is sharded into the following sections for maintainability:

- **[01_problem_and_goals.md](./sections/01_problem_and_goals.md)**: The "Why" and "What" (Goals, KPIs, Audience).
- **[02_functional_requirements.md](./sections/02_functional_requirements.md)**: Detailed breakdown of the Agent OS, Planner, Executor, and Validator engines. Includes FR-08 (User Interaction), FR-09 (Monitor-Diagnose-Heal), FR-10 (Multi-Model Driver).
- **[05_task_decomposition.md](./sections/05_task_decomposition.md)**: Strategy for parsing PRD into atomic `tasks.json`.
- **[06_mvp_scope_definition.md](./sections/06_mvp_scope_definition.md)**: Clear definition of MVP vs Production vs Future scope with feature categorization.

## Key Principles
1.  **Red-Green-Refactor**: No code without a failing test.
2.  **Ephemerality**: All code runs in disposable E2B sandboxes. **Side-Effect Containment** is mandatory.
3.  **Determinism**: Graph-based memory (Neo4j) over purely purely probabilistic vector search.
4.  **Agnosticism**: Model Context Protocol (MCP) to detach from specific LLM providers.
5.  **Security**: Strict `.mcpignore` protocol to prevent data leakage.
