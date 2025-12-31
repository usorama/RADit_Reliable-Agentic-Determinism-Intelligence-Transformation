# RADit Master Epic Plan: Epic 13-16

**Document Version**: 2.0
**Created**: 2025-12-31
**Vision**: A Self-Improving Software Development Factory
**Status**: APPROVED FOR IMPLEMENTATION

---

## Executive Summary

This document defines the complete roadmap from current MVP (49 backend tasks complete) to a **production-grade, self-improving software development factory** that:

1. **Interacts** with users during planning (Epic 13)
2. **Visualizes** work in real-time via Kanban (Epic 14)
3. **Self-heals** production issues autonomously (Epic 15)
4. **Evolves** through learning and optimization (Epic 16)

### MVP Definition

> **MVP = Epic 13 Phase A + Epic 14 Phase A**
>
> The minimum viable product enables users to:
> - Collaborate interactively during planning
> - See and approve PRDs before execution
> - Track progress via live Kanban board
> - Control what gets built

### Scope Classification

| Category | Definition | Timeline |
|----------|------------|----------|
| **MVP** | Required for first user deployment | 2-3 weeks |
| **Production** | Required for enterprise readiness | +2-3 weeks |
| **Future** | Competitive differentiation | Backlog |

---

## Research Foundation

This plan incorporates findings from:

1. **Master Design Document** - "The Deterministic Builder" vision
2. **Claude Agent SDK** - Orchestrator-subagent patterns, parallel execution
3. **Vibe Kanban** - tasks.json two-way sync architecture
4. **Agentic SDLC 2025** - Specialized agent ecosystems, maturity tiers
5. **Self-Healing AI** - Monitor-Diagnose-Heal loop architecture
6. **Factory AI patterns** - Automated code review, self-improving builds

---

## Epic 13: User Interaction & Human-in-the-Loop

**Theme**: Enable meaningful collaboration between users and AI during planning
**Business Outcome**: Users trust the system because they control decisions

### Phase A: MVP (Required)

#### INTERACT-001: Interview Response Collection
**Priority**: P0 | **Estimate**: 3 days | **Scope**: MVP

Enable users to answer the Planner's clarifying questions.

**Definition of Done**:
- Backend: Interview questions streamed via WebSocket
- Backend: `POST /api/workflow/{id}/interview-answer` endpoint
- Backend: Taskmaster `_interview_node` pauses for user input
- Frontend: `ClarificationFlow.tsx` with question display
- Frontend: Text, multi-choice, checkbox input types
- Frontend: Progress indicator ("Question 2 of 4")
- Frontend: "Skip remaining" option with confirmation
- Tests: Unit + integration tests for interview loop
- Accessibility: WCAG 2.1 AA compliant

**Acceptance Criteria**:
- User submits "Build a todo app" → sees clarifying questions within 5s
- User answers question → next question appears or PRD generation begins
- User clicks "skip" → workflow proceeds with defaults noted

---

#### INTERACT-002: PRD Presentation Display
**Priority**: P0 | **Estimate**: 3 days | **Scope**: MVP

Display generated PRD in structured, reviewable format.

**Definition of Done**:
- Frontend: `PlanPresentation.tsx` component
- Frontend: Sections: Overview, User Stories, Tech Specs, Acceptance Criteria, NFRs
- Frontend: Roundtable persona feedback displayed (CTO, UX, Security)
- Frontend: Expandable/collapsible sections
- Frontend: Complexity badges per feature
- Frontend: Export to PDF button
- Backend: PRD includes display metadata
- Tests: Unit tests + visual regression
- Accessibility: Screen reader compatible

**Acceptance Criteria**:
- PRD generated → user sees all 6 sections
- Roundtable critique visible with persona labels
- Export button → PDF download within 3s

---

#### INTERACT-003: PRD Approval Gate
**Priority**: P0 | **Estimate**: 2 days | **Scope**: MVP

Enable user approval/rejection/modification of PRD before execution.

**Definition of Done**:
- Backend: `AWAITING_PRD_APPROVAL` workflow status
- Backend: Orchestrator pauses after PRD generation
- Backend: `POST /api/workflow/{id}/prd-review` with approve/reject/modify
- Frontend: `ApprovalGate.tsx` with action buttons
- Frontend: Comment textarea for feedback
- Frontend: Confirmation modal before actions
- WebSocket: Status change streamed to UI
- Audit: Actions logged with timestamp + user

**Acceptance Criteria**:
- PRD displayed → status shows "Awaiting Your Approval"
- User clicks "Approve" → workflow proceeds to task decomposition
- User clicks "Reject" with reason → returns to interview phase

---

#### INTERACT-004: Task List Review
**Priority**: P0 | **Estimate**: 3 days | **Scope**: MVP

Enable user review of decomposed tasks before execution begins.

**Definition of Done**:
- Backend: `AWAITING_TASK_APPROVAL` workflow status
- Backend: `POST /api/workflow/{id}/tasks-review` endpoint
- Frontend: `TaskList.tsx` with hierarchical display
- Frontend: Phase → Story → Task hierarchy
- Frontend: Dependency indicators
- Frontend: Complexity badges
- Frontend: "Approve and Begin" button
- Tests: Unit + integration tests

**Acceptance Criteria**:
- Tasks decomposed → user sees hierarchical breakdown
- User reviews → can see dependencies between tasks
- User approves → execution phase begins

---

### Phase B: Production

#### INTERACT-005: Research Evidence Display
**Priority**: P1 | **Estimate**: 2 days | **Scope**: Production

Show research findings that informed PRD decisions.

**Definition of Done**:
- Frontend: `ResearchDisplay.tsx` component
- Frontend: Tabbed interface (Requirements, Architecture, Risks, Technology)
- Frontend: Source citations with links
- Frontend: Confidence scores for recommendations
- Backend: Research phase captures structured findings

---

#### INTERACT-006: Complexity Analysis Visualization
**Priority**: P1 | **Estimate**: 2 days | **Scope**: Production

Display complexity analysis with risk visualization.

**Definition of Done**:
- Frontend: `ComplexityAnalysis.tsx` component
- Frontend: Cognitive load scores (1-10 bars)
- Frontend: Dependency graph with risk coloring
- Frontend: Bottleneck warnings highlighted
- Backend: COMPLEXITY-001 output surfaced via API

---

#### INTERACT-007: Web Research MCP Server
**Priority**: P1 | **Estimate**: 4 days | **Scope**: Production

Enable Planner to perform live web research.

**Definition of Done**:
- Backend: `WebSearchMCPServer` in packages/daw-mcp/
- Tools: `web_search`, `fetch_page`, `summarize_url`
- Integration: Context7 or similar for library docs
- Backend: Rate limiting and caching
- RBAC: Planner role granted access

---

#### INTERACT-008: Iterative Planning Refinement
**Priority**: P1 | **Estimate**: 3 days | **Scope**: Production

Enable multiple planning iterations with version history.

**Definition of Done**:
- Backend: "Back to interview" from any planning phase
- Backend: State preservation on phase return
- Backend: PRD version history
- Frontend: "Refine Further" button at each gate
- Frontend: Version selector with diff view

---

### Phase C: Future

#### INTERACT-009: Workflow Progress Dashboard
**Priority**: P2 | **Scope**: Future

Visual state machine showing complete workflow progress.

---

#### INTERACT-010: Inline PRD Editing
**Priority**: P2 | **Scope**: Future

Edit PRD sections directly in UI without regeneration.

---

#### INTERACT-011: Persona Collaboration Indicators
**Priority**: P2 | **Scope**: Future

Show which AI persona is currently speaking/thinking.

---

#### INTERACT-012: Dependency Resolver MCP
**Priority**: P2 | **Scope**: Future

Check package versions and conflicts across npm/PyPI/Cargo.

---

## Epic 14: Kanban Board & Real-Time Visualization

**Theme**: tasks.json is the database; Kanban is the visualization
**Business Outcome**: Users see exactly what's happening, when

### Phase A: MVP (Required)

#### KANBAN-001: Core Kanban Board Component
**Priority**: P0 | **Estimate**: 4 days | **Scope**: MVP

Implement Kanban board that visualizes tasks.json state.

**Definition of Done**:
- Frontend: `KanbanBoard.tsx` component
- Frontend: Columns: Backlog, Planning, Coding, Validating, Deploying, Done
- Frontend: Task cards with ID, description, status, assignee
- Frontend: Real-time updates via WebSocket
- Frontend: Column counts and progress indicators
- Backend: `GET /api/workflow/{id}/kanban` endpoint
- Backend: `PATCH /api/workflow/{id}/kanban/{taskId}` for moves
- Two-way sync: UI changes → tasks.json, tasks.json changes → UI
- Tests: Unit tests for board state management

**Acceptance Criteria**:
- Workflow active → Kanban shows tasks in correct columns
- Agent completes task → card moves to next column automatically
- Page refresh → board state matches tasks.json exactly

---

#### KANBAN-002: Task Card Details Panel
**Priority**: P0 | **Estimate**: 2 days | **Scope**: MVP

Show task details when card is clicked.

**Definition of Done**:
- Frontend: `TaskDetailPanel.tsx` slide-out panel
- Frontend: Shows: description, dependencies, assigned agent, artifacts
- Frontend: Activity timeline (status changes, commits)
- Frontend: Link to agent trace for this task
- Tests: Unit tests for panel rendering

**Acceptance Criteria**:
- User clicks task card → details panel opens
- Panel shows complete task context
- Link to trace → navigates to agent trace view

---

#### KANBAN-003: Live Status Streaming
**Priority**: P0 | **Estimate**: 2 days | **Scope**: MVP

Stream task status changes to Kanban in real-time.

**Definition of Done**:
- Backend: Emit `kanban_update` events on task status change
- Frontend: `useKanban` hook subscribes to WebSocket
- Frontend: Optimistic updates with rollback on failure
- Frontend: Connection status indicator
- Tests: WebSocket event handling tests

**Acceptance Criteria**:
- Agent starts coding → card animates to "Coding" column
- Agent completes → card moves to "Validating" within 1s
- Connection lost → indicator shows, auto-reconnect

---

### Phase B: Production

#### KANBAN-004: Drag-and-Drop Prioritization
**Priority**: P1 | **Estimate**: 3 days | **Scope**: Production

Allow users to reorder tasks via drag-and-drop.

**Definition of Done**:
- Frontend: Drag-and-drop library integration
- Frontend: Visual feedback during drag
- Backend: Priority update endpoint
- Backend: Dependency validation (can't move before dependencies)
- Orchestrator: Respects user priority ordering

---

#### KANBAN-005: Agent Assignment Display
**Priority**: P1 | **Estimate**: 2 days | **Scope**: Production

Show which agent is assigned to each task.

**Definition of Done**:
- Frontend: Agent avatar on task cards
- Frontend: Agent status indicator (working, idle, error)
- Frontend: Click avatar → agent detail popover
- Backend: Agent assignment tracking

---

#### KANBAN-006: Metrics Dashboard
**Priority**: P1 | **Estimate**: 3 days | **Scope**: Production

Show workflow metrics alongside Kanban.

**Definition of Done**:
- Frontend: `MetricsDashboard.tsx` component
- Metrics: Tasks completed, avg time per task, error rate
- Metrics: Token usage, cost accumulation
- Metrics: Model distribution (which models used)
- Charts: Progress over time, velocity

---

### Phase C: Future

#### KANBAN-007: Multi-Workflow Board
**Priority**: P2 | **Scope**: Future

View multiple workflows on single board.

---

#### KANBAN-008: Custom Column Configuration
**Priority**: P2 | **Scope**: Future

Allow users to define custom workflow stages.

---

#### KANBAN-009: Swimlane Views
**Priority**: P2 | **Scope**: Future

Group tasks by feature, priority, or agent.

---

## Epic 15: Monitor-Diagnose-Heal Loop

**Theme**: Self-healing production software that fixes itself
**Business Outcome**: Reduced downtime, autonomous error resolution

### Phase A: Production (Post-MVP)

#### MDH-001: Monitor Node Integration
**Priority**: P1 | **Estimate**: 3 days | **Scope**: Production

Add monitoring state to Orchestrator workflow.

**Definition of Done**:
- Backend: `MONITORING` status in OrchestratorStatus enum
- Backend: `_monitor_node()` in Orchestrator
- Backend: Health check logic for deployed code
- Backend: Integration with external monitoring (Sentry/Datadog hooks)
- Backend: Anomaly detection thresholds
- Tests: Monitoring state transition tests

**Acceptance Criteria**:
- Deployment complete → status transitions to MONITORING
- Health check fails → triggers diagnosis workflow
- Metrics within threshold → continues monitoring

---

#### MDH-002: Diagnose Node Implementation
**Priority**: P1 | **Estimate**: 3 days | **Scope**: Production

Implement automated diagnosis of detected issues.

**Definition of Done**:
- Backend: `DIAGNOSING` status
- Backend: `_diagnose_node()` in Orchestrator
- Backend: Error classification (fixable vs. critical)
- Backend: Root cause analysis using error knowledge graph
- Backend: Query Neo4j for similar past errors
- Integration: Connect to existing Healer agent
- Tests: Diagnosis accuracy tests

**Acceptance Criteria**:
- Error detected → diagnosis runs automatically
- Similar error exists in KB → retrieves solution
- Novel error → classifies and suggests approaches

---

#### MDH-003: Heal Node Implementation
**Priority**: P1 | **Estimate**: 3 days | **Scope**: Production

Implement automated healing of fixable issues.

**Definition of Done**:
- Backend: `HEALING` status
- Backend: `_heal_node()` in Orchestrator
- Backend: Wire existing Healer agent into workflow
- Backend: Auto-retry up to 3x before escalation
- Backend: Create reproduction test case (Red)
- Backend: Apply fix (Green)
- Backend: Push to staging branch for review
- Tests: Healing success rate tests

**Acceptance Criteria**:
- Fixable error → Healer attempts fix
- Fix succeeds → returns to MONITORING
- Fix fails 3x → escalates to human

---

#### MDH-004: Escalation & Human Override
**Priority**: P1 | **Estimate**: 2 days | **Scope**: Production

Implement escalation for unfixable issues.

**Definition of Done**:
- Backend: `ESCALATING` status
- Backend: Alert generation with full context
- Backend: Human approval endpoint for manual override
- Frontend: Escalation notification in UI
- Frontend: "Override and Continue" or "Pause" buttons
- Notification: Slack/email webhook integration

**Acceptance Criteria**:
- Critical error → immediate escalation
- 3 failed heal attempts → escalation with context
- Human approves → workflow resumes or pauses

---

### Phase B: Future

#### MDH-005: Sentinel Agent (Risk Scanning)
**Priority**: P2 | **Scope**: Future

Parallel agent that critiques and intercepts risky operations.

**Definition of Done**:
- Backend: `SentinelAgent` class
- Backend: Runs parallel to Orchestrator
- Backend: Intercepts dangerous commands (DROP, rm -rf, sudo)
- Backend: Requires human approval for intercepted ops
- Integration: MCP server for Sentinel tools

---

#### MDH-006: Predictive Issue Detection
**Priority**: P2 | **Scope**: Future

Predict issues before they occur using patterns.

---

#### MDH-007: Auto-Rollback Capability
**Priority**: P2 | **Scope**: Future

Automatic rollback to last known good state on critical failure.

---

## Epic 16: Self-Evolution & Learning

**Theme**: System that improves itself over time
**Business Outcome**: Increasing efficiency, decreasing costs

### Phase A: Production (Foundation Already Built)

Note: EVOLVE-001 and EVOLVE-002 are already complete.

#### EVOLVE-003: Skill Extraction Library
**Priority**: P1 | **Estimate**: 4 days | **Scope**: Production

Extract reusable patterns from successful experiences.

**Definition of Done**:
- Backend: `SkillExtractor` class
- Backend: Analyze successful task completions
- Backend: Extract code patterns as reusable "skills"
- Backend: Store skills in Neo4j with success_rate
- Backend: Skills retrieved for similar future tasks
- Pattern: Voyager-style skill library
- Tests: Skill extraction accuracy tests

**Acceptance Criteria**:
- Task succeeds → patterns analyzed for extraction
- Similar task appears → relevant skills suggested
- Skill success rate tracked over time

---

#### EVOLVE-004: Model Performance Analytics
**Priority**: P1 | **Estimate**: 3 days | **Scope**: Production

Track and analyze model performance by task type.

**Definition of Done**:
- Backend: Performance metrics per model per task type
- Backend: Success rate, latency, cost analysis
- Backend: Automatic model recommendation updates
- Frontend: Model analytics dashboard
- Integration: Helicone data aggregation

**Acceptance Criteria**:
- Each task → metrics logged by model
- Weekly analysis → identifies best models per task type
- Recommendations updated automatically

---

### Phase B: Future

#### EVOLVE-005: Prompt Optimization (DSPy)
**Priority**: P2 | **Scope**: Future

Automatic prompt improvement via DSPy-style optimization.

---

#### EVOLVE-006: A/B Testing Infrastructure
**Priority**: P2 | **Scope**: Future

Test prompt/model variations with statistical significance.

---

#### EVOLVE-007: Constitutional Safety Constraints
**Priority**: P2 | **Scope**: Future

Safety guardrails for self-modification capabilities.

---

## Epic 17: Multi-Model Driver Support

**Theme**: LLM as stateless reasoning unit, system as the OS
**Business Outcome**: Best model for each task, cost optimization

### Phase A: Production

#### DRIVER-001: Model Driver Abstraction Layer
**Priority**: P1 | **Estimate**: 3 days | **Scope**: Production

Implement hot-swappable model driver configuration.

**Definition of Done**:
- Backend: `ModelDriver` abstract interface
- Backend: Drivers: ClaudeDriver, OpenAIDriver, GeminiDriver, LocalDriver
- Backend: Config via `config.yaml` use_driver setting
- Backend: Task formatting per driver requirements
- Backend: Unified response parsing
- Tests: Driver switching tests

**Acceptance Criteria**:
- Config change → driver switches without code change
- Same task → same output structure regardless of driver
- Driver fails → automatic fallback to secondary

---

#### DRIVER-002: Model Driver MCP Server
**Priority**: P1 | **Estimate**: 2 days | **Scope**: Production

Expose model configuration via MCP for agent introspection.

**Definition of Done**:
- Backend: `ModelDriverMCPServer` in packages/daw-mcp/
- Tools: `list_models`, `get_model_config`, `estimate_cost`
- Integration: Query from Planner for model recommendations
- Tests: MCP server unit tests

---

#### DRIVER-003: Cost Optimization Router
**Priority**: P1 | **Estimate**: 2 days | **Scope**: Production

Intelligent routing based on cost/capability tradeoffs.

**Definition of Done**:
- Backend: Cost-aware routing in ModelRouter
- Backend: Task complexity → model tier mapping
- Backend: Budget constraints respected
- Frontend: Cost projection display
- Tests: Cost optimization accuracy tests

---

### Phase B: Future

#### DRIVER-004: Local Model Support
**Priority**: P2 | **Scope**: Future

Support for local models via Ollama/LM Studio.

---

#### DRIVER-005: Model Ensemble Voting
**Priority**: P2 | **Scope**: Future

Multiple models vote on critical decisions.

---

---

## MVP Summary

### MVP Scope (2-3 weeks)

| Epic | Tasks | Est. Days |
|------|-------|-----------|
| Epic 13 Phase A | INTERACT-001, 002, 003, 004 | 11 |
| Epic 14 Phase A | KANBAN-001, 002, 003 | 8 |
| **Total** | **7 tasks** | **~19 days** |

### MVP Deliverables

1. **User can answer Planner questions** (INTERACT-001)
2. **User can see and approve PRD** (INTERACT-002, 003)
3. **User can review tasks before execution** (INTERACT-004)
4. **User can track progress via Kanban** (KANBAN-001, 002, 003)

### MVP User Journey

```
User: "Build me a todo app"
        ↓
Planner: "A few questions..."
        ↓ (INTERACT-001)
User answers questions
        ↓
PRD displayed for review
        ↓ (INTERACT-002)
User: [Approve PRD]
        ↓ (INTERACT-003)
Tasks displayed
        ↓
User: [Approve Tasks]
        ↓ (INTERACT-004)
Kanban shows progress
        ↓ (KANBAN-001, 002, 003)
User watches cards move through columns
        ↓
Deployment complete
```

---

## Production Scope (+2-3 weeks after MVP)

| Epic | Tasks | Est. Days |
|------|-------|-----------|
| Epic 13 Phase B | INTERACT-005, 006, 007, 008 | 11 |
| Epic 14 Phase B | KANBAN-004, 005, 006 | 8 |
| Epic 15 Phase A | MDH-001, 002, 003, 004 | 11 |
| Epic 16 Phase A | EVOLVE-003, 004 | 7 |
| Epic 17 Phase A | DRIVER-001, 002, 003 | 7 |
| **Total** | **17 tasks** | **~44 days** |

---

## Future Backlog

| Epic | Tasks |
|------|-------|
| Epic 13 Phase C | INTERACT-009, 010, 011, 012 |
| Epic 14 Phase C | KANBAN-007, 008, 009 |
| Epic 15 Phase B | MDH-005, 006, 007 |
| Epic 16 Phase B | EVOLVE-005, 006, 007 |
| Epic 17 Phase B | DRIVER-004, 005 |
| **Total** | **17 tasks** |

---

## Task ID Reference

| ID | Description | Scope |
|----|-------------|-------|
| INTERACT-001 | Interview Response Collection | MVP |
| INTERACT-002 | PRD Presentation Display | MVP |
| INTERACT-003 | PRD Approval Gate | MVP |
| INTERACT-004 | Task List Review | MVP |
| INTERACT-005 | Research Evidence Display | Production |
| INTERACT-006 | Complexity Visualization | Production |
| INTERACT-007 | Web Research MCP Server | Production |
| INTERACT-008 | Iterative Planning Refinement | Production |
| INTERACT-009 | Workflow Progress Dashboard | Future |
| INTERACT-010 | Inline PRD Editing | Future |
| INTERACT-011 | Persona Collaboration Indicators | Future |
| INTERACT-012 | Dependency Resolver MCP | Future |
| KANBAN-001 | Core Kanban Board Component | MVP |
| KANBAN-002 | Task Card Details Panel | MVP |
| KANBAN-003 | Live Status Streaming | MVP |
| KANBAN-004 | Drag-and-Drop Prioritization | Production |
| KANBAN-005 | Agent Assignment Display | Production |
| KANBAN-006 | Metrics Dashboard | Production |
| KANBAN-007 | Multi-Workflow Board | Future |
| KANBAN-008 | Custom Column Configuration | Future |
| KANBAN-009 | Swimlane Views | Future |
| MDH-001 | Monitor Node Integration | Production |
| MDH-002 | Diagnose Node Implementation | Production |
| MDH-003 | Heal Node Implementation | Production |
| MDH-004 | Escalation & Human Override | Production |
| MDH-005 | Sentinel Agent | Future |
| MDH-006 | Predictive Issue Detection | Future |
| MDH-007 | Auto-Rollback Capability | Future |
| EVOLVE-003 | Skill Extraction Library | Production |
| EVOLVE-004 | Model Performance Analytics | Production |
| EVOLVE-005 | Prompt Optimization (DSPy) | Future |
| EVOLVE-006 | A/B Testing Infrastructure | Future |
| EVOLVE-007 | Constitutional Safety Constraints | Future |
| DRIVER-001 | Model Driver Abstraction Layer | Production |
| DRIVER-002 | Model Driver MCP Server | Production |
| DRIVER-003 | Cost Optimization Router | Production |
| DRIVER-004 | Local Model Support | Future |
| DRIVER-005 | Model Ensemble Voting | Future |

---

## Dependencies Graph

```
MVP Critical Path:
INTERACT-001 → INTERACT-002 → INTERACT-003 → INTERACT-004
       ↓
KANBAN-001 → KANBAN-002 → KANBAN-003

Production Dependencies:
INTERACT-004 → MDH-001 → MDH-002 → MDH-003 → MDH-004
INTERACT-007 ← CORE-003 (MCP Client - already complete)
DRIVER-001 → DRIVER-002 → DRIVER-003
EVOLVE-001 (complete) → EVOLVE-003 → EVOLVE-004
```

---

## Success Metrics

### MVP Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Interview completion rate | 100% | All sessions complete interview |
| PRD approval (first attempt) | ≥70% | Approvals / Total PRDs |
| Task approval rate | ≥80% | Approvals / Total decompositions |
| Kanban sync accuracy | 100% | UI state = tasks.json state |
| User satisfaction | ≥4/5 | Post-session survey |

### Production Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Self-healing success rate | ≥70% | Heals / Total fixable errors |
| Mean time to heal | <5 min | Avg healing duration |
| Skill reuse rate | ≥30% | Tasks using extracted skills |
| Model cost reduction | ≥20% | Via intelligent routing |
| pass@1 rate | ≥90% | First attempt success |

---

## Architecture Impact

### New Orchestrator States

```python
class OrchestratorStatus(str, Enum):
    # Existing
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    DEPLOYING = "deploying"
    COMPLETED = "completed"
    ERROR = "error"

    # New (Epic 13)
    AWAITING_PRD_APPROVAL = "awaiting_prd_approval"
    AWAITING_TASK_APPROVAL = "awaiting_task_approval"

    # New (Epic 15)
    MONITORING = "monitoring"
    DIAGNOSING = "diagnosing"
    HEALING = "healing"
    ESCALATING = "escalating"
```

### New MCP Servers

| Server | Epic | Purpose |
|--------|------|---------|
| `web_research` | 13 | Web search + doc lookup |
| `model_driver` | 17 | Model config exposure |
| `sentinel` | 15 | Risk scanning |
| `dependency_resolver` | 13 | Package version checks |

### New Frontend Components

| Component | Epic | Location |
|-----------|------|----------|
| `ClarificationFlow.tsx` | 13 | apps/web/src/components/plan/ |
| `PlanPresentation.tsx` | 13 | apps/web/src/components/plan/ |
| `ApprovalGate.tsx` | 13 | apps/web/src/components/plan/ |
| `TaskList.tsx` | 13 | apps/web/src/components/plan/ |
| `KanbanBoard.tsx` | 14 | apps/web/src/components/kanban/ |
| `TaskDetailPanel.tsx` | 14 | apps/web/src/components/kanban/ |
| `MetricsDashboard.tsx` | 14 | apps/web/src/components/dashboard/ |

---

*Document Version: 2.0*
*Last Updated: 2025-12-31*
*Status: Ready for implementation*
