# Definition of Done & Success Metrics by Story

**Document Version**: 1.0
**Created**: 2025-12-30
**Purpose**: Provide measurable completion criteria and success metrics for every story in the DAW (Deterministic Agentic Workbench) project.

---

## MVP Definition of Done (Global Reference)

Before individual story completion, the MVP must achieve:
- [ ] User can login (Clerk)
- [ ] User can chat with "Planner" to create a PRD
- [ ] "Executor" can generate a single Python file with a passing test in E2B

---

## Epic 1: Workbench Core (The "Kernel")

### Story 1.1: [Backend] Set up FastAPI foundation with LangGraph integration
**Task Ref**: CORE-001, CORE-002

**Definition of Done**:
- [ ] `pyproject.toml` created with all required dependencies (fastapi, uvicorn, langgraph, pydantic)
- [ ] FastAPI application starts without errors on `uvicorn main:app`
- [ ] `GET /health` endpoint returns HTTP 200 OK
- [ ] LangGraph StateGraph is initialized and importable
- [ ] 0 lint errors (Ruff with strict config)
- [ ] 0 type errors (mypy or pyright)
- [ ] Unit tests for health endpoint exist and pass
- [ ] Test coverage >= 80% for new code
- [ ] API documentation auto-generated at `/docs`
- [ ] Code reviewed and approved

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Server startup time | < 5 seconds | Time from `uvicorn` start to first 200 OK response |
| `/health` response time (p95) | < 50ms | `pytest-benchmark` or `ab -n 1000` |
| Memory usage at idle | < 100MB | `ps` or `docker stats` |
| StateGraph initialization | < 500ms | Instrumented timer in test |
| Test coverage | >= 80% | `pytest-cov` report |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** the backend is started, **When** `GET /health` is called, **Then** HTTP 200 is returned with `{"status": "healthy", "version": "0.1.0"}`
- **Given** LangGraph is initialized, **When** StateGraph is inspected, **Then** it contains at least one node definition
- **Given** the server is running, **When** `/docs` is accessed, **Then** OpenAPI documentation is rendered
- **Given** invalid JSON is sent to any endpoint, **When** the request is processed, **Then** HTTP 422 is returned with validation errors

---

### Story 1.2: [Auth] Integrate Clerk for User Authentication
**Task Ref**: AUTH-001, AUTH-002

**Definition of Done**:
- [ ] Clerk SDK installed and configured (`clerk-backend-api`)
- [ ] Environment variables for Clerk API keys are documented and validated at startup
- [ ] FastAPI middleware validates JWTs on protected routes
- [ ] Dashboard route (`/dashboard/*`) returns 401 without valid JWT
- [ ] Dashboard route returns 200 with valid JWT
- [ ] User context (user_id, email) is available in request state
- [ ] Unit tests mock Clerk and verify auth flow
- [ ] Integration test with real Clerk tokens passes
- [ ] No secrets committed to repository (verified by secret scanner)
- [ ] Test coverage >= 85% for auth module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| JWT validation time | < 10ms | Instrumented middleware timer |
| Auth middleware overhead | < 5ms per request | Before/after timing comparison |
| Invalid token rejection rate | 100% | Test suite with expired/malformed tokens |
| Token cache hit rate | > 90% | Cache instrumentation after warmup |
| Auth failure response time | < 20ms | Benchmark on 401 responses |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** no Authorization header is provided, **When** accessing `/dashboard/projects`, **Then** HTTP 401 is returned with `{"detail": "Missing authentication"}`
- **Given** an expired JWT is provided, **When** accessing a protected route, **Then** HTTP 401 is returned with `{"detail": "Token expired"}`
- **Given** a valid JWT is provided, **When** accessing `/dashboard/projects`, **Then** HTTP 200 is returned and `request.state.user_id` is populated
- **Given** a JWT with invalid signature is provided, **When** accessing a protected route, **Then** HTTP 401 is returned with `{"detail": "Invalid token"}`

---

### Story 1.3: [Memory] Implement Neo4j connectivity
**Task Ref**: DB-001, CORE-006

**Definition of Done**:
- [ ] Neo4j driver installed (`neo4j` Python package)
- [ ] Connection pool configured with health checks
- [ ] Can create a "Project Node" with properties (id, name, created_at, user_id)
- [ ] Can read a "Project Node" by ID
- [ ] Context Compaction query implemented (summarize conversation history)
- [ ] Connection retry logic with exponential backoff
- [ ] Unit tests with in-memory Neo4j or testcontainers
- [ ] Integration test verifies CRUD operations
- [ ] Test coverage >= 80% for memory module
- [ ] Database indexes created for common queries

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Connection establishment | < 2 seconds | Timer from driver init to first query |
| Write latency (p95) | < 100ms | Benchmark with 100 Project Node writes |
| Read latency (p95) | < 50ms | Benchmark with 100 Project Node reads |
| Context Compaction query time | < 500ms | Benchmark with 1000-message history |
| Connection pool utilization | > 70% under load | Pool instrumentation |
| Failed connection recovery | < 5 seconds | Test with simulated network failure |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** Neo4j is running, **When** creating a Project Node with `{"name": "Test", "user_id": "123"}`, **Then** a node ID is returned and the node is queryable
- **Given** a Project Node exists, **When** `GET /projects/{id}` is called, **Then** the full node properties are returned
- **Given** 100 conversation messages exist for a project, **When** Context Compaction is invoked, **Then** a summarized context < 4000 tokens is returned
- **Given** Neo4j is temporarily unavailable, **When** a query is attempted, **Then** the system retries 3 times before returning 503

---

### Story 1.4: [MCP] Configure generic MCP Client and default Servers (git, filesystem)
**Task Ref**: CORE-003, INFRA-001

**Definition of Done**:
- [ ] MCP Client library installed and configured
- [ ] Git MCP server can execute `git status` and return parsed output
- [ ] Filesystem MCP server can execute `ls` and return directory listing
- [ ] Security allowlist configured (only permitted commands)
- [ ] Blocked commands (rm -rf, sudo, etc.) return 403
- [ ] Tool call audit logging implemented
- [ ] Unit tests for MCP client wrapper
- [ ] Integration tests with real MCP servers
- [ ] Test coverage >= 80% for MCP module
- [ ] MCP server health checks active

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| `git status` execution time | < 2 seconds | Timer from call to response |
| `ls` execution time | < 500ms | Timer from call to response |
| Blocked command rejection rate | 100% | Test suite with 20+ blocked patterns |
| Audit log write success rate | 100% | Verify all calls logged |
| MCP server startup time | < 3 seconds | Timer from spawn to ready |
| Tool call overhead | < 50ms | Compare direct vs. MCP execution |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** a Git repository exists, **When** `git status` is called via MCP, **Then** the working directory status is returned as structured data
- **Given** a directory exists, **When** `ls` is called via MCP, **Then** file/folder names and metadata are returned
- **Given** a command `rm -rf /` is attempted, **When** MCP processes the request, **Then** HTTP 403 is returned with `{"error": "Command blocked by security policy"}`
- **Given** any MCP tool is called, **When** the call completes, **Then** an audit log entry exists with timestamp, agent_id, tool, action, and result

---

## Epic 2: The Planner Agent (Spec-Driven Dev)

### Story 2.1: [AI] Implement "Senior PM" Persona prompt chain
**Task Ref**: PLANNER-001

**Definition of Done**:
- [ ] Prompt template for "Senior PM" persona stored in `packages/daw-agents/planner/prompts/senior_pm_v1.0.yaml`
- [ ] Agent asks minimum 3 clarifying questions before accepting requirements
- [ ] Clarifying questions are relevant to the input (not generic)
- [ ] Conversation state persisted between turns
- [ ] Prompt includes validation checklist for self-correction
- [ ] Unit tests verify question generation
- [ ] Integration test with mock LLM verifies flow
- [ ] Test coverage >= 85% for planner module
- [ ] Prompt versioning documented

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Clarifying questions asked | >= 3 | Count in conversation log |
| Question relevance score | >= 4.0/5.0 | Human evaluation rubric (sample 10 conversations) |
| Time to first question | < 5 seconds | Timer from user input to response |
| Conversation coherence | >= 90% | LLM-as-judge evaluation |
| Token usage per planning session | < 5000 tokens | Helicone tracking |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** user provides vague input "build me an app", **When** the Planner processes it, **Then** at least 3 clarifying questions are returned before any PRD generation
- **Given** user provides "build a todo app with auth", **When** Planner asks questions, **Then** questions relate to authentication method, data storage, and UI requirements
- **Given** conversation has 5 turns, **When** checking state, **Then** all previous turns are accessible and coherent
- **Given** user answers all clarifying questions, **When** requirements are confirmed, **Then** a structured summary is presented for approval

---

### Story 2.2: [Workflow] Implement the "Taskmaster" loop
**Task Ref**: PLANNER-001, PLANNER-002

**Definition of Done**:
- [ ] Conversation history persisted to Neo4j with project linkage
- [ ] "Roundtable" personas (CTO, UX, Security) implemented
- [ ] Each persona provides distinct critique perspective
- [ ] Roundtable critique occurs before PRD finalization
- [ ] State machine enforces Taskmaster flow (Interview -> Roundtable -> Refinement -> Approval)
- [ ] Unit tests for each state transition
- [ ] Integration test verifies full loop
- [ ] Test coverage >= 80% for workflow module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Conversation persistence success rate | 100% | Verify all turns saved to Neo4j |
| Roundtable personas engaged | 3 per session | Count distinct persona responses |
| Critique coverage | 100% of PRD sections | Check each section has feedback |
| State transition correctness | 100% | FSM validation tests |
| Full loop completion time | < 10 minutes | End-to-end timer |
| User satisfaction with refinements | >= 4.0/5.0 | Post-session survey |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** a planning session is active, **When** checking Neo4j, **Then** all conversation turns are persisted with project_id linkage
- **Given** user requirements are gathered, **When** Roundtable is invoked, **Then** CTO, UX, and Security personas each provide at least one critique
- **Given** CTO persona is invoked, **When** critiquing a PRD, **Then** feedback focuses on architecture and scalability
- **Given** Roundtable critiques are provided, **When** user reviews, **Then** original requirements are refined to address concerns

---

### Story 2.3: [Output] Implement `generate_prd` Tool
**Task Ref**: PLANNER-001

**Definition of Done**:
- [ ] `generate_prd` tool creates valid Markdown file
- [ ] PRD written to `docs/` folder of target project
- [ ] PRD includes: Title, Overview, User Stories, Technical Specs, Acceptance Criteria, NFRs
- [ ] PRD follows template structure from `templates/prd_template.md`
- [ ] Markdown linting passes (markdownlint)
- [ ] File creation logged with full path
- [ ] Unit tests verify PRD structure
- [ ] Integration test verifies file creation
- [ ] Test coverage >= 85% for PRD generator

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| PRD generation time | < 30 seconds | Timer from trigger to file write |
| PRD structure validity | 100% | Schema validation (all required sections present) |
| Markdown lint errors | 0 | `markdownlint` check |
| PRD character count | 2000-10000 | Character count of output |
| User stories count | >= 3 | Parse and count in output |
| Acceptance criteria per story | >= 2 | Parse and count in output |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** planning conversation is complete, **When** `generate_prd` is invoked, **Then** a file `docs/prd-{timestamp}.md` is created
- **Given** PRD is generated, **When** parsing the file, **Then** sections for Overview, User Stories, Tech Specs, and Acceptance Criteria exist
- **Given** PRD is generated, **When** running `markdownlint docs/prd-*.md`, **Then** 0 errors are reported
- **Given** PRD is generated for "todo app", **When** reading User Stories section, **Then** stories relate to todo functionality (create, read, update, delete)

---

### Story 2.4: [AI] Implement Complexity Analysis Engine
**Task Ref**: COMPLEXITY-001
**Gap Ref**: Gap 2 (Research Paper Lines 105-107)

**Definition of Done**:
- [ ] Complexity analysis runs BEFORE task generation
- [ ] Output file `complexity_analysis.json` created with required fields
- [ ] Feature cognitive load scores (1-10 scale) calculated
- [ ] Dependency graph with risk ratings generated
- [ ] Recommended model tier per task determined
- [ ] Architectural bottleneck warnings included
- [ ] Analysis blocks task generation if it fails
- [ ] Unit tests for each scoring algorithm
- [ ] Integration test verifies blocking behavior
- [ ] Test coverage >= 80% for complexity module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Analysis completion time | < 60 seconds | Timer from trigger to JSON write |
| Cognitive load score accuracy | >= 80% correlation | Compare to expert ratings on 20 samples |
| Dependency detection completeness | >= 90% | Manual review of 10 PRDs |
| Risk rating accuracy | >= 75% | Compare to actual implementation difficulty |
| Model tier recommendation accuracy | >= 85% | Track actual model used vs. recommended |
| Blocking behavior reliability | 100% | Test with failing analysis scenarios |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** a PRD exists, **When** complexity analysis is triggered, **Then** `complexity_analysis.json` is created before any tasks are generated
- **Given** PRD has 5 features, **When** analysis completes, **Then** each feature has a cognitive load score between 1-10
- **Given** PRD includes "auth" and "database", **When** dependency graph is generated, **Then** auth depends on database with "medium" risk rating
- **Given** a feature has cognitive load >= 8, **When** model tier is recommended, **Then** "o1" or "opus" is suggested (not haiku/sonnet)
- **Given** complexity analysis fails validation, **When** task generation is attempted, **Then** it is blocked with error message

---

## Epic 3: The Executor Agent (Test-Driven Dev)

### Story 3.1: [Sandbox] Integrate E2B SDK
**Task Ref**: CORE-004

**Definition of Done**:
- [ ] E2B SDK installed (`e2b` package)
- [ ] Can spin up a sandbox programmatically
- [ ] Can execute Python script and capture stdout
- [ ] Can capture stderr separately
- [ ] Sandbox timeout configured (default 5 minutes)
- [ ] Resource limits applied (CPU, RAM)
- [ ] Sandbox cleanup on completion/error
- [ ] Unit tests mock E2B for fast testing
- [ ] Integration test verifies real sandbox execution
- [ ] Test coverage >= 80% for sandbox module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Sandbox spin-up time | < 10 seconds | Timer from request to ready |
| Script execution latency overhead | < 500ms | Compare to local execution |
| Stdout capture reliability | 100% | Test with 50 different outputs |
| Stderr capture reliability | 100% | Test with error scenarios |
| Sandbox cleanup success rate | 100% | Verify no orphaned sandboxes |
| Resource limit enforcement | 100% | Test with resource-intensive scripts |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** E2B credentials are configured, **When** `create_sandbox()` is called, **Then** a sandbox ID is returned within 10 seconds
- **Given** a sandbox is running, **When** `print("hello")` Python script is executed, **Then** stdout contains "hello"
- **Given** a sandbox is running, **When** `raise Exception("error")` is executed, **Then** stderr contains "error"
- **Given** a sandbox completes execution, **When** cleanup is invoked, **Then** the sandbox is destroyed and resources freed
- **Given** a script runs for > 5 minutes, **When** timeout is reached, **Then** sandbox is terminated with timeout error

---

### Story 3.2: [Workflow] Implement "Red Phase" constraint
**Task Ref**: CORE-005, EXECUTOR-001

**Definition of Done**:
- [ ] Agent cannot create files in `src/` until `tests/` file exists
- [ ] System verifies test file fails before allowing implementation
- [ ] "Red Phase" state enforced in LangGraph workflow
- [ ] Clear error message when constraint violated
- [ ] Constraint bypass impossible without code change
- [ ] Unit tests verify constraint enforcement
- [ ] Integration test verifies TDD flow
- [ ] Test coverage >= 90% for TDD module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Constraint violation prevention | 100% | Attempt 20 bypass scenarios |
| Test file creation detection | < 500ms | Timer from write to detection |
| Test failure verification | < 5 seconds | Timer from execution to result |
| False positive rate | 0% | Test with valid TDD flows |
| False negative rate | 0% | Test with invalid flows |
| Developer feedback clarity | >= 4.5/5.0 | Survey on error messages |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** no test file exists, **When** agent attempts to create `src/main.py`, **Then** the operation is blocked with "Red Phase violation: test must exist first"
- **Given** test file exists but passes, **When** agent attempts implementation, **Then** operation is blocked with "Red Phase violation: test must fail first"
- **Given** test file `tests/test_main.py` exists and fails, **When** agent creates `src/main.py`, **Then** operation is allowed
- **Given** Red Phase is active, **When** workflow state is inspected, **Then** `current_phase` is "red"

---

### Story 3.3: [Workflow] Implement "Green Phase" & "Healer Loop"
**Task Ref**: EXECUTOR-001, OPS-002

**Definition of Done**:
- [ ] Agent writes minimal code to pass failing test
- [ ] Auto-retry up to 3 times if tests fail
- [ ] Healer Agent uses RAG to diagnose errors
- [ ] Error patterns stored in knowledge base for future use
- [ ] Retry count and outcomes logged
- [ ] Human escalation after 3 failures
- [ ] Unit tests for Green Phase transitions
- [ ] Integration test for Healer Loop
- [ ] Test coverage >= 85% for executor module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| First-attempt pass rate | >= 70% | Track across 100 tasks |
| Pass rate after 3 retries | >= 95% | Track across 100 tasks |
| Average retries to success | < 1.5 | Calculate mean |
| Healer RAG relevance score | >= 80% | Evaluate diagnosis accuracy |
| Error knowledge base growth | +10 patterns/week | Count new entries |
| Human escalation rate | < 5% | Track escalations / total tasks |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** a failing test exists, **When** Green Phase begins, **Then** agent generates minimal implementation code
- **Given** implementation fails tests, **When** retry #1 occurs, **Then** Healer Agent provides diagnostic context
- **Given** 3 retries have failed, **When** retry limit is reached, **Then** task is escalated to human with full context
- **Given** a common error pattern is diagnosed, **When** similar error occurs later, **Then** Healer retrieves relevant solution from RAG
- **Given** implementation passes tests, **When** Green Phase completes, **Then** workflow transitions to "refactor" or "done" state

---

## Epic 4: Observability & Monitoring

### Story 4.1: [Ops] Integrate Helicone proxy
**Task Ref**: OPS-001

**Definition of Done**:
- [ ] All OpenAI API calls routed through `oai.helicone.ai`
- [ ] Helicone API key configured securely
- [ ] Cost tracking visible in Helicone dashboard
- [ ] Request metadata (user_id, project_id, agent_type) attached
- [ ] Caching enabled with configurable TTL
- [ ] Unit tests verify proxy configuration
- [ ] Integration test verifies cost tracking
- [ ] Test coverage >= 80% for observability module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Proxy routing success rate | 100% | Verify all calls in Helicone logs |
| Metadata attachment rate | 100% | Check metadata fields in dashboard |
| Cache hit rate | >= 30% | Helicone cache metrics |
| Proxy latency overhead | < 50ms | Compare direct vs. proxied calls |
| Cost tracking accuracy | 100% | Compare Helicone to OpenAI billing |
| Dashboard data freshness | < 1 minute | Time from call to dashboard update |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** Helicone is configured, **When** any OpenAI call is made, **Then** it appears in Helicone dashboard within 60 seconds
- **Given** a call is made with `user_id="123"`, **When** checking Helicone, **Then** the request shows user_id metadata
- **Given** caching is enabled, **When** identical prompt is sent twice, **Then** second call shows cache hit
- **Given** 100 API calls are made, **When** checking Helicone, **Then** total cost matches sum of individual costs

---

### Story 4.2: [UI] Build "Agent Trace" view in Next.js
**Task Ref**: FRONTEND-001, FRONTEND-002

**Definition of Done**:
- [ ] "Agent Trace" component renders in dashboard
- [ ] Live "thought bubble" shows agent reasoning in real-time
- [ ] Streaming updates via WebSocket or SSE
- [ ] Trace persisted for replay after completion
- [ ] Expandable/collapsible trace sections
- [ ] Unit tests for React components
- [ ] E2E test verifies trace rendering
- [ ] Test coverage >= 80% for frontend module
- [ ] Accessibility score >= 90 (Lighthouse)

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Time to first trace update | < 500ms | Timer from agent start to UI update |
| Update latency | < 200ms | Measure stream delay |
| Trace rendering performance | 60 fps | Chrome DevTools Performance |
| UI responsiveness during streaming | No jank | Lighthouse performance audit |
| Trace replay accuracy | 100% | Compare live vs. replayed |
| Mobile responsiveness | 100% | Test on 3 viewport sizes |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** an agent is running, **When** viewing the dashboard, **Then** the Agent Trace component shows live updates
- **Given** agent has 5 reasoning steps, **When** trace is displayed, **Then** all 5 steps are visible with timestamps
- **Given** trace is streaming, **When** user collapses a section, **Then** new updates continue to stream
- **Given** agent has completed, **When** trace is replayed, **Then** timing and content match original execution

---

### Story 4.3: [Ops] Implement Drift Detection Metrics
**Task Ref**: DRIFT-001
**Gap Ref**: Gap 7 (Research Paper Lines 218-223)

**Definition of Done**:
- [ ] Tool Usage Frequency tracked per task type
- [ ] Reasoning Step Count monitored per session
- [ ] Context Window Utilization percentage calculated
- [ ] Retry Rate tracked per agent
- [ ] Token Cost per Task computed
- [ ] Baselines established from historical data
- [ ] Deviation calculation from baseline implemented
- [ ] Metrics stored in time-series format
- [ ] Unit tests for each metric calculator
- [ ] Integration test verifies metric collection
- [ ] Test coverage >= 85% for drift module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Metric collection latency | < 100ms | Timer from event to storage |
| Metric accuracy | 100% | Validate against manual counts |
| Baseline calculation stability | < 5% variance | Measure over 7 days |
| Deviation detection sensitivity | Detect +25% change | Inject synthetic drift |
| False positive rate | < 5% | Monitor alerts over 30 days |
| Storage efficiency | < 1KB per task | Measure storage per 1000 tasks |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** an agent executes 10 tool calls, **When** metrics are queried, **Then** Tool Usage Frequency shows 10 calls for that session
- **Given** context window is 80% full, **When** utilization is calculated, **Then** metric shows 80%
- **Given** baseline retry rate is 0.5, **When** current rate is 1.5, **Then** deviation shows +200%
- **Given** 50% tool usage increase occurs, **When** alert threshold is checked, **Then** warning alert is generated

---

### Story 4.4: [Ops] Implement Drift Detection Alerting and Actions
**Task Ref**: DRIFT-002
**Gap Ref**: Gap 7 (Research Paper Lines 218-223)

**Definition of Done**:
- [ ] Integration with Helicone/Datadog for alerts
- [ ] Slack notifications for warnings
- [ ] Linear ticket creation for critical alerts
- [ ] Weekly drift reports auto-generated
- [ ] Graduated response implemented (Mild -> Log, Moderate -> Compaction, Severe -> Pause)
- [ ] Alert thresholds configurable
- [ ] Unit tests for alert logic
- [ ] Integration test with mock notification services
- [ ] Test coverage >= 80% for alerting module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Alert delivery latency | < 30 seconds | Timer from detection to notification |
| Alert delivery success rate | >= 99% | Track failed deliveries |
| Action execution success rate | 100% | Verify actions completed |
| Weekly report generation | 100% on schedule | Track report creation |
| False alert rate | < 3% | Review alerts over 30 days |
| Mean time to acknowledgment | < 15 minutes | Track Slack reaction time |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** tool usage deviation > 50%, **When** alert is triggered, **Then** Slack message is sent within 30 seconds
- **Given** step count deviation > 100%, **When** alert is triggered, **Then** agent is paused and Linear ticket created
- **Given** context utilization > 90%, **When** threshold is exceeded, **Then** context compaction is auto-triggered
- **Given** it is Sunday 9am, **When** weekly report job runs, **Then** drift report email is sent to stakeholders

---

## Epic 5: Validator Agent & Quality Assurance

### Story 5.1: [AI] Implement Validator Agent LangGraph Workflow
**Task Ref**: VALIDATOR-001
**Gap Ref**: Gap 1 (Research Paper Lines 55-61)

**Definition of Done**:
- [ ] Validator Agent architecturally separate from E2B sandbox
- [ ] Runs on DIFFERENT model than Executor (configurable)
- [ ] LangGraph states implemented: [run_tests, security_scan, policy_check, generate_report, route_decision]
- [ ] State transitions documented and tested
- [ ] Model selection configurable via environment
- [ ] Unit tests for each state
- [ ] Integration test verifies full workflow
- [ ] Test coverage >= 90% for validator module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Workflow completion rate | >= 99% | Track completed vs. started |
| State transition correctness | 100% | FSM validation tests |
| Model diversity enforcement | 100% | Verify different models used |
| Validation latency (full workflow) | < 60 seconds | Timer from start to report |
| Report generation success rate | 100% | Track report creation |
| Architectural isolation verification | 100% | Network isolation tests |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** Executor uses Claude, **When** Validator runs, **Then** GPT-4o (or configured alternative) is used
- **Given** code is submitted for validation, **When** workflow starts, **Then** states execute in order: run_tests -> security_scan -> policy_check -> generate_report -> route_decision
- **Given** all validations pass, **When** route_decision executes, **Then** result is "approved" with confidence score
- **Given** Validator Agent is running, **When** network isolation is checked, **Then** it cannot directly access E2B sandbox

---

### Story 5.2: [AI] Implement Validator Test Execution and Interpretation
**Task Ref**: VALIDATOR-001
**Gap Ref**: Gap 1 (Research Paper Lines 55-61)

**Definition of Done**:
- [ ] Validator executes test suites and captures results
- [ ] Intelligent interpretation of failures (not just pass/fail)
- [ ] Root cause analysis for failing tests
- [ ] Actionable improvement suggestions generated
- [ ] Test flakiness detection implemented
- [ ] Unit tests for interpretation logic
- [ ] Integration test with sample test suites
- [ ] Test coverage >= 85% for interpretation module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Test result interpretation accuracy | >= 90% | Human review of 50 interpretations |
| Root cause identification accuracy | >= 80% | Compare to actual fixes |
| Suggestion usefulness score | >= 4.0/5.0 | Developer survey |
| Flaky test detection rate | >= 85% | Compare to manual analysis |
| Interpretation latency | < 10 seconds per test | Timer per test result |
| False root cause rate | < 10% | Track incorrect diagnoses |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** a test fails with AssertionError, **When** Validator interprets, **Then** specific assertion failure and expected vs. actual values are reported
- **Given** multiple tests fail with same root cause, **When** analysis completes, **Then** common root cause is identified
- **Given** test interpretation is complete, **When** suggestions are generated, **Then** at least one actionable code change is recommended
- **Given** a test fails intermittently, **When** flakiness analysis runs, **Then** test is flagged as potentially flaky with evidence

---

### Story 5.3: [Security] Implement Validator SAST/SCA Integration
**Task Ref**: VALIDATOR-001
**Gap Ref**: Gap 1 (Research Paper Lines 55-61)

**Definition of Done**:
- [ ] SAST tool integrated (Snyk, SonarQube, or equivalent)
- [ ] SCA vulnerability scanning for all dependencies
- [ ] Critical/High findings block validation
- [ ] Medium/Low findings logged as warnings
- [ ] Results formatted for actionable output
- [ ] False positive management workflow
- [ ] Unit tests for SAST/SCA integration
- [ ] Integration test with vulnerable code samples
- [ ] Test coverage >= 80% for security module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| SAST scan completion rate | 100% | Track completed scans |
| SCA scan completion rate | 100% | Track completed scans |
| Critical finding detection rate | 100% | Test with known vulnerabilities |
| Scan latency | < 120 seconds | Timer from trigger to results |
| False positive rate | < 10% | Manual review of findings |
| Actionable recommendation rate | >= 90% | Track fixable findings |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** code contains SQL injection vulnerability, **When** SAST runs, **Then** critical finding is reported with line number and fix suggestion
- **Given** dependency has known CVE, **When** SCA runs, **Then** vulnerability is reported with severity and remediation path
- **Given** SAST finds 1 critical issue, **When** validation completes, **Then** overall result is "blocked" with critical finding details
- **Given** SAST finds only medium issues, **When** validation completes, **Then** overall result is "passed with warnings"

---

### Story 5.4: [AI] Implement Multi-Model Validation Ensemble
**Task Ref**: VALIDATOR-002
**Gap Ref**: Gap 1 (Research Paper Lines 55-61)

**Definition of Done**:
- [ ] 2+ models configured for critical validations
- [ ] Voting/consensus mechanism implemented
- [ ] Configurable which validations require ensemble
- [ ] Disagreement handling with escalation
- [ ] Ensemble results logged with individual model outputs
- [ ] Unit tests for consensus logic
- [ ] Integration test with multi-model setup
- [ ] Test coverage >= 85% for ensemble module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Ensemble agreement rate | >= 90% | Track consensus vs. disagreement |
| Ensemble accuracy improvement | >= 10% vs. single model | Compare error rates |
| Ensemble latency overhead | < 2x single model | Timer comparison |
| Disagreement resolution success | >= 95% | Track resolved disagreements |
| Model diversity coverage | >= 2 providers | Count unique providers |
| Escalation rate | < 10% | Track human escalations |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** security validation is critical, **When** ensemble runs, **Then** GPT-4o and Claude both evaluate and vote
- **Given** both models agree "pass", **When** consensus is calculated, **Then** result is "pass" with high confidence
- **Given** models disagree (one pass, one fail), **When** disagreement handling runs, **Then** result is escalated for human review
- **Given** ensemble is configured for security only, **When** non-security validation runs, **Then** single model is used

---

### Story 5.5: [Workflow] Implement Validator Retry and Escalation Logic
**Task Ref**: VALIDATOR-001
**Gap Ref**: Gap 1 (Research Paper Lines 55-61)

**Definition of Done**:
- [ ] Fixable failures route back to Executor
- [ ] Maximum 3 retries enforced
- [ ] Critical/unfixable issues escalate to human
- [ ] Full context provided in escalation (code, errors, attempts)
- [ ] Escalation queue with priority
- [ ] Retry outcomes tracked for improvement
- [ ] Unit tests for retry logic
- [ ] Integration test for escalation flow
- [ ] Test coverage >= 85% for retry module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Retry success rate | >= 70% within 3 tries | Track retry outcomes |
| Escalation appropriateness | >= 95% | Human review of escalations |
| Context completeness in escalation | 100% | Check required fields present |
| Escalation response time | < 4 hours | Track time to human action |
| Retry loop detection | 100% | Test with infinite loop scenarios |
| Priority queue correctness | 100% | Verify ordering by severity |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** test failure is fixable (syntax error), **When** retry is triggered, **Then** code is sent back to Executor with error context
- **Given** 3 retries have failed, **When** limit is reached, **Then** task is escalated with all attempt details
- **Given** security critical finding, **When** issue is detected, **Then** immediate escalation occurs (no retry allowed)
- **Given** escalation is created, **When** human reviews, **Then** original code, all errors, and all fix attempts are visible

---

## Epic 6: MCP Security & Governance

### Story 6.1: [Security] Implement MCP Gateway OAuth 2.1 Authorization
**Task Ref**: MCP-SEC-001
**Gap Ref**: Gap 8 (Research Paper Lines 185-191)

**Definition of Done**:
- [ ] OAuth 2.1 with RFC 8707 Resource Indicators implemented
- [ ] Per-agent scoped tokens (database agent: SELECT only, etc.)
- [ ] Token TTL: 15 minutes for automated, 1 hour for interactive
- [ ] Token refresh mechanism implemented
- [ ] Invalid/expired tokens rejected with proper error codes
- [ ] Unit tests for token validation
- [ ] Integration test with OAuth flows
- [ ] Test coverage >= 90% for OAuth module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Token validation latency | < 10ms | Instrumented timer |
| Invalid token rejection rate | 100% | Test with 50 invalid scenarios |
| Token refresh success rate | >= 99% | Track refresh operations |
| Scope enforcement accuracy | 100% | Test scope violations |
| TTL enforcement accuracy | 100% | Test with expired tokens |
| OAuth flow completion rate | >= 99% | Track flow completions |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** database agent requests token, **When** token is issued, **Then** scope is limited to SELECT operations only
- **Given** token is 16 minutes old (automated), **When** used for MCP call, **Then** request is rejected with "token expired"
- **Given** executor agent token, **When** attempting DDL operation, **Then** request is rejected with "scope violation"
- **Given** valid token is about to expire, **When** refresh is requested, **Then** new token is issued with same scope

---

### Story 6.2: [Security] Implement RBAC for MCP Tools
**Task Ref**: MCP-SEC-002
**Gap Ref**: Gap 8 (Research Paper Lines 185-191)

**Definition of Done**:
- [ ] Role definitions stored in YAML configuration
- [ ] Planner: read-only operations (search, read_file, query_db SELECT)
- [ ] Executor: scoped writes (read_file, write_file, git_commit in project dir)
- [ ] Validator: no writes (run_tests, security_scan, lint)
- [ ] Healer: patch-only with approval (read_file, write_file patches)
- [ ] Role assignment verified at every tool call
- [ ] Unit tests for each role
- [ ] Integration test verifies role enforcement
- [ ] Test coverage >= 90% for RBAC module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Role enforcement accuracy | 100% | Test all role/action combinations |
| Permission check latency | < 5ms | Instrumented timer |
| Unauthorized action rejection rate | 100% | Test 100 unauthorized scenarios |
| Role configuration load time | < 100ms | Timer on YAML parse |
| Policy update propagation | < 5 seconds | Time from file change to enforcement |
| YAML validation success rate | 100% | Test with valid/invalid configs |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** Planner agent, **When** attempting `write_file`, **Then** operation is denied with "role violation: Planner cannot write"
- **Given** Executor agent, **When** writing to `/etc/passwd`, **Then** operation is denied with "path violation: outside project scope"
- **Given** Validator agent, **When** running `run_tests`, **Then** operation is allowed
- **Given** Healer agent, **When** writing a patch, **Then** operation requires human approval before execution

---

### Story 6.3: [Security] Implement MCP Audit Logging
**Task Ref**: MCP-SEC-003
**Gap Ref**: Gap 8 (Research Paper Lines 185-191)

**Definition of Done**:
- [ ] Every tool call logged with: timestamp, agent_id, user_id, tool, action, params, result
- [ ] Hash-chaining implemented for tamper resistance
- [ ] 7-year retention configured for SOC 2/ISO 27001
- [ ] Log rotation and archival automated
- [ ] Log integrity verification tool available
- [ ] Unit tests for log format
- [ ] Integration test verifies hash chain
- [ ] Test coverage >= 85% for audit module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Log capture rate | 100% | Compare calls to log entries |
| Log write latency | < 20ms | Instrumented timer |
| Hash chain integrity | 100% over 30 days | Verification tool check |
| Log storage efficiency | < 500 bytes per entry | Measure average entry size |
| Retention compliance | 7 years verified | Check oldest accessible log |
| Tamper detection rate | 100% | Test with modified logs |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** MCP tool call occurs, **When** audit log is checked, **Then** entry exists with all required fields (timestamp, agent_id, user_id, tool, action, params, result)
- **Given** 100 log entries exist, **When** hash chain is verified, **Then** all entries pass integrity check
- **Given** log entry is tampered with, **When** verification runs, **Then** tampering is detected and reported
- **Given** log is 7 years old, **When** retrieval is requested, **Then** log is accessible and readable

---

### Story 6.4: [Security] Implement Content Injection Prevention
**Task Ref**: MCP-SEC-004
**Gap Ref**: Gap 8 (Research Paper Lines 185-191)

**Definition of Done**:
- [ ] AI Prompt Shields active on all tool inputs
- [ ] JSON schema validation on all tool I/O
- [ ] Blocked patterns list: DROP, DELETE, rm -rf, sudo, eval(), exec()
- [ ] Malicious requests rejected at gateway with detailed error
- [ ] Pattern list configurable and updateable without deploy
- [ ] Unit tests for each blocked pattern
- [ ] Integration test with injection attempts
- [ ] Test coverage >= 95% for injection prevention module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Injection attack detection rate | 100% | Test with 100 known attack patterns |
| False positive rate | < 1% | Test with 1000 legitimate requests |
| Validation latency | < 10ms | Instrumented timer |
| Pattern list update time | < 5 seconds | Time from update to enforcement |
| Schema validation coverage | 100% of tools | Audit tool definitions |
| Attack vector coverage | OWASP Top 10 | Security audit |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** tool input contains `'; DROP TABLE users; --`, **When** processed, **Then** request is rejected with "injection attempt detected"
- **Given** tool input contains `rm -rf /`, **When** processed, **Then** request is rejected with "blocked command pattern"
- **Given** tool output does not match JSON schema, **When** validation runs, **Then** output is rejected with schema violation details
- **Given** legitimate query `SELECT * FROM users WHERE id=1`, **When** processed, **Then** request is allowed

---

## Epic 7: Prompt Template Governance

### Story 7.1: [DevOps] Establish Prompt Governance Structure
**Task Ref**: PROMPT-GOV-001
**Gap Ref**: Gap 3 (Research Paper Lines 113-118)

**Definition of Done**:
- [ ] All prompts stored in `packages/daw-agents/{agent}/prompts/`
- [ ] Semantic versioning applied (e.g., `prd_generator_v1.0.yaml`)
- [ ] Each prompt has: version, name, persona, system_prompt, validation_checklist, output_schema
- [ ] Prompt loader validates structure on load
- [ ] Version history tracked in git
- [ ] Unit tests for prompt loading
- [ ] Integration test verifies agent uses versioned prompts
- [ ] Test coverage >= 80% for prompt module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Prompt structure compliance | 100% | Validate all prompts against schema |
| Version tracking accuracy | 100% | Git log verification |
| Prompt load time | < 50ms | Instrumented timer |
| Schema validation coverage | 100% of prompts | Audit all prompt files |
| Prompt discoverability | 100% | Can list all prompts programmatically |
| Documentation completeness | 100% of prompts | Check required fields present |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** a prompt file exists, **When** parsed, **Then** it contains version, name, persona, system_prompt, validation_checklist, and output_schema fields
- **Given** prompt version is `v1.0`, **When** updated to `v1.1`, **Then** git history shows both versions
- **Given** prompt schema is invalid, **When** agent attempts to load, **Then** clear error message indicates missing fields
- **Given** planner agent starts, **When** prompt is loaded, **Then** correct versioned prompt from `packages/daw-agents/planner/prompts/` is used

---

### Story 7.2: [Testing] Implement Prompt Regression Testing Harness
**Task Ref**: PROMPT-GOV-002
**Gap Ref**: Gap 3 (Research Paper Lines 113-118)

**Definition of Done**:
- [ ] Golden input/output pairs stored in `tests/prompts/goldens/`
- [ ] CI runs regression tests on every prompt change
- [ ] Semantic similarity scoring with >= 85% threshold
- [ ] JSON schema validation for structured outputs
- [ ] Test report generated with similarity scores
- [ ] Regression detection alerts
- [ ] Unit tests for similarity scoring
- [ ] Integration test with prompt changes
- [ ] Test coverage >= 85% for regression module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Golden test coverage | >= 90% of prompts | Count prompts with goldens |
| Semantic similarity threshold | >= 85% | Embedding-based comparison |
| Regression detection accuracy | >= 95% | Compare to manual review |
| CI test execution time | < 5 minutes | Timer from trigger to result |
| False positive rate | < 5% | Track false regressions |
| Schema validation coverage | 100% of structured outputs | Audit output schemas |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** golden input/output pair exists, **When** prompt generates output, **Then** semantic similarity >= 85% to golden
- **Given** prompt is modified in PR, **When** CI runs, **Then** regression tests execute automatically
- **Given** output similarity is 80%, **When** below threshold, **Then** CI fails with detailed similarity report
- **Given** output is JSON, **When** schema validation runs, **Then** output matches defined schema or test fails

---

## Epic 8: Deployment & Policy-as-Code

### Story 8.1: [DevOps] Implement Policy-as-Code Deployment Gates
**Task Ref**: POLICY-001
**Gap Ref**: Gap 4 (Research Paper Lines 193-196)

**Definition of Done**:
- [ ] Gate 1 (Quality): Coverage >= 80% new, >= 70% total, strict mode, 0 lint errors
- [ ] Gate 2 (Security): 0 SAST critical, 0 SCA critical CVEs, 0 secrets detected
- [ ] Gate 3 (Performance): p95 < 500ms, bundle size < +10% from baseline
- [ ] Gate 4 (UAT): P0 journeys 100%, visual diff < 0.1%
- [ ] All gates configurable via YAML
- [ ] Gate bypass requires explicit approval
- [ ] Unit tests for each gate
- [ ] Integration test verifies gate enforcement
- [ ] Test coverage >= 90% for policy module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Gate evaluation accuracy | 100% | Test with pass/fail scenarios |
| Gate execution time | < 30 seconds per gate | Timer per gate |
| Deployment block rate for violations | 100% | Test policy violations |
| Configuration load time | < 100ms | Timer on YAML parse |
| Bypass audit trail completeness | 100% | Check required fields logged |
| False positive rate | < 2% | Track incorrect blocks |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** new code coverage is 75%, **When** Gate 1 evaluates, **Then** deployment is blocked with "coverage below 80% threshold"
- **Given** SAST finds 1 critical CVE, **When** Gate 2 evaluates, **Then** deployment is blocked with CVE details
- **Given** p95 latency is 600ms, **When** Gate 3 evaluates, **Then** deployment is blocked with "p95 > 500ms threshold"
- **Given** all gates pass, **When** deployment proceeds, **Then** deployment completes successfully

---

### Story 8.2: [DevOps] Implement Zero-Copy Fork for Database Migrations
**Task Ref**: POLICY-002
**Gap Ref**: Gap 4 (Research Paper Lines 193-196)

**Definition of Done**:
- [ ] Instant zero-copy fork creation implemented
- [ ] Migration applied to fork only
- [ ] Validation suite runs against fork
- [ ] If pass: apply to production
- [ ] If fail: discard fork with zero production impact
- [ ] Fork cleanup automated
- [ ] Unit tests for fork logic
- [ ] Integration test verifies migration flow
- [ ] Test coverage >= 85% for migration module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Fork creation time | < 60 seconds | Timer from request to ready |
| Fork accuracy | 100% data match | Compare fork to source |
| Migration validation success rate | >= 99% | Track validation outcomes |
| Production protection rate | 100% | Test failed migrations don't affect prod |
| Fork cleanup success rate | 100% | Verify no orphaned forks |
| Rollback capability | < 30 seconds | Timer for fork discard |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** production database exists, **When** fork is requested, **Then** zero-copy clone is created within 60 seconds
- **Given** migration is applied to fork, **When** validation fails, **Then** fork is discarded and production is unchanged
- **Given** migration validation passes, **When** approved, **Then** migration is applied to production
- **Given** fork exists for > 24 hours, **When** cleanup runs, **Then** orphaned fork is automatically deleted

---

## Epic 9: UAT Automation

### Story 9.1: [Testing] Implement UAT Agent with Playwright MCP
**Task Ref**: UAT-001
**Gap Ref**: Gap 5 (Research Paper Lines 235-237)

**Definition of Done**:
- [ ] UAT Agent uses Playwright MCP for browser automation
- [ ] Operates on accessibility snapshots (not screenshots)
- [ ] Supports Chromium, Firefox, WebKit browsers
- [ ] Executes Gherkin scenarios from PRD acceptance criteria
- [ ] Test results include traces and timing
- [ ] Unit tests for UAT agent logic
- [ ] Integration test verifies browser automation
- [ ] Test coverage >= 80% for UAT module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Browser automation success rate | >= 99% | Track completed vs. failed runs |
| Accessibility snapshot accuracy | >= 95% | Compare to manual inspection |
| Cross-browser consistency | >= 98% | Compare results across browsers |
| Scenario execution time | < 30 seconds per scenario | Timer per Gherkin scenario |
| Gherkin parsing accuracy | 100% | Test with 50 scenarios |
| Trace completeness | 100% of steps | Verify all steps traced |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** Gherkin scenario "User logs in", **When** UAT agent executes, **Then** all steps complete with pass/fail result
- **Given** UAT runs on Chromium, **When** same test runs on Firefox, **Then** results are consistent
- **Given** test completes, **When** trace is reviewed, **Then** each step has timestamp, screenshot, and accessibility state
- **Given** accessibility snapshot is taken, **When** analyzed, **Then** all interactive elements are identified

---

### Story 9.2: [Testing] Implement Persona-Based UAT Testing
**Task Ref**: UAT-002
**Gap Ref**: Gap 5 (Research Paper Lines 235-237)

**Definition of Done**:
- [ ] Personas defined in `uat/personas.yaml`
- [ ] Power User: desktop, fast network, keyboard shortcuts
- [ ] First-Time User: mobile, 3G throttled, help-seeking
- [ ] Accessibility User: screen reader, keyboard-only
- [ ] Persona modifies agent interaction behavior
- [ ] Unit tests for persona loading
- [ ] Integration test with each persona
- [ ] Test coverage >= 80% for persona module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Persona definition completeness | 100% | Schema validation |
| Behavior modification accuracy | 100% | Verify behavior per persona |
| Network throttling accuracy | Within 10% of target | Measure actual throughput |
| Keyboard navigation coverage | >= 90% of actions | Count keyboard vs. mouse |
| Screen reader compatibility | WCAG 2.1 AA | Automated accessibility scan |
| Persona switch time | < 5 seconds | Timer between persona changes |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** Power User persona, **When** test runs, **Then** keyboard shortcuts are used preferentially
- **Given** First-Time User persona, **When** test runs, **Then** network is throttled to 3G speeds
- **Given** Accessibility User persona, **When** test runs, **Then** only keyboard navigation is used (no mouse clicks)
- **Given** personas.yaml is loaded, **When** parsed, **Then** all 3 personas have required fields (viewport, network, interaction_style)

---

### Story 9.3: [Testing] Implement Visual Regression Testing
**Task Ref**: UAT-003
**Gap Ref**: Gap 5 (Research Paper Lines 235-237)

**Definition of Done**:
- [ ] AI-powered visual comparison (Applitools or equivalent)
- [ ] Threshold < 0.1% for critical UI components
- [ ] Automatic baseline updates for approved changes
- [ ] Visual diff report with highlighted differences
- [ ] Integration with CI/CD pipeline
- [ ] Unit tests for comparison logic
- [ ] Integration test with visual changes
- [ ] Test coverage >= 80% for visual module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Visual detection accuracy | >= 99% | Compare to manual review |
| False positive rate | < 2% | Track incorrect failures |
| Comparison time | < 5 seconds per screenshot | Timer per comparison |
| Baseline update success rate | 100% | Track update operations |
| Diff report clarity score | >= 4.0/5.0 | Developer survey |
| Threshold enforcement accuracy | 100% | Test with 0.05%, 0.1%, 0.15% diffs |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** UI has 0.05% pixel difference, **When** comparison runs, **Then** test passes (below 0.1% threshold)
- **Given** UI has 0.15% pixel difference, **When** comparison runs, **Then** test fails with visual diff report
- **Given** visual change is approved, **When** baseline update is triggered, **Then** new baseline is set for future comparisons
- **Given** visual comparison completes, **When** report is generated, **Then** differences are highlighted with bounding boxes

---

## Epic 10: Eval Protocol & Benchmarking

### Story 10.1: [Testing] Establish Golden PRD Benchmark Suite
**Task Ref**: EVAL-001
**Gap Ref**: Gap 6 (Research Paper Line 251)

**Definition of Done**:
- [ ] 10-20 representative PRDs created (Calculator, ToDo, E-commerce, Chat, etc.)
- [ ] Expected outputs stored as golden references
- [ ] Scoring rubrics defined per benchmark
- [ ] Index file with metadata (complexity, domain, expected tokens)
- [ ] Benchmark loader validates structure
- [ ] Unit tests for benchmark loading
- [ ] Integration test verifies benchmark execution
- [ ] Test coverage >= 80% for benchmark module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Benchmark coverage | 10-20 PRDs | Count unique benchmarks |
| Domain diversity | >= 5 domains | Count unique domains |
| Complexity distribution | Low/Med/High balanced | Count by complexity |
| Golden output accuracy | Validated by 2+ reviewers | Human review process |
| Benchmark load time | < 1 second total | Timer for full suite load |
| Rubric completeness | 100% of benchmarks | Check each has rubric |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** benchmark suite exists, **When** loaded, **Then** >= 10 unique PRD benchmarks are available
- **Given** Calculator benchmark, **When** inspected, **Then** golden reference includes expected functions, tests, and code structure
- **Given** benchmark has metadata, **When** parsed, **Then** complexity (1-10), domain, and expected_tokens are present
- **Given** benchmark index exists, **When** loaded, **Then** all benchmark files are discoverable and valid

---

### Story 10.2: [Testing] Implement Eval Harness with Performance Metrics
**Task Ref**: EVAL-002
**Gap Ref**: Gap 6 (Research Paper Line 251)

**Definition of Done**:
- [ ] DeepEval or Braintrust framework integrated
- [ ] pass@1 >= 85% (blocking metric)
- [ ] Task Completion >= 90% (blocking metric)
- [ ] pass@8 >= 60% (warning metric)
- [ ] Cost < $0.50 per task (advisory metric)
- [ ] CI nightly runs configured
- [ ] Regression > 5% triggers alert
- [ ] Unit tests for eval harness
- [ ] Integration test with full benchmark suite
- [ ] Test coverage >= 85% for eval module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| pass@1 rate | >= 85% | First attempt success across benchmarks |
| Task Completion rate | >= 90% | Fully completed tasks / total |
| pass@8 rate | >= 60% | Success within 8 attempts |
| Average cost per task | < $0.50 | Helicone cost tracking |
| Eval suite runtime | < 30 minutes | Timer for full suite |
| Regression detection latency | < 24 hours | Time from regression to alert |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** agent runs on benchmark suite, **When** pass@1 is calculated, **Then** result is >= 85% or CI fails
- **Given** agent completes benchmark, **When** cost is calculated, **Then** average < $0.50 per task
- **Given** nightly eval runs, **When** pass@1 drops by 6%, **Then** alert is triggered within 1 hour
- **Given** eval completes, **When** report is generated, **Then** all metrics are visible with trends

---

### Story 10.3: [Testing] Implement Agent Similarity Scoring
**Task Ref**: EVAL-003
**Gap Ref**: Gap 6 (Research Paper Line 251)

**Definition of Done**:
- [ ] Semantic similarity for text (embedding-based, >= 85%)
- [ ] AST comparison for code outputs
- [ ] JSON schema validation for structured outputs
- [ ] Detailed divergence reports generated
- [ ] Similarity thresholds configurable
- [ ] Unit tests for each comparison method
- [ ] Integration test with diverse outputs
- [ ] Test coverage >= 85% for similarity module

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Text similarity accuracy | >= 90% correlation with human | Compare to expert ratings |
| AST comparison accuracy | >= 95% | Test with known equivalent/different code |
| Schema validation coverage | 100% of structured outputs | Audit output types |
| Divergence report completeness | 100% of differences | Manual review of reports |
| Comparison latency | < 2 seconds per output | Timer per comparison |
| False equivalence rate | < 3% | Test with similar-but-wrong outputs |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** generated text and golden text, **When** semantic similarity is calculated, **Then** score >= 85% or test fails
- **Given** generated code and golden code, **When** AST comparison runs, **Then** structural equivalence is determined (ignoring formatting)
- **Given** generated JSON output, **When** schema validation runs, **Then** output matches expected schema or detailed errors are reported
- **Given** similarity < threshold, **When** divergence report is generated, **Then** specific differences are highlighted with line numbers

---

## Epic 11: Self-Evolution Foundation (Learning Layer)

### Story 11.1: [AI] Implement Experience Logger for Neo4j
**Task Ref**: EVOLVE-001
**FR Ref**: FR-07.1 (Experience Logger)

**Definition of Done**:
- [ ] Experience node schema implemented in Neo4j (id, task_type, task_id, success, prompt_version, model_used, tokens_used, cost_usd, duration_ms, retries, timestamp)
- [ ] Skill relationship implemented: `(:Experience)-[:USED_SKILL]->(:Skill)`
- [ ] Artifact relationship implemented: `(:Experience)-[:PRODUCED]->(:Artifact)`
- [ ] `ExperienceLogger.log_success()` method functional
- [ ] `ExperienceLogger.log_failure()` method functional
- [ ] `ExperienceLogger.query_similar_experiences()` method functional
- [ ] `ExperienceLogger.get_success_rate()` method functional with filters (task_type, model, prompt_version, time_window)
- [ ] Pydantic schemas defined for Experience, Skill, Artifact, Insight
- [ ] Cypher queries module with parameterized queries
- [ ] Unit tests for all ExperienceLogger methods
- [ ] Integration tests with Neo4j (VPS connection)
- [ ] Test coverage >= 85% for evolution module
- [ ] No blocking impact on main workflow performance

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Experience logging latency | < 100ms | Timer on log_success/log_failure |
| Query latency | < 200ms | Timer on query_similar_experiences |
| Storage overhead | < 1KB per experience | Neo4j node size monitoring |
| Success rate accuracy | 100% | Verify calculations against manual count |
| Schema compliance | 100% | Pydantic validation on all writes |
| Test coverage | >= 85% | pytest-cov for evolution module |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** a task completes successfully, **When** log_success() is called, **Then** Experience node exists in Neo4j with all required fields
- **Given** a task fails, **When** log_failure() is called, **Then** Experience node exists with error_type and error_message
- **Given** 10 experiences logged for task_type="coding", **When** get_success_rate(task_type="coding") is called, **Then** correct percentage is returned
- **Given** experiences with skills logged, **When** query_similar_experiences() is called, **Then** experiences with matching skills are returned first
- **Given** main workflow running, **When** experience logging occurs, **Then** workflow latency increases by < 5%

---

### Story 11.2: [AI] Implement Reflection Hook for Post-Task Learning
**Task Ref**: EVOLVE-002
**FR Ref**: FR-07.2 (Reflection Hook)

**Definition of Done**:
- [ ] ReflectionHook class implemented with LangGraph integration
- [ ] `reflect()` method functional (async, non-blocking)
- [ ] Three reflection depth modes implemented: quick, standard, deep
- [ ] Insight node schema implemented: what_worked, what_failed, lesson_learned
- [ ] Relationship implemented: `(:Experience)-[:REFLECTED_AS]->(:Insight)`
- [ ] Integration with ModelRouter for LLM reflection calls
- [ ] Reflection prompt template in prompts/ directory
- [ ] Non-blocking execution verified (main workflow continues)
- [ ] Unit tests for ReflectionHook methods
- [ ] Integration test with LangGraph orchestrator
- [ ] Test coverage >= 85% for reflection module
- [ ] Configurable depth selection (quick/standard/deep)

**Success Metrics**:
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Quick reflection latency | < 100ms | Timer on quick mode |
| Standard reflection latency | < 3 seconds | Timer on standard mode |
| Deep reflection latency | < 15 seconds | Timer on deep mode |
| Main workflow impact | 0% (async) | Verify non-blocking execution |
| Insight quality (manual) | >= 80% actionable | Sample 20 insights, rate quality |
| Reflection trigger rate | 100% of completions | Count reflections vs completions |

**Acceptance Criteria** (Testable - Given/When/Then):
- **Given** task completes, **When** ReflectionHook.reflect() is called, **Then** execution is non-blocking (main workflow continues immediately)
- **Given** depth="quick", **When** reflection runs, **Then** only metrics are logged (no LLM call)
- **Given** depth="standard", **When** reflection runs, **Then** LLM generates insight with what_worked, what_failed, lesson_learned
- **Given** depth="deep", **When** reflection runs, **Then** multi-model consensus is used for insight
- **Given** reflection completes, **When** Neo4j is queried, **Then** Insight node exists linked to Experience

---

### Story 11.3: [Future] Skill Library Integration (Placeholder)
**Task Ref**: EVOLVE-003 (not yet in tasks.json)
**FR Ref**: FR-07.3.1 (Skill Library)
**Status**: Reserved for Phase 2

**Definition of Done** (Placeholder - to be detailed in Phase 2):
- [ ] Skill extraction from successful experiences (Voyager pattern)
- [ ] Skill storage with success_rate and usage_count
- [ ] Skill retrieval for similar tasks
- [ ] Skill versioning and deprecation

---

### Story 11.4: [Future] Prompt Optimization (Placeholder)
**Task Ref**: EVOLVE-005 (not yet in tasks.json)
**FR Ref**: FR-07.3.2 (Prompt Optimization)
**Status**: Reserved for Phase 3

**Definition of Done** (Placeholder - to be detailed in Phase 3):
- [ ] DSPy-style automatic prompt improvement
- [ ] A/B testing infrastructure for prompts
- [ ] Success metric correlation with prompt versions
- [ ] Constitutional safety constraints for self-modification

---

## Summary Statistics

| Epic | Stories | Total DoD Items | Total Metrics |
|------|---------|-----------------|---------------|
| Epic 1: Workbench Core | 4 | 38 | 24 |
| Epic 2: Planner Agent | 4 | 36 | 24 |
| Epic 3: Executor Agent | 3 | 27 | 18 |
| Epic 4: Observability | 4 | 32 | 24 |
| Epic 5: Validator Agent | 5 | 42 | 30 |
| Epic 6: MCP Security | 4 | 32 | 24 |
| Epic 7: Prompt Governance | 2 | 18 | 12 |
| Epic 8: Deployment Policy | 2 | 18 | 12 |
| Epic 9: UAT Automation | 3 | 24 | 18 |
| Epic 10: Eval Protocol | 3 | 24 | 18 |
| Epic 11: Self-Evolution | 4 | 29 | 12 |
| **TOTAL** | **38** | **320** | **216** |

---

## Appendix: Metric Measurement Tools Reference

| Tool | Purpose | Stories Using |
|------|---------|---------------|
| pytest-cov | Test coverage measurement | 1.1, 1.2, 1.3, 1.4, All |
| pytest-benchmark | Performance benchmarking | 1.1, 1.3, 3.1 |
| Ruff | Python linting | 1.1, All Python stories |
| mypy/pyright | Type checking | 1.1, All Python stories |
| Helicone | LLM cost tracking | 2.1, 4.1, 10.2 |
| markdownlint | Markdown validation | 2.3 |
| Lighthouse | Frontend accessibility | 4.2 |
| Snyk/SonarQube | SAST/SCA scanning | 5.3, 8.1 |
| Playwright | Browser automation | 9.1, 9.2, 9.3 |
| Applitools | Visual regression | 9.3 |
| DeepEval/Braintrust | Agent evaluation | 10.2, 10.3 |
| Neo4j | Graph database for experiences | 11.1, 11.2 |
| asyncio | Non-blocking execution | 11.2 |

---

*Document generated: 2025-12-30*
*Updated: 2025-12-31 - Added Epic 11: Self-Evolution Foundation*
*Next review: Before Sprint 1 kickoff*
