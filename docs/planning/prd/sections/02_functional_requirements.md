# 02. Functional Requirements (FR)

## FR-01: Agent Operating System (Kernel)
The core platform must provide an abstraction layer over raw LLM APIs.
-   **FR-01.1 Model Layer**: Standardized interface for LLMs (OpenAI, Anthropic, DeepSeek). Support for "Router Mode" to select models based on task complexity (e.g., o1 for planning, Haiku for coding).
-   **FR-01.2 Memory Layer**: Context management system. Must support "Context Compaction" to summarize session history and maintain a `project-context.md` (or semantic graph) file that is injected into every prompt.
-   **FR-01.3 Tool Layer (MCP)**: Full implementation of the **Model Context Protocol (MCP)**.
    -   Discovery of tools (Git, Postgres, Filesystem).
    -   Security validation of tool calls against a schema.
    -   **FR-01.3.1 MCP Gateway Authorization** (OAuth 2.1 with RFC 8707 Resource Indicators)
        -   Per-agent scoped tokens (e.g., database agent: SELECT only, no DDL)
        -   Token TTL: 15 minutes for automated, 1 hour for interactive sessions
    -   **FR-01.3.2 RBAC for Tools**: Fine-grained role-based access control
        -   Planner: search, read_file, query_db (SELECT) - No writes
        -   Executor: read_file, write_file, git_commit - Scoped to project directory
        -   Validator: run_tests, security_scan, lint - No file writes
        -   Healer: read_file, write_file (patches only) - Requires human approval for production
    -   **FR-01.3.3 Audit Logging**: Every tool call logged with timestamp, agent_id, user_id, tool name, action, parameters, result. Hash-chained for tamper resistance. 7-year retention for SOC 2/ISO 27001 compliance.
    -   **FR-01.3.4 Content Injection Prevention**: AI Prompt Shields, JSON schema validation, blocked command patterns (DROP, DELETE, rm -rf, sudo).
-   **FR-01.4 Workflow Engine**: A state machine to enforce the sequence of operations (Planning -> Coding -> Testing).

## FR-02: Spec-Driven Development Engine (The Planner)
A module to transform vague ideas into executable requirements.
-   **FR-02.1 Taskmaster Workflow**: Interactive chat interface where a "Senior PM" agent interviews the user.
-   **FR-02.2 Concept Roundtable**: Simulation of a critique session between synthetic personas (CTO, UX, Security).
-   **FR-02.3 PRD Generation**: Output a structured `prd.md` containing User Stories, Tech Specs, and Acceptance Criteria.
-   **FR-02.4 Task Decomposition**: Parse `prd.md` into atomic `tasks.json` usable by Executor Agents.
-   **FR-02.5 Complexity Analysis Engine**: Before any code is written, analyze the PRD to produce `complexity_analysis.json`:
    -   Feature-by-feature cognitive load scores (1-10)
    -   Dependency graph with risk ratings (low/medium/high/critical)
    -   Recommended model tier per task (planning: o1/opus, coding: sonnet/haiku)
    -   Architectural bottleneck warnings and mitigation strategies
    -   **Integration**: Complexity scores inform task sizing in `tasks.json`
    -   **Acceptance Criteria**: Analysis must complete successfully before task generation proceeds.

## FR-03: Development Loop (The Executor)
The coding engine that strictly follows TDD.
-   **FR-03.1 Red Phase Enforcement**: The agent *must* write a failing test first. The system must verify the test fails before allowing implementation code.
-   **FR-03.2 Green Phase**: Agent writes minimal code to pass the test.
-   **FR-03.3 Refactor Phase**: Agent optimizes code. Tests are auto-run to ensure no regression.
-   **FR-03.4 Rule Enforcement**: Apply `.cursorrules` or equivalent linter rules to constrain coding style.

## FR-04: Validation & Quality Assurance

### FR-04.1 Secure Sandbox (Execution Environment)
Isolated execution environment for running untrusted code:
-   **FR-04.1.1 Ephemeral Environments**: Integration with **E2B** or Docker Containers. Every task runs in a fresh container.
-   **FR-04.1.2 Network Isolation**: Sandbox has restricted internet access (allowlist only).
-   **FR-04.1.3 Resource Limits**: CPU/RAM caps to prevent infinite loops from crashing the host.
-   **FR-04.1.4 Side-Effect Containment**: All file writes, command executions, and package installations happen inside isolated containers.

### FR-04.2 Validator Agent (Quality Assurance - DISTINCT FROM SANDBOX)
A separate intelligent agent responsible for validation, running on a **different model** from the Executor to prevent bias:
-   **FR-04.2.1 Test Execution**: Run test suites (unit, integration) and interpret results
-   **FR-04.2.2 Static Analysis**: Run SAST security scans (Snyk, SonarQube, or equivalent)
-   **FR-04.2.3 Dependency Checks**: SCA vulnerability scanning for all dependencies
-   **FR-04.2.4 Policy Compliance**: Validate against organizational policies and coding standards
-   **FR-04.2.5 Actionable Feedback**: Generate improvement suggestions, not just pass/fail
-   **FR-04.2.6 Retry Logic**: Route fixable failures back to Executor (max 3 retries)
-   **FR-04.2.7 Escalation**: Route critical/unfixable issues to human reviewers
-   **FR-04.2.8 Multi-Model Validation**: Use ensemble of models for cross-verification on critical validations

## FR-05: Operational Resilience (The Ops)

### FR-05.1 Monitor Agent (Drift Detection)
Inspects agent traces for "Looping" or "Drift" with specific, measurable metrics:

| Metric | Baseline | Alert Threshold | Action |
|--------|----------|-----------------|--------|
| Tool Usage Frequency | Per-task baseline | +50% deviation | Log warning |
| Reasoning Step Count | Average per task type | +100% increase | Pause agent |
| Context Window Utilization | Tracked per session | > 90% | Force compaction |
| Retry Rate | Per-task baseline | > 3x baseline | Escalate to human |
| Token Cost per Task | Historical average | +200% increase | Budget alert |

-   **FR-05.1.1 Alerting**: Integration with observability stack (Helicone, Datadog). Slack/Linear notifications.
-   **FR-05.1.2 Actions**: Mild drift → increase monitoring; Moderate → context compaction; Severe → pause agent.

### FR-05.2 Diagnose & Heal
If a build fails, a separate "Healer Agent" reads the error log, searches a knowledge base (RAG), and attempts a patch.

## FR-06: Automated User Acceptance Testing (UAT)

### FR-06.1 Playwright MCP Integration
-   UAT Agent uses Playwright MCP for browser automation
-   Operates on accessibility snapshots (not screenshots) for determinism and speed
-   Supports cross-browser testing (Chromium, Firefox, WebKit)

### FR-06.2 Persona-Based Testing
User personas defined in `uat/personas.yaml`:
-   "Power User" - Desktop, fast network, uses keyboard shortcuts
-   "First-Time User" - Mobile, 3G network, help-seeking behavior
-   "Accessibility User" - Screen reader, keyboard-only navigation

### FR-06.3 Business Journey Validation
-   PRD acceptance criteria translated to Gherkin scenarios (Given/When/Then)
-   UAT Agent executes scenarios using Playwright MCP
-   Generate validation reports with screenshots, traces, and timing

### FR-06.4 Visual Regression Testing
-   Applitools Eyes or equivalent AI-powered visual comparison
-   Threshold: < 0.1% pixel difference for critical UI components
-   Automatic baseline updates for approved intentional changes

### FR-06.5 Release Gating
-   UAT results integrated with deployment quality gates
-   P0 journey failures **block** production deployment
-   P1 journey failures generate warnings, require explicit approval

## FR-07: Self-Evolution Foundation (Learning Layer)

The system must establish foundations for autonomous improvement over time, transitioning from purely reactive (Monitor-Diagnose-Heal) to proactive learning patterns.

### FR-07.1 Experience Logger
Store structured records of task executions in Neo4j for future learning:
-   **FR-07.1.1 Experience Schema**: Each task completion creates an Experience node with:
    -   `task_type` (planning, coding, validation)
    -   `task_id` (reference to original task)
    -   `success` (boolean outcome)
    -   `prompt_version` (which prompt template was used)
    -   `model_used` (which LLM executed the task)
    -   `tokens_used`, `cost_usd`, `duration_ms` (resource metrics)
    -   `retries` (how many attempts before success/failure)
-   **FR-07.1.2 Skill Relationships**: Link experiences to discovered patterns:
    -   `(:Experience)-[:USED_SKILL]->(:Skill)` - code patterns that worked
    -   `(:Experience)-[:PRODUCED]->(:Artifact)` - outputs generated
-   **FR-07.1.3 Success Rate Tracking**: Calculate and store success rates per:
    -   Task type + model combination
    -   Prompt version
    -   Time period (detect degradation over time)
-   **FR-07.1.4 RAG Retrieval**: Query similar past experiences when starting new tasks

### FR-07.2 Reflection Hook
Proactive learning after task completion (not just on failure):
-   **FR-07.2.1 Post-Task Reflection**: After successful completion, trigger reflection:
    -   "What worked well in this task?"
    -   "What patterns should be remembered?"
    -   "What could be improved next time?"
-   **FR-07.2.2 Insight Storage**: Store reflection insights as Neo4j nodes:
    -   `(:Experience)-[:REFLECTED_AS]->(:Insight)`
    -   Insights include `what_worked`, `what_failed`, `lesson_learned`
-   **FR-07.2.3 Configurable Depth**: Three reflection modes:
    -   `quick` - Minimal overhead, key metrics only
    -   `standard` - LLM-generated insights (default)
    -   `deep` - Multi-model consensus on lessons learned
-   **FR-07.2.4 Non-Blocking**: Reflection executes asynchronously to avoid slowing main workflow

### FR-07.3 Future Evolution Hooks (Placeholder)
Reserved for Phase 2+ self-evolution capabilities:
-   **FR-07.3.1 Skill Library**: Extract and store reusable code patterns (Voyager pattern)
-   **FR-07.3.2 Prompt Optimization**: DSPy-style automatic prompt improvement
-   **FR-07.3.3 Constitutional Safety**: RLAIF constraints for safe self-modification

**Note**: FR-07.1 and FR-07.2 establish the data foundation. FR-07.3 capabilities require this foundation and are planned for post-MVP implementation.
