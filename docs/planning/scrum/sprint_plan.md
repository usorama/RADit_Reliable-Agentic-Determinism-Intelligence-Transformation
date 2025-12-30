# Sprint Plan: 01 - Foundation (The Kernel)

**Goal**: Initialize the Monorepo, setting up the "Kernel" (FastAPI + LangGraph), the "Sandbox" (E2B), and all supporting Infrastructure (Neo4j, Clerk, Helicone).

## Tasks

### Day 1: Repo Setup & Auth (CORE + AUTH)
- [ ] Initialize Git Monorepo (CORE-001).
- [ ] Setup `packages/daw-agents` (FastAPI) (CORE-002).
- [ ] Implement Clerk Auth Middleware (AUTH-001, AUTH-002).
- [ ] Implement Helicone Observability (OPS-001).

### Day 2: The Agent Graph & Memory (DB + PROTOCOL)
- [ ] Implement Neo4j Connector (DB-001).
- [ ] Implement Context Compactor (CORE-006).
- [ ] Implement MCP Client (CORE-003).
- [ ] Configure MCP Servers (INFRA-001).

### Day 3: The Tool Interface (SANDBOX + GUARD)
- [ ] Implement E2B Sandbox Wrapper (CORE-004).
- [ ] Implement TDD Guard Logic (CORE-005).
- [ ] Verify: Agent can write `print("Hello E2B")` and get the output back.

### Day 4: Frontend Dashboard (WEB)
- [ ] Setup `packages/daw-frontend` (Next.js 14) (FRONTEND-001).
- [ ] Implement Agent Trace UI (FRONTEND-002).
- [ ] Connect Chat UI to FastAPI endpoint.

### Day 5: Agent Logic & Review (AGENTS)
- [ ] Implement Planner Graph (PLANNER-001, PLANNER-002).
- [ ] Implement Executor Graph (EXECUTOR-001).
- [ ] End-to-End Test: User logs in -> Creates PRD -> Agent writes Python code -> Runs in E2B.
