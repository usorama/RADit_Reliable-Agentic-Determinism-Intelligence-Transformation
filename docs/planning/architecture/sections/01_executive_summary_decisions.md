# 01. Executive Summary & Decisions

## Executive Summary
The Deterministic Agentic Workbench (DAW) is an **Agent Operating System** designed to bridge the "Determinism Gap" in Generative AI engineering. Unlike probabilistic chat interfaces, DAW imposes strict architectural constraints—**Spec-Driven Development (SDD)** and **Test-Driven Development (TDD)**—to ensure that AI-generated software is reliable, secure, and production-ready.

## Decision Summary

| Category | Decision | Version | Affects Epics | Rationale |
| -------- | -------- | ------- | ------------- | --------- |
| **Orchestration** | **LangGraph** (Python) | 1.x | All | Selected for its superior state management, "human-in-the-loop" checkpoints, and cyclic graph capabilities required for the Red-Green-Refactor loop. |
| **Sandboxing** | **E2B** | 1.x | Security | Provides secure, ephemeral cloud sandboxes with sub-second startup times, specifically designed for AI code interpretation. |
| **Protocol** | **MCP** (Model Context Protocol) | 2024-11 | Integration | Ensures the system is LLM-agnostic and creates a clear boundary between the "reasoning engine" and the "tools". |
| **Memory/DB** | **Neo4j** (Graph + Vector) | 5.x | Planning, Ops | Chosen over pure vector DBs to enable *deterministic* retrieval of explicit relationships (e.g., "Dependency A requires Component B") alongside semantic search. |
| **Auth/Identity** | **Clerk** | Latest | Security | Selected for its superior DX and dedicated "Agent Toolkit" for managing M2M identities. |
| **Observability/Cost** | **Helicone** | OSS | Ops | Open-source alternative to LangSmith. Selected for "Zero Markup" billing and caching capabilities to reduce LLM costs by 30%. |
| **Async Queues** | **Celery + Redis** | 5.x | Scalability | Distributed task queue to handle long-running agent workflows and parallel execution. |
| **Frontend** | **Next.js** (TypeScript) | 14+ | UX/Dashboard | Industry standard for robust, interactive dashboards. Type-safety in the UI layer complements the deterministic backend. |
| **Backend API** | **FastAPI** (Python) | 0.100+ | API | Native integration with LangGraph and the broader AI/Data Science ecosystem. |
