# Epics & User Stories

## Epic 1: Workbench Core (The "Kernel")
**Goal**: Build the foundational "Agent OS" capabilities, including Context Management, Tool Execution (MCP), and Authentication.

-   **Story 1.1**: [Backend] Set up FastAPI foundation with LangGraph integration.
    -   *AC*: `GET /health` returns 200. LangGraph StateGraph is initialized.
    -   *Task Ref*: CORE-001, CORE-002
-   **Story 1.2**: [Auth] Integrate Clerk for User Authentication.
    -   *AC*: Dashboard is protected. JWTs are validated by FastAPI middleware.
    -   *Task Ref*: AUTH-001, AUTH-002
-   **Story 1.3**: [Memory] Implement Neo4j connectivity.
    -   *AC*: Can write and read a "Project Node" to the graph. Including "Context Compaction" query.
    -   *Task Ref*: DB-001, CORE-006
-   **Story 1.4**: [MCP] Configure generic MCP Client and default Servers (`git`, `filesystem`).
    -   *AC*: Can execute `git status` and `ls` via MCP. Security Policies (allowlist) are active.
    -   *Task Ref*: CORE-003, INFRA-001

## Epic 2: The Planner Agent (Spec-Driven Dev)
**Goal**: Create the agent workflow that interviews users and generates a deterministic PRD.

-   **Story 2.1**: [AI] Implement "Senior PM" Persona prompt chain.
    -   *AC*: Agent asks 3 clarifying questions before accepting a prompt.
    -   *Task Ref*: PLANNER-001
-   **Story 2.2**: [Workflow] Implement the "Taskmaster" loop.
    -   *AC*: Conversation history is persisted to Neo4j. "Roundtable" personas (CTO, UX) critique the concept.
    -   *Task Ref*: PLANNER-001, PLANNER-002
-   **Story 2.3**: [Output] Implement `generate_prd` Tool.
    -   *AC*: Agent can write a valid Markdown file to the `docs/` folder.
    -   *Task Ref*: PLANNER-001

## Epic 3: The Executor Agent (Test-Driven Dev)
**Goal**: The core "Red-Green-Refactor" coding loop.

-   **Story 3.1**: [Sandbox] Integrate E2B SDK.
    -   *AC*: Can spin up a sandbox and return `stdout` from a Python script.
    -   *Task Ref*: CORE-004
-   **Story 3.2**: [Workflow] Implement "Red Phase" constraint.
    -   *AC*: Agent is blocked from writing `src/` files until a `tests/` file exists and fails.
    -   *Task Ref*: CORE-005, EXECUTOR-001
-   **Story 3.3**: [Workflow] Implement "Green Phase" & "Healer Loop".
    -   *AC*: Agent auto-retries code generation up to 3 times if tests fail. Use RAG to diagnose errors via Healer Agent.
    -   *Task Ref*: EXECUTOR-001, OPS-002

## Epic 4: Observability & Monitoring
**Goal**: Ensure we can see what the agents are thinking and how much they cost.

-   **Story 4.1**: [Ops] Integrate Helicone proxy.
    -   *AC*: All OpenAI calls go through `oai.helicone.ai`. Dashboard shows costs.
    -   *Task Ref*: OPS-001
-   **Story 4.2**: [UI] Build "Agent Trace" view in Next.js.
    -   *AC*: User can see the live "thought bubble" of the running agent.
    -   *Task Ref*: FRONTEND-001, FRONTEND-002
-   **Story 4.3**: [Ops] Implement Drift Detection Metrics.
    -   *AC*: System monitors Tool Usage Frequency, Reasoning Step Count, Context Window Utilization, Retry Rate, and Token Cost per Task. Alerts fire when thresholds exceeded (+50% tool deviation = warning, +100% step count = pause agent, >90% context = force compaction).
    -   *Task Ref*: DRIFT-001
    -   *Gap Ref*: Gap 7 (Research Paper Lines 218-223)
-   **Story 4.4**: [Ops] Implement Drift Detection Alerting and Actions.
    -   *AC*: Integration with Helicone/Datadog. Slack/Linear notifications. Weekly drift reports. Graduated response: Mild → log, Moderate → compaction, Severe → pause + human.
    -   *Task Ref*: DRIFT-002
    -   *Gap Ref*: Gap 7 (Research Paper Lines 218-223)

---

## Epic 5: Validator Agent & Quality Assurance
**Goal**: Implement an intelligent Validator Agent DISTINCT from the sandbox execution environment, running on a different model to prevent bias. This addresses Gap 1 (Critical) from the research paper.

-   **Story 5.1**: [AI] Implement Validator Agent LangGraph Workflow.
    -   *AC*: Validator Agent is architecturally separate from E2B sandbox. Runs on a DIFFERENT model than Executor (e.g., if Executor uses Claude, Validator uses GPT-4o). States: [run_tests, security_scan, policy_check, generate_report, route_decision].
    -   *Task Ref*: VALIDATOR-001
    -   *Gap Ref*: Gap 1 (Research Paper Lines 55-61)
-   **Story 5.2**: [AI] Implement Validator Test Execution and Interpretation.
    -   *AC*: Validator runs test suites and provides intelligent interpretation of failures, not just pass/fail. Generates actionable improvement suggestions.
    -   *Task Ref*: VALIDATOR-001
    -   *Gap Ref*: Gap 1 (Research Paper Lines 55-61)
-   **Story 5.3**: [Security] Implement Validator SAST/SCA Integration.
    -   *AC*: Validator runs static analysis security scans and dependency vulnerability checks. Results feed into pass/fail decision.
    -   *Task Ref*: VALIDATOR-001
    -   *Gap Ref*: Gap 1 (Research Paper Lines 55-61)
-   **Story 5.4**: [AI] Implement Multi-Model Validation Ensemble.
    -   *AC*: Critical validations (security, production deploys) use 2+ models with voting/consensus mechanism. Configurable which validations require ensemble.
    -   *Task Ref*: VALIDATOR-002
    -   *Gap Ref*: Gap 1 (Research Paper Lines 55-61)
-   **Story 5.5**: [Workflow] Implement Validator Retry and Escalation Logic.
    -   *AC*: Fixable failures route back to Executor (max 3 retries). Critical/unfixable issues escalate to human reviewers with full context.
    -   *Task Ref*: VALIDATOR-001
    -   *Gap Ref*: Gap 1 (Research Paper Lines 55-61)

---

## Epic 6: MCP Security & Governance
**Goal**: Harden the MCP gateway with OAuth 2.1 authorization, fine-grained RBAC, audit logging, and content injection prevention. This addresses Gap 8 (High) from the research paper.

-   **Story 6.1**: [Security] Implement MCP Gateway OAuth 2.1 Authorization.
    -   *AC*: OAuth 2.1 with RFC 8707 Resource Indicators. Per-agent scoped tokens (e.g., database agent: SELECT only). Token TTL: 15 min automated, 1 hour interactive.
    -   *Task Ref*: MCP-SEC-001
    -   *Gap Ref*: Gap 8 (Research Paper Lines 185-191)
-   **Story 6.2**: [Security] Implement RBAC for MCP Tools.
    -   *AC*: Fine-grained role definitions: Planner (read-only), Executor (scoped writes), Validator (no writes), Healer (patch-only with approval). Policies stored in YAML.
    -   *Task Ref*: MCP-SEC-002
    -   *Gap Ref*: Gap 8 (Research Paper Lines 185-191)
-   **Story 6.3**: [Security] Implement MCP Audit Logging.
    -   *AC*: Every tool call logged with timestamp, agent_id, user_id, tool, action, params, result. Hash-chained for tamper resistance. 7-year retention for SOC 2/ISO 27001.
    -   *Task Ref*: MCP-SEC-003
    -   *Gap Ref*: Gap 8 (Research Paper Lines 185-191)
-   **Story 6.4**: [Security] Implement Content Injection Prevention.
    -   *AC*: AI Prompt Shields active. JSON schema validation on all tool I/O. Blocked patterns: DROP, DELETE, rm -rf, sudo. Malicious requests rejected at gateway.
    -   *Task Ref*: MCP-SEC-004
    -   *Gap Ref*: Gap 8 (Research Paper Lines 185-191)

---

## Epic 7: Prompt Template Governance
**Goal**: Treat prompts as first-class code artifacts with version control, self-correction checklists, and regression testing. This addresses Gap 3 (High) from the research paper.

-   **Story 7.1**: [DevOps] Establish Prompt Governance Structure.
    -   *AC*: All prompts in `packages/daw-agents/{agent}/prompts/`. Semantic versioning (e.g., `prd_generator_v1.0.yaml`). Each prompt has version, name, persona, system_prompt, validation_checklist, output_schema.
    -   *Task Ref*: PROMPT-GOV-001
    -   *Gap Ref*: Gap 3 (Research Paper Lines 113-118)
-   **Story 7.2**: [Testing] Implement Prompt Regression Testing Harness.
    -   *AC*: Golden input/output pairs in `tests/prompts/goldens/`. CI runs regression tests on prompt changes. Semantic similarity scoring (>= 85% threshold). JSON schema validation for structured outputs.
    -   *Task Ref*: PROMPT-GOV-002
    -   *Gap Ref*: Gap 3 (Research Paper Lines 113-118)

---

## Epic 8: Deployment & Policy-as-Code
**Goal**: Implement codified deployment policies enforced automatically by Validator Agent. This addresses Gap 4 (Critical) from the research paper.

-   **Story 8.1**: [DevOps] Implement Policy-as-Code Deployment Gates.
    -   *AC*: Gate 1 (Quality): Coverage >= 80% new, >= 70% total, strict mode, 0 lint errors. Gate 2 (Security): 0 SAST critical, 0 SCA critical CVEs, 0 secrets. Gate 3 (Performance): p95 < 500ms, bundle < +10%. Gate 4 (UAT): P0 journeys 100%, visual < 0.1%.
    -   *Task Ref*: POLICY-001
    -   *Gap Ref*: Gap 4 (Research Paper Lines 193-196)
-   **Story 8.2**: [DevOps] Implement Zero-Copy Fork for Database Migrations.
    -   *AC*: Create instant zero-copy fork of production DB. Apply migration to fork. Run validation suite. If pass → apply to production. If fail → discard fork with zero impact.
    -   *Task Ref*: POLICY-002
    -   *Gap Ref*: Gap 4 (Research Paper Lines 193-196)

---

## Epic 9: UAT Automation
**Goal**: Implement automated User Acceptance Testing using Playwright MCP with persona-based testing and visual regression. This addresses Gap 5 (High) from the research paper.

-   **Story 9.1**: [Testing] Implement UAT Agent with Playwright MCP.
    -   *AC*: UAT Agent uses Playwright MCP for browser automation. Operates on accessibility snapshots (not screenshots). Supports Chromium, Firefox, WebKit. Executes Gherkin scenarios from PRD acceptance criteria.
    -   *Task Ref*: UAT-001
    -   *Gap Ref*: Gap 5 (Research Paper Lines 235-237)
-   **Story 9.2**: [Testing] Implement Persona-Based UAT Testing.
    -   *AC*: Personas defined in `uat/personas.yaml`: Power User (desktop, fast, keyboard), First-Time User (mobile, 3G, help-seeking), Accessibility User (screen reader, keyboard-only). Personas modify agent interaction behavior.
    -   *Task Ref*: UAT-002
    -   *Gap Ref*: Gap 5 (Research Paper Lines 235-237)
-   **Story 9.3**: [Testing] Implement Visual Regression Testing.
    -   *AC*: AI-powered visual comparison (Applitools Eyes or equivalent). Threshold < 0.1% for critical UI. Automatic baseline updates for approved changes.
    -   *Task Ref*: UAT-003
    -   *Gap Ref*: Gap 5 (Research Paper Lines 235-237)

---

## Epic 10: Eval Protocol & Benchmarking
**Goal**: Implement systematic agent performance measurement with golden benchmarks and release gating. This addresses Gap 6 (Critical) from the research paper.

-   **Story 10.1**: [Testing] Establish Golden PRD Benchmark Suite.
    -   *AC*: 10-20 representative PRDs (Calculator, ToDo, E-commerce, etc.). Expected outputs stored as golden references. Scoring rubrics defined per benchmark. Index file with metadata.
    -   *Task Ref*: EVAL-001
    -   *Gap Ref*: Gap 6 (Research Paper Line 251)
-   **Story 10.2**: [Testing] Implement Eval Harness with Performance Metrics.
    -   *AC*: DeepEval or Braintrust framework. Metrics: pass@1 >= 85% (blocking), Task Completion >= 90% (blocking), pass^8 >= 60% (warning), Cost < $0.50 (advisory). CI nightly runs. Regression > 5% triggers alert.
    -   *Task Ref*: EVAL-002
    -   *Gap Ref*: Gap 6 (Research Paper Line 251)
-   **Story 10.3**: [Testing] Implement Agent Similarity Scoring.
    -   *AC*: Semantic similarity for text (embedding-based, >= 85%). AST comparison for code. JSON schema validation for structured outputs. Detailed divergence reports.
    -   *Task Ref*: EVAL-003
    -   *Gap Ref*: Gap 6 (Research Paper Line 251)

---

## Epic 2 (Extended): Complexity Analysis Engine
**Goal**: Add complexity analysis as a required step before code generation. This addresses Gap 2 (High) from the research paper.

-   **Story 2.4**: [AI] Implement Complexity Analysis Engine.
    -   *AC*: Before task generation, system produces `complexity_analysis.json` with: feature cognitive load scores (1-10), dependency graph with risk ratings, recommended model tier per task, architectural bottleneck warnings. Analysis MUST complete before task generation proceeds.
    -   *Task Ref*: COMPLEXITY-001
    -   *Gap Ref*: Gap 2 (Research Paper Lines 105-107)

---

## Epic 11: Self-Evolution Foundation (Learning Layer)
**Goal**: Establish the data foundation for autonomous improvement, transitioning from purely reactive (Monitor-Diagnose-Heal) to proactive learning patterns. This addresses the self-evolution gap identified in the 2025-12-30 analysis.

-   **Story 11.1**: [AI] Implement Experience Logger for Neo4j.
    -   *AC*: Every task completion creates an Experience node in Neo4j with: task_type, task_id, success, prompt_version, model_used, tokens_used, cost_usd, duration_ms, retries, timestamp. Relationships: (:Experience)-[:USED_SKILL]->(:Skill) for patterns, (:Experience)-[:PRODUCED]->(:Artifact) for outputs. Success rates queryable per task type, model, prompt version, time window.
    -   *Task Ref*: EVOLVE-001
    -   *FR Ref*: FR-07.1 (Experience Logger)
-   **Story 11.2**: [AI] Implement Reflection Hook for Post-Task Learning.
    -   *AC*: After task completion, ReflectionHook triggers asynchronously. Uses LLM to analyze: "What worked?", "What patterns to remember?", "What to improve?". Stores (:Insight) nodes linked to (:Experience). Three depth modes: quick (metrics only), standard (LLM reflection), deep (multi-model consensus). Non-blocking execution.
    -   *Task Ref*: EVOLVE-002
    -   *FR Ref*: FR-07.2 (Reflection Hook)
-   **Story 11.3**: [Future] Skill Library Integration (Placeholder).
    -   *AC*: Reserved for Phase 2. Will extract reusable code patterns from successful experiences (Voyager pattern).
    -   *Task Ref*: EVOLVE-003 (not yet in tasks.json)
    -   *FR Ref*: FR-07.3.1 (Skill Library)
-   **Story 11.4**: [Future] Prompt Optimization (Placeholder).
    -   *AC*: Reserved for Phase 3. Will implement DSPy-style automatic prompt improvement based on experience success metrics.
    -   *Task Ref*: EVOLVE-005 (not yet in tasks.json)
    -   *FR Ref*: FR-07.3.2 (Prompt Optimization)

**Design Principle**: Stories 11.1 and 11.2 create the data foundation (experiences, insights) that Stories 11.3 and 11.4 will consume for skill extraction and prompt optimization.

---

## Epic 12: Architecture Conformance Refactoring
**Goal**: Restructure the codebase to align with the documented architecture in `docs/planning/architecture/sections/02_project_structure.md`. This is a comprehensive refactoring effort requiring file-by-file, folder-by-folder migration with full E2E testing validation.

**Background**: The current implementation deviated from the documented architecture:
| Documented | Current | Required Change |
|------------|---------|-----------------|
| `apps/web/` | `packages/daw-frontend/` | Move frontend to apps/web/ |
| `apps/server/` | (embedded in daw-agents) | Extract server to apps/server/ |
| `packages/daw-agents/` | Contains agents + server | Keep agents only |
| `packages/daw-mcp/` | Missing | Create MCP servers package |
| `packages/daw-protocol/` | `packages/daw-shared/` | Rename to daw-protocol |

-   **Story 12.1**: [Infra] Create apps/ directory structure.
    -   *AC*: `apps/web/` and `apps/server/` directories created. Monorepo tooling (pnpm workspaces, turbo) updated to recognize new structure.
    -   *Task Ref*: REFACTOR-001
    -   *Architecture Ref*: 02_project_structure.md
    -   *Dependencies*: None (first task)
    -   *Implementation Steps*:
        1. Create directory structure: `mkdir -p apps/web apps/server`
        2. Read current `pnpm-workspace.yaml` and add `'apps/*'` to packages array
        3. If `turbo.json` exists, update pipeline to include apps
        4. Run `pnpm install` to verify monorepo recognizes new structure
        5. Verify: `ls apps/` shows web/ and server/ directories
    -   *Files to Create/Modify*:
        - `apps/web/.gitkeep` (placeholder)
        - `apps/server/.gitkeep` (placeholder)
        - `pnpm-workspace.yaml` (add apps/*)
        - `turbo.json` (if exists)

-   **Story 12.2**: [Frontend] Migrate daw-frontend to apps/web/.
    -   *AC*: All files from `packages/daw-frontend/` moved to `apps/web/`. Package.json updated with correct name. All imports updated. `pnpm install` succeeds. `pnpm dev` runs frontend successfully. No TypeScript errors.
    -   *Task Ref*: REFACTOR-002
    -   *Architecture Ref*: 02_project_structure.md
    -   *Dependencies*: REFACTOR-001
    -   *Implementation Steps*:
        1. Copy all files from `packages/daw-frontend/` to `apps/web/` (preserve structure)
           - EXCLUDE: `node_modules/`, `.next/`, `*.tsbuildinfo`
        2. Update `apps/web/package.json`:
           - Change `"name"` to `"@daw/web"`
           - Verify all dependency paths are correct
        3. Update `apps/web/tsconfig.json`:
           - Adjust `baseUrl` and `paths` if they reference parent directories
        4. Search for any imports referencing `daw-frontend` and update to `@daw/web`
        5. Run `cd apps/web && pnpm install`
        6. Run `cd apps/web && pnpm typecheck` - must be 0 errors
        7. Run `cd apps/web && pnpm dev` - verify it starts on localhost:3000
        8. Run `cd apps/web && pnpm build` - verify production build succeeds
        9. Delete `packages/daw-frontend/` only after all verifications pass
    -   *Files to Move*:
        - `packages/daw-frontend/src/**/*` → `apps/web/src/**/*`
        - `packages/daw-frontend/public/**/*` → `apps/web/public/**/*`
        - `packages/daw-frontend/package.json` → `apps/web/package.json` (modify)
        - `packages/daw-frontend/tsconfig.json` → `apps/web/tsconfig.json`
        - `packages/daw-frontend/next.config.*` → `apps/web/next.config.*`
        - `packages/daw-frontend/postcss.config.*` → `apps/web/postcss.config.*`
        - `packages/daw-frontend/tailwind.config.*` → `apps/web/tailwind.config.*`
    -   *Verification Commands*:
        ```bash
        cd apps/web && pnpm install
        cd apps/web && pnpm typecheck  # 0 errors
        cd apps/web && pnpm build      # succeeds
        cd apps/web && pnpm dev &      # starts on :3000
        curl -f http://localhost:3000  # responds
        ```

-   **Story 12.3**: [Backend] Extract FastAPI server to apps/server/.
    -   *AC*: FastAPI application code extracted from `packages/daw-agents/` to `apps/server/`. Includes: API routes, WebSocket handlers, middleware, Celery workers. Server imports agents from `packages/daw-agents/`. `uvicorn` starts successfully. All API endpoints respond.
    -   *Task Ref*: REFACTOR-003
    -   *Architecture Ref*: 02_project_structure.md
    -   *Dependencies*: REFACTOR-001
    -   *Implementation Steps*:
        1. Create `apps/server/pyproject.toml` with project metadata:
           - name = "daw-server"
           - Add dependency on `daw-agents` (path = "../../packages/daw-agents")
           - Add FastAPI, uvicorn, celery, redis dependencies
        2. Create `apps/server/src/daw_server/` package structure
        3. Move from `packages/daw-agents/src/daw_agents/`:
           - `api/` → `apps/server/src/daw_server/api/`
           - `workers/` → `apps/server/src/daw_server/workers/`
           - `auth/` → `apps/server/src/daw_server/auth/`
           - `main.py` → `apps/server/src/daw_server/main.py`
        4. Update all imports in moved files:
           - `from daw_agents.agents` → `from daw_agents.agents` (external import)
           - `from daw_agents.api` → `from daw_server.api` (internal import)
        5. Create `apps/server/src/daw_server/__init__.py` with exports
        6. Run `cd apps/server && poetry install`
        7. Run `cd apps/server && uvicorn daw_server.main:app` - verify starts
        8. Test: `curl -f http://localhost:8000/health` - must respond
        9. Run `cd apps/server && pytest tests/` - API tests pass
    -   *Files to Create*:
        - `apps/server/pyproject.toml`
        - `apps/server/src/daw_server/__init__.py`
        - `apps/server/src/daw_server/main.py`
        - `apps/server/tests/__init__.py`
    -   *Files to Move*:
        - `packages/daw-agents/src/daw_agents/api/**/*` → `apps/server/src/daw_server/api/**/*`
        - `packages/daw-agents/src/daw_agents/workers/**/*` → `apps/server/src/daw_server/workers/**/*`
        - `packages/daw-agents/src/daw_agents/auth/**/*` → `apps/server/src/daw_server/auth/**/*`
    -   *Verification Commands*:
        ```bash
        cd apps/server && poetry install
        cd apps/server && poetry run uvicorn daw_server.main:app --host 0.0.0.0 --port 8000 &
        sleep 5 && curl -f http://localhost:8000/health
        cd apps/server && poetry run pytest tests/
        ```

-   **Story 12.4**: [Agents] Refactor daw-agents to contain only agent definitions.
    -   *AC*: `packages/daw-agents/` contains ONLY: LangGraph agent definitions (planner/, developer/, validator/, healer/, uat/), agent schemas, agent prompts. No FastAPI routes, no Celery config, no API handlers. Agents importable as library.
    -   *Task Ref*: REFACTOR-004
    -   *Architecture Ref*: 02_project_structure.md
    -   *Dependencies*: REFACTOR-003 (must complete first - files moved to apps/server)
    -   *Implementation Steps*:
        1. Verify REFACTOR-003 completed - files now in apps/server/
        2. Delete from `packages/daw-agents/src/daw_agents/`:
           - `api/` directory (now in apps/server)
           - `workers/` directory (now in apps/server)
           - `auth/` directory (now in apps/server)
           - `main.py` (now in apps/server)
        3. Keep these directories/files:
           - `agents/` - all agent implementations
           - `schemas/` - Pydantic models
           - `evolution/` - experience logger, reflection
           - `models/` - model router
           - `mcp/` - MCP client (NOT servers - those go to daw-mcp)
           - `memory/` - Neo4j connector
           - `context/` - context compaction
           - `sandbox/` - E2B wrapper
           - `tdd/` - TDD guard
           - `ops/` - drift detection
           - `deploy/` - deployment gates
           - `testing/` - prompt harness
           - `workflow/` - orchestrator, rule enforcer
           - `config/` - configuration
           - `prompts/` at package root
        4. Update `packages/daw-agents/src/daw_agents/__init__.py`:
           - Remove exports for api, workers, auth
           - Keep exports for agents, schemas, evolution, etc.
        5. Update `packages/daw-agents/pyproject.toml`:
           - Remove FastAPI, uvicorn, celery from dependencies (server-only)
           - Keep langgraph, langchain, litellm, neo4j, etc.
        6. Run `cd packages/daw-agents && poetry install`
        7. Run `cd packages/daw-agents && pytest tests/agents/` - all pass
        8. Verify package is importable: `python -c "from daw_agents.agents import *"`
    -   *Directories to DELETE* (after REFACTOR-003):
        - `packages/daw-agents/src/daw_agents/api/`
        - `packages/daw-agents/src/daw_agents/workers/`
        - `packages/daw-agents/src/daw_agents/auth/`
        - `packages/daw-agents/src/daw_agents/main.py`
    -   *Directories to KEEP*:
        - `packages/daw-agents/src/daw_agents/agents/`
        - `packages/daw-agents/src/daw_agents/schemas/`
        - `packages/daw-agents/src/daw_agents/evolution/`
        - `packages/daw-agents/src/daw_agents/models/`
        - `packages/daw-agents/src/daw_agents/mcp/` (client only)
        - `packages/daw-agents/src/daw_agents/memory/`
        - `packages/daw-agents/src/daw_agents/context/`
        - `packages/daw-agents/src/daw_agents/sandbox/`
        - `packages/daw-agents/src/daw_agents/tdd/`
        - `packages/daw-agents/src/daw_agents/ops/`
        - `packages/daw-agents/src/daw_agents/deploy/`
        - `packages/daw-agents/src/daw_agents/testing/`
        - `packages/daw-agents/src/daw_agents/workflow/`
        - `packages/daw-agents/src/daw_agents/config/`
        - `packages/daw-agents/prompts/`
    -   *Verification Commands*:
        ```bash
        cd packages/daw-agents && poetry install
        cd packages/daw-agents && poetry run pytest tests/agents/
        python -c "from daw_agents.agents.planner import *; print('OK')"
        python -c "from daw_agents.agents.validator import *; print('OK')"
        ```

-   **Story 12.5**: [MCP] Create packages/daw-mcp/ for custom MCP servers.
    -   *AC*: `packages/daw-mcp/` created with subdirectories: `git-mcp/`, `graph-memory/`. MCP server implementations moved/created here. Servers register with MCP protocol correctly.
    -   *Task Ref*: REFACTOR-005
    -   *Architecture Ref*: 02_project_structure.md
    -   *Dependencies*: REFACTOR-001
    -   *Implementation Steps*:
        1. Create directory structure:
           ```
           packages/daw-mcp/
           ├── pyproject.toml
           ├── src/
           │   └── daw_mcp/
           │       ├── __init__.py
           │       ├── git_mcp/
           │       │   ├── __init__.py
           │       │   └── server.py
           │       └── graph_memory/
           │           ├── __init__.py
           │           └── server.py
           └── tests/
               └── __init__.py
           ```
        2. Create `pyproject.toml` with MCP SDK dependencies:
           - mcp (Model Context Protocol SDK)
           - neo4j (for graph-memory)
           - gitpython (for git-mcp)
        3. If MCP server code exists in `packages/daw-agents/src/daw_agents/mcp/`:
           - Identify SERVER code (not client) and move to daw-mcp
           - Keep CLIENT code in daw-agents
        4. Create placeholder implementations if servers don't exist yet:
           - `git_mcp/server.py`: Git operations MCP server
           - `graph_memory/server.py`: Neo4j memory MCP server
        5. Each server must implement MCP protocol:
           - `list_tools()` - returns available tools
           - `call_tool(name, params)` - executes tool
        6. Run `cd packages/daw-mcp && poetry install`
        7. Test: Start each server and verify tool discovery works
    -   *Files to Create*:
        - `packages/daw-mcp/pyproject.toml`
        - `packages/daw-mcp/src/daw_mcp/__init__.py`
        - `packages/daw-mcp/src/daw_mcp/git_mcp/__init__.py`
        - `packages/daw-mcp/src/daw_mcp/git_mcp/server.py`
        - `packages/daw-mcp/src/daw_mcp/graph_memory/__init__.py`
        - `packages/daw-mcp/src/daw_mcp/graph_memory/server.py`
        - `packages/daw-mcp/tests/__init__.py`
    -   *Verification Commands*:
        ```bash
        cd packages/daw-mcp && poetry install
        cd packages/daw-mcp && poetry run pytest tests/
        # Test MCP server starts (implementation-specific)
        ```

-   **Story 12.6**: [Shared] Rename daw-shared to daw-protocol.
    -   *AC*: `packages/daw-shared/` renamed to `packages/daw-protocol/`. All imports across codebase updated. Contains: Pydantic models, Zod schemas, shared TypeScript types. No import errors.
    -   *Task Ref*: REFACTOR-006
    -   *Architecture Ref*: 02_project_structure.md
    -   *Dependencies*: REFACTOR-001
    -   *Implementation Steps*:
        1. Rename directory: `mv packages/daw-shared packages/daw-protocol`
        2. Update package configuration:
           - If Python: Update `pyproject.toml` name to `daw-protocol`
           - If TypeScript: Update `package.json` name to `@daw/protocol`
        3. Search entire codebase for `daw-shared` imports:
           ```bash
           grep -r "daw-shared" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.json"
           ```
        4. Replace all occurrences:
           - Python: `from daw_shared` → `from daw_protocol`
           - TypeScript: `@daw/shared` or `daw-shared` → `@daw/protocol`
           - package.json dependencies
        5. Update `pnpm-workspace.yaml` if it references daw-shared
        6. Run `pnpm install` at root to update workspace
        7. Run full test suite to catch any missed imports:
           ```bash
           cd packages/daw-agents && poetry run pytest
           cd apps/web && pnpm typecheck
           cd apps/server && poetry run pytest
           ```
    -   *Files to Modify*:
        - `packages/daw-protocol/package.json` or `pyproject.toml` (name field)
        - All files importing from daw-shared (search and replace)
        - `pnpm-workspace.yaml` (if references daw-shared)
        - Any `requirements.txt` or `pyproject.toml` with daw-shared dependency
    -   *Verification Commands*:
        ```bash
        # Ensure no references to old name remain
        grep -r "daw-shared" --include="*.py" --include="*.ts" --include="*.json" | wc -l  # should be 0

        # Full test suite
        pnpm install
        cd packages/daw-agents && poetry run pytest
        cd apps/web && pnpm typecheck
        ```

-   **Story 12.7**: [Testing] Comprehensive E2E validation post-refactor.
    -   *AC*: All unit tests pass (pytest, jest). All integration tests pass. Docker Compose builds successfully. Full system starts: frontend connects to backend, backend connects to Neo4j/Redis, agents execute successfully. Manual smoke test of critical flows: auth, chat, agent trace.
    -   *Task Ref*: REFACTOR-007
    -   *Architecture Ref*: 02_project_structure.md
    -   *Dependencies*: ALL previous REFACTOR tasks (REFACTOR-001 through REFACTOR-006)
    -   *BLOCKING*: This story MUST pass before Epic 12 is considered complete.
    -   *Implementation Steps*:
        1. **Unit Tests (Python)**:
           ```bash
           cd packages/daw-agents && poetry run pytest tests/ -v
           cd packages/daw-mcp && poetry run pytest tests/ -v
           cd apps/server && poetry run pytest tests/ -v
           ```
           All must pass with 0 failures.

        2. **Unit Tests (TypeScript)**:
           ```bash
           cd apps/web && pnpm test
           ```
           All must pass.

        3. **Type Checking**:
           ```bash
           cd apps/web && pnpm typecheck  # 0 errors
           cd packages/daw-agents && poetry run mypy src/  # 0 errors (if mypy configured)
           ```

        4. **Linting**:
           ```bash
           cd packages/daw-agents && poetry run ruff check src/
           cd apps/server && poetry run ruff check src/
           cd apps/web && pnpm lint
           ```
           0 errors required.

        5. **Docker Build**:
           ```bash
           docker-compose build
           ```
           Must complete without errors.

        6. **Full System Startup**:
           ```bash
           docker-compose up -d
           sleep 30  # wait for services

           # Check all services healthy
           docker-compose ps  # all should be "Up"
           ```

        7. **Connectivity Tests**:
           ```bash
           # Frontend responds
           curl -f http://localhost:3000

           # Backend responds
           curl -f http://localhost:8000/health

           # Neo4j responds (if exposed)
           curl -f http://localhost:7474

           # Redis responds
           docker-compose exec redis redis-cli ping  # PONG
           ```

        8. **Smoke Tests** (manual or scripted):
           - [ ] User can access sign-in page
           - [ ] Auth flow works (sign in/out)
           - [ ] Chat interface loads
           - [ ] Agent trace component renders
           - [ ] API endpoints respond with valid JSON

        9. **Integration Verification**:
           - [ ] Frontend successfully calls backend API
           - [ ] Backend successfully connects to Neo4j
           - [ ] Backend successfully connects to Redis
           - [ ] Celery workers can be started

        10. **Coverage Check**:
            ```bash
            cd packages/daw-agents && poetry run pytest --cov=daw_agents --cov-report=term-missing
            ```
            Must be >= 80% on new code.

    -   *Success Criteria Checklist*:
        - [ ] `pytest` (all packages): 0 failures
        - [ ] `pnpm test` (apps/web): 0 failures
        - [ ] `pnpm typecheck` (apps/web): 0 errors
        - [ ] `ruff check` (Python): 0 errors
        - [ ] `pnpm lint` (TypeScript): 0 errors
        - [ ] `docker-compose build`: succeeds
        - [ ] `docker-compose up`: all services healthy
        - [ ] Frontend accessible at localhost:3000
        - [ ] Backend accessible at localhost:8000
        - [ ] All smoke tests pass

    -   *If ANY check fails*:
        1. Document the failure in PROGRESS.md
        2. Create follow-up task to fix the issue
        3. Do NOT mark Epic 12 as complete
        4. Re-run REFACTOR-007 after fixes

**Execution Strategy**:
1. **Wave 1**: REFACTOR-001 (create structure) - must complete first
2. **Wave 2**: REFACTOR-002, 003, 005, 006 (parallel - all depend only on 001)
3. **Wave 3**: REFACTOR-004 (depends on 003 completing)
4. **Wave 4**: REFACTOR-007 (E2E validation - depends on all above)

**Rollback Strategy**:
- All work done on a feature branch: `git checkout -b epic-12-architecture-refactor`
- Each story committed separately with clear messages
- If REFACTOR-007 fails, branch can be abandoned
- Only merge to main after REFACTOR-007 passes all checks
