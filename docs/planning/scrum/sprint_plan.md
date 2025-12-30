# Sprint Plan: DAW Implementation

**Last Updated**: 2025-12-30
**Total Tasks**: 50
**Total Epics**: 10
**Estimated Duration**: ~41 hours (with agent parallelism)

---

## Sprint Structure Overview

Based on the agent execution plan, implementation is organized into **8 phases** across **10 execution waves**. Each phase can be treated as a sprint for human coordination.

---

## Phase 0: Infrastructure Setup (Foundation)
**Goal**: Initialize the monorepo and all supporting infrastructure.
**Duration**: ~2 hours (parallel execution)
**Sprint Velocity**: 4 tasks

### Tasks
| Task ID | Description | Priority | Deps | Est. Hours |
|---------|-------------|----------|------|------------|
| CORE-001 | Initialize Monorepo Structure | P0 | - | 0.5 |
| INFRA-001 | Configure Docker & MCP Servers | P0 | CORE-001 | 2 |
| INFRA-002 | Configure Redis (Celery + Checkpoints) | P0 | CORE-001 | 1 |
| PROMPT-GOV-001 | Prompt Template Governance Structure | P1 | CORE-001 | 1 |

### Definition of Done (Phase)
- [ ] Monorepo structure created with packages/
- [ ] docker-compose.yml with Neo4j, Redis, MCP servers
- [ ] Redis pingable and configured
- [ ] Prompt directory structure established

---

## Phase 1: Core Foundations
**Goal**: Initialize backend, frontend, auth, and core services.
**Duration**: ~4 hours (parallel execution)
**Sprint Velocity**: 6 tasks

### Tasks
| Task ID | Description | Priority | Deps | Est. Hours |
|---------|-------------|----------|------|------------|
| CORE-002 | Initialize Python Backend (FastAPI + LangGraph) | P0 | CORE-001 | 1 |
| FRONTEND-001 | Initialize Next.js Frontend | P0 | CORE-001 | 0.5 |
| AUTH-001 | Initialize Clerk Authentication | P0 | CORE-001 | 1 |
| DB-001 | Implement Neo4j Connector | P0 | CORE-002 | 2 |
| CORE-003 | Implement MCP Client Interface | P0 | CORE-002 | 3 |
| MODEL-001 | Implement Model Layer with Router Mode | P0 | CORE-002 | 4 |

### Definition of Done (Phase)
- [ ] FastAPI server starts with /health endpoint
- [ ] Next.js app initializes
- [ ] Clerk API keys configured
- [ ] Neo4j CRUD operations work
- [ ] MCP client can call tools
- [ ] Model router selects appropriate models

**Critical**: MODEL-001 is on the critical path - blocks Planner, Executor, Validator

---

## Phase 2: Security & Governance
**Goal**: Implement authentication middleware and MCP security hardening.
**Duration**: ~4 hours (parallel execution)
**Sprint Velocity**: 6 tasks

### Tasks
| Task ID | Description | Priority | Deps | Est. Hours |
|---------|-------------|----------|------|------------|
| AUTH-002 | Implement FastAPI Clerk Middleware | P0 | CORE-002, AUTH-001 | 2 |
| MCP-SEC-001 | MCP Gateway OAuth 2.1 Authorization | P1 | CORE-003, AUTH-002 | 4 |
| MCP-SEC-002 | RBAC for MCP Tools | P1 | MCP-SEC-001 | 3 |
| MCP-SEC-003 | MCP Audit Logging | P1 | MCP-SEC-001 | 3 |
| MCP-SEC-004 | Content Injection Prevention | P1 | MCP-SEC-001 | 3 |
| PROMPT-GOV-002 | Prompt Regression Testing Harness | P1 | PROMPT-GOV-001, CORE-002 | 4 |

### Definition of Done (Phase)
- [ ] Protected routes reject unauthorized requests
- [ ] OAuth 2.1 tokens scoped per agent role
- [ ] RBAC policies enforced (Planner read-only, etc.)
- [ ] All tool calls audit logged with hash chain
- [ ] Injection attempts blocked at gateway
- [ ] Prompt regression tests run in CI

---

## Phase 3: Core Agent Infrastructure
**Goal**: Build sandbox, TDD enforcement, and observability.
**Duration**: ~3 hours (parallel execution)
**Sprint Velocity**: 4 tasks

### Tasks
| Task ID | Description | Priority | Deps | Est. Hours |
|---------|-------------|----------|------|------------|
| CORE-004 | Implement E2B Sandbox Wrapper | P0 | CORE-002 | 3 |
| CORE-005 | Implement Red-Green-Refactor Enforcement | P0 | CORE-002 | 2 |
| CORE-006 | Implement Context Compaction | P0 | CORE-002, DB-001 | 3 |
| OPS-001 | Implement Helicone Observability | P0 | CORE-002 | 2 |

### Definition of Done (Phase)
- [ ] E2B sandbox executes Python and returns stdout
- [ ] TDD guard blocks src/ writes until tests exist and fail
- [ ] Context compaction produces <4000 tokens from 1000+ messages
- [ ] All LLM calls route through Helicone proxy

---

## Phase 4: Planner Agent
**Goal**: Build the planning agent that generates PRDs from user conversations.
**Duration**: ~6 hours (with some parallelism)
**Sprint Velocity**: 5 tasks

### Tasks
| Task ID | Description | Priority | Deps | Est. Hours |
|---------|-------------|----------|------|------------|
| PLANNER-001 | Implement Taskmaster Agent Workflow | P1 | CORE-002, DB-001, CORE-003, MODEL-001 | 6 |
| PLANNER-002 | Implement Roundtable Personas | P1 | PLANNER-001 | 3 |
| COMPLEXITY-001 | Implement Complexity Analysis Engine | P1 | PLANNER-001, CORE-003 | 4 |
| TASK-DECOMP-001 | Implement Task Decomposition Agent | P0 | PLANNER-001, COMPLEXITY-001 | 4 |
| PRD-OUTPUT-001 | Implement PRD Output Format & Validation | P1 | PLANNER-001 | 3 |

### Definition of Done (Phase)
- [ ] Planner asks clarifying questions before accepting PRD
- [ ] Roundtable personas (CTO, UX, Security) critique plans
- [ ] Complexity analysis produces cognitive load scores
- [ ] Task decomposer generates valid tasks.json
- [ ] PRD output conforms to template with validation

**Critical**: PLANNER-001 is on the critical path - blocks Executor and Orchestrator

---

## Phase 5: Executor Agent
**Goal**: Build the developer agent that writes code following TDD.
**Duration**: ~6 hours (limited parallelism)
**Sprint Velocity**: 3 tasks

### Tasks
| Task ID | Description | Priority | Deps | Est. Hours |
|---------|-------------|----------|------|------------|
| EXECUTOR-001 | Implement Developer Agent Workflow | P1 | CORE-005, CORE-004, CORE-003, MODEL-001 | 6 |
| OPS-002 | Implement Healer Agent | P1 | EXECUTOR-001, DB-001, CORE-003 | 4 |
| RULES-001 | Implement Rule Enforcement | P1 | EXECUTOR-001 | 3 |

### Definition of Done (Phase)
- [ ] Executor follows Red-Green-Refactor loop
- [ ] Code passes tests and linting before commit
- [ ] Healer agent diagnoses and fixes failures (max 3 retries)
- [ ] .cursorrules enforcement active

**Critical**: EXECUTOR-001 is on the critical path - blocks Validator and Orchestrator

---

## Phase 6: Validator & Quality
**Goal**: Build validation pipeline with multi-model ensemble and policy gates.
**Duration**: ~8 hours (with some parallelism)
**Sprint Velocity**: 4 tasks

### Tasks
| Task ID | Description | Priority | Deps | Est. Hours |
|---------|-------------|----------|------|------------|
| VALIDATOR-001 | Implement Validator Agent | P0 | CORE-002, MODEL-001, CORE-003 | 8 |
| VALIDATOR-002 | Implement Multi-Model Ensemble | P0 | VALIDATOR-001 | 4 |
| POLICY-001 | Implement Policy-as-Code Gates | P0 | VALIDATOR-001 | 6 |
| POLICY-002 | Implement Zero-Copy Fork Migrations | P0 | DB-001, POLICY-001 | 4 |

### Definition of Done (Phase)
- [ ] Validator runs on different model than Executor
- [ ] SAST/SCA scans integrated and blocking
- [ ] Multi-model ensemble for critical validations
- [ ] Deployment gates enforce coverage, security, performance thresholds
- [ ] Database migrations tested on zero-copy fork first

**Critical**: VALIDATOR-001 is SEPARATE from Sandbox (architecture requirement)

---

## Phase 7: UAT & Eval
**Goal**: Build evaluation benchmarks, UAT automation, and frontend features.
**Duration**: ~6 hours (highly parallel)
**Sprint Velocity**: 15 tasks

### Tasks
| Task ID | Description | Priority | Deps | Est. Hours |
|---------|-------------|----------|------|------------|
| API-001 | Define FastAPI Route Endpoints | P1 | CORE-002, AUTH-002 | 4 |
| STREAMING-001 | Implement WebSocket Streaming | P1 | CORE-002, FRONTEND-001 | 4 |
| FRONTEND-AUTH-001 | Integrate Clerk React SDK | P1 | FRONTEND-001, AUTH-001 | 3 |
| FRONTEND-002 | Implement Agent Trace UI | P1 | FRONTEND-001, STREAMING-001 | 4 |
| FRONTEND-003 | Implement Chat Interface | P0 | FRONTEND-001, STREAMING-001 | 4 |
| INFRA-003 | Configure Celery Workers | P1 | INFRA-002 | 3 |
| EVAL-001 | Establish Golden Benchmark Suite | P0 | PLANNER-001, EXECUTOR-001 | 3 |
| EVAL-002 | Implement Eval Harness | P0 | EVAL-001, VALIDATOR-001 | 6 |
| EVAL-003 | Implement Similarity Scoring | P0 | EVAL-002 | 3 |
| UAT-001 | Implement UAT Agent (Playwright) | P1 | VALIDATOR-001, FRONTEND-002, CORE-003 | 6 |
| UAT-002 | Implement Persona-Based Testing | P1 | UAT-001 | 3 |
| UAT-003 | Implement Visual Regression | P1 | UAT-001 | 3 |

### Definition of Done (Phase)
- [ ] API routes documented and protected
- [ ] WebSocket streaming works for live traces
- [ ] Frontend authentication flow complete
- [ ] Chat interface renders markdown and streams responses
- [ ] 10-20 golden benchmarks defined
- [ ] Eval harness tracks pass@1, completion rate, cost
- [ ] UAT agent automates user journey testing
- [ ] Visual regression catches <0.1% changes

---

## Phase 8: Observability & Operations
**Goal**: Complete drift detection and the main orchestrator.
**Duration**: ~8 hours (limited parallelism at end)
**Sprint Velocity**: 3 tasks

### Tasks
| Task ID | Description | Priority | Deps | Est. Hours |
|---------|-------------|----------|------|------------|
| DRIFT-001 | Implement Drift Detection Metrics | P2 | OPS-001, EXECUTOR-001 | 4 |
| DRIFT-002 | Implement Drift Alerting & Actions | P2 | DRIFT-001 | 3 |
| ORCHESTRATOR-001 | Implement Main Workflow Orchestrator | P0 | MODEL-001, PLANNER-001, EXECUTOR-001, VALIDATOR-001 | 8 |

### Definition of Done (Phase)
- [ ] Drift metrics tracked (tool usage, step count, cost)
- [ ] Alerts fire and actions trigger on thresholds
- [ ] Orchestrator coordinates full pipeline: Input → Planner → Executor → Validator → Deploy

**Critical**: ORCHESTRATOR-001 is the final integration - requires all prior phases complete

---

## MVP Milestone (End of Phase 6)

After Phase 6, the system achieves MVP:
- [ ] User can login (Clerk)
- [ ] User can chat with Planner to create PRD
- [ ] Executor can generate code with passing tests in E2B
- [ ] Validator validates independently with different model

---

## Full System (End of Phase 8)

After Phase 8, the system is complete:
- [ ] All 50 tasks implemented
- [ ] All 10 epics delivered
- [ ] All 34 stories pass DoD
- [ ] Eval benchmarks achieve >= 85% pass@1
- [ ] Production-ready with drift detection and alerting

---

## References

- Task Details: `docs/planning/tasks.json`
- Agent Execution Plan: `docs/planning/agent_execution_plan.md`
- Definition of Done: `docs/planning/stories/definition_of_done.md`
- TDD Workflow: `docs/planning/tdd_workflow.md`
- Progress Tracking: `PROGRESS.md`

---

*Sprint plan updated: 2025-12-30*
*Aligned with: 8-phase structure, 10 epics, 50 tasks*
