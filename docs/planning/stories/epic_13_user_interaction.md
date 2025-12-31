# Epic 13: User Interaction & Human-in-the-Loop Planning

**Created**: 2025-12-31
**Status**: Draft - Pending Review
**Priority**: P0 (Critical for MVP completeness)
**Rationale**: The current MVP has backend agents complete but lacks the critical user interaction layer that makes the system usable by non-technical product owners.

---

## Executive Summary

**Problem Statement**:
The RADit system currently operates as a "fire and forget" AI - users send a message and receive a complete output. This lacks the **human-in-the-loop** interaction that makes AI-assisted development trustworthy and effective.

**Business Outcome**:
Enable product owners and non-technical stakeholders to:
1. Collaborate interactively with AI during planning
2. Review and approve plans before execution begins
3. Provide clarifications that shape the requirements
4. Maintain control over what gets built

**User Outcome**:
- I can answer the AI's clarifying questions
- I can see and review the generated PRD before coding starts
- I can approve, reject, or request modifications to plans
- I can see research findings that inform decisions
- I can understand complexity and risks before committing

---

## Gap Analysis Summary

| Gap Category | Count | MVP Impact |
|--------------|-------|------------|
| Frontend UI Components | 6 | HIGH - Users can't see/interact with plans |
| Backend Workflow Interrupts | 4 | HIGH - No human checkpoints in workflow |
| Research Tools | 4 | MEDIUM - AI relies only on training data |
| API Endpoints | 5 | HIGH - No way to send user decisions |

---

## Stories and Tasks

### PHASE A: Critical Path (Required for MVP)

These stories are **blocking** - without them, users cannot meaningfully interact with the Planner.

---

#### Story 13.1: Interview Response Collection

**As a** Product Owner,
**I want** to answer the Planner's clarifying questions,
**So that** my requirements are accurately captured before PRD generation.

**Task ID**: INTERACT-001
**Priority**: P0
**Phase**: 10

**Definition of Done**:
- [ ] Backend: Interview questions streamed to UI via WebSocket
- [ ] Backend: New endpoint `POST /api/workflow/{id}/interview-answer` accepts user responses
- [ ] Backend: `_interview_node` in Taskmaster pauses and waits for user input (async)
- [ ] Backend: Interview loop continues until user says "proceed" or AI has no more questions
- [ ] Frontend: `ClarificationFlow.tsx` component displays questions with answer inputs
- [ ] Frontend: Support for text, multi-choice, and checkbox question types
- [ ] Frontend: Progress indicator showing "Question 2 of 4"
- [ ] Frontend: "Skip remaining questions" option with warning
- [ ] Integration: User answers stored in workflow state and accessible to Roundtable
- [ ] Tests: Unit tests for interview loop state machine
- [ ] Tests: Integration test with mock user responses
- [ ] Accessibility: WCAG 2.1 AA compliant

**Acceptance Criteria**:
1. **Given** user submits "Build a todo app", **When** Planner processes, **Then** UI displays first clarifying question within 5 seconds
2. **Given** question is displayed, **When** user submits answer, **Then** next question appears or PRD generation begins
3. **Given** user clicks "skip remaining", **When** confirmed, **Then** workflow proceeds with default assumptions noted
4. **Given** interview complete, **When** PRD is generated, **Then** it references user's specific answers

**Dependencies**: None (can start immediately)

---

#### Story 13.2: PRD Presentation and Display

**As a** Product Owner,
**I want** to see the generated PRD in a structured, readable format,
**So that** I can understand and evaluate what the AI plans to build.

**Task ID**: INTERACT-002
**Priority**: P0
**Phase**: 10

**Definition of Done**:
- [ ] Frontend: `PlanPresentation.tsx` component created
- [ ] Frontend: Structured display of PRD sections:
  - Overview/Summary
  - User Stories with priority badges
  - Technical Specifications
  - Acceptance Criteria (testable format)
  - Non-Functional Requirements
  - Architecture decisions
- [ ] Frontend: Expandable/collapsible sections
- [ ] Frontend: Roundtable persona feedback displayed (CTO, UX, Security critiques)
- [ ] Frontend: Complexity scores visualized (heat map or badges)
- [ ] Frontend: Syntax highlighting for any code snippets
- [ ] Frontend: Print/Export to PDF button
- [ ] Backend: PRD data structure includes display metadata
- [ ] Tests: Unit tests for PRD rendering
- [ ] Tests: Visual regression tests for PRD display
- [ ] Accessibility: Screen reader compatible

**Acceptance Criteria**:
1. **Given** PRD is generated, **When** user views it, **Then** all 6 PRD sections are visible
2. **Given** Roundtable critique exists, **When** viewing PRD, **Then** persona feedback is shown with persona labels
3. **Given** PRD is displayed, **When** user clicks export, **Then** PDF download starts within 3 seconds

**Dependencies**: INTERACT-001 (interview must complete to generate PRD)

---

#### Story 13.3: PRD Approval Gate

**As a** Product Owner,
**I want** to approve, reject, or request modifications to the PRD,
**So that** I maintain control over what gets built before any code is written.

**Task ID**: INTERACT-003
**Priority**: P0
**Phase**: 10

**Definition of Done**:
- [ ] Backend: New workflow status `AWAITING_PRD_APPROVAL` added
- [ ] Backend: Orchestrator pauses after PRD generation, sets status
- [ ] Backend: New endpoint `POST /api/workflow/{id}/prd-review` with actions:
  - `approve`: Proceed to task decomposition
  - `reject`: Return to interview with reason
  - `modify`: Accept modifications and regenerate
- [ ] Backend: Modifications incorporated into PRD state
- [ ] Frontend: `ApprovalGate.tsx` component with three action buttons
- [ ] Frontend: Comment/feedback textarea for rejection reason
- [ ] Frontend: Modifications form for inline edits
- [ ] Frontend: Confirmation modal before approve/reject
- [ ] Frontend: Status badge showing "Awaiting Your Approval"
- [ ] WebSocket: Stream status change to UI when approval needed
- [ ] Tests: E2E test for full approval flow
- [ ] Audit: Approval actions logged with timestamp and user

**Acceptance Criteria**:
1. **Given** PRD is generated, **When** displayed to user, **Then** status shows "Awaiting Your Approval"
2. **Given** user clicks "Approve", **When** confirmed, **Then** workflow proceeds to task decomposition
3. **Given** user clicks "Reject" with reason, **When** submitted, **Then** workflow returns to interview phase with context preserved
4. **Given** user clicks "Request Modifications", **When** modifications submitted, **Then** PRD is regenerated incorporating changes

**Dependencies**: INTERACT-002 (PRD must be displayed before approval)

---

#### Story 13.4: Task List Review and Approval

**As a** Product Owner,
**I want** to review the decomposed tasks before execution begins,
**So that** I can validate the work breakdown and adjust priorities.

**Task ID**: INTERACT-004
**Priority**: P0
**Phase**: 10

**Definition of Done**:
- [ ] Backend: New workflow status `AWAITING_TASK_APPROVAL` added
- [ ] Backend: Orchestrator pauses after task decomposition
- [ ] Backend: New endpoint `POST /api/workflow/{id}/tasks-review` with actions:
  - `approve`: Proceed to execution
  - `reorder`: Accept new task order
  - `remove`: Remove specified tasks
  - `modify`: Update task descriptions/criteria
- [ ] Frontend: `TaskList.tsx` component with hierarchical display
- [ ] Frontend: Phase → Story → Task hierarchy
- [ ] Frontend: Dependency arrows or badges
- [ ] Frontend: Complexity/effort badges per task
- [ ] Frontend: Drag-and-drop reordering (optional, nice-to-have)
- [ ] Frontend: Checkbox to remove tasks
- [ ] Frontend: Inline edit for task descriptions
- [ ] Frontend: "Approve and Begin Execution" prominent button
- [ ] Tests: Unit tests for task list manipulation
- [ ] Tests: Integration test for task reordering

**Acceptance Criteria**:
1. **Given** tasks are decomposed, **When** displayed, **Then** user sees hierarchical task breakdown
2. **Given** task list is shown, **When** user removes a task, **Then** dependencies are recalculated
3. **Given** user clicks "Approve", **When** confirmed, **Then** execution phase begins
4. **Given** task has dependency, **When** viewing, **Then** dependency is visually indicated

**Dependencies**: INTERACT-003 (PRD must be approved before task decomposition)

---

### PHASE B: Essential Enhancements (Required for Production)

---

#### Story 13.5: Research Display and Evidence

**As a** Product Owner,
**I want** to see the research findings that informed the PRD,
**So that** I can trust the AI's recommendations are well-founded.

**Task ID**: INTERACT-005
**Priority**: P1
**Phase**: 10

**Definition of Done**:
- [ ] Frontend: `ResearchDisplay.tsx` component
- [ ] Frontend: Tabbed interface showing:
  - Requirements analysis findings
  - Architecture recommendations with rationale
  - Competitive analysis (if performed)
  - Risk assessment matrix
  - Technology recommendations with alternatives
- [ ] Frontend: Source citations with links (if from web research)
- [ ] Frontend: Confidence scores for recommendations
- [ ] Backend: Research phase captures structured findings
- [ ] Backend: Findings attached to workflow state
- [ ] Tests: Unit tests for research display

**Acceptance Criteria**:
1. **Given** research is complete, **When** user views research tab, **Then** all findings are categorized
2. **Given** recommendation has alternatives, **When** displayed, **Then** user sees comparison
3. **Given** finding has source, **When** displayed, **Then** source link is clickable

**Dependencies**: INTERACT-002

---

#### Story 13.6: Complexity Analysis Visualization

**As a** Product Owner,
**I want** to see the complexity analysis before committing to the plan,
**So that** I understand the risks and effort involved.

**Task ID**: INTERACT-006
**Priority**: P1
**Phase**: 10

**Definition of Done**:
- [ ] Frontend: `ComplexityAnalysis.tsx` component
- [ ] Frontend: Cognitive load scores visualized (1-10 scale bars)
- [ ] Frontend: Dependency graph with risk coloring (low=green, high=red)
- [ ] Frontend: Recommended model tier per task (info tooltip)
- [ ] Frontend: Bottleneck warnings highlighted
- [ ] Frontend: Overall risk assessment summary
- [ ] Backend: COMPLEXITY-001 output surfaced to API
- [ ] Tests: Visual regression tests for complexity display

**Acceptance Criteria**:
1. **Given** complexity analysis exists, **When** displayed, **Then** each feature shows cognitive load score
2. **Given** bottleneck exists, **When** viewing analysis, **Then** warning is prominently displayed
3. **Given** high-risk dependency, **When** viewing graph, **Then** edge is colored red

**Dependencies**: COMPLEXITY-001 must produce analysis, INTERACT-002

---

#### Story 13.7: Web Research MCP Integration

**As a** Planner Agent,
**I want** access to web search and documentation lookup tools,
**So that** I can provide current, accurate recommendations.

**Task ID**: INTERACT-007
**Priority**: P1
**Phase**: 10

**Definition of Done**:
- [ ] Backend: `WebSearchMCPServer` created in packages/daw-mcp/
- [ ] Backend: Tools: `web_search`, `fetch_page`, `summarize_url`
- [ ] Backend: Rate limiting and caching implemented
- [ ] Backend: Integration with search API (SerpAPI, Brave, or similar)
- [ ] Backend: `DocumentationLookupMCPServer` created
- [ ] Backend: Tools: `lookup_library_docs`, `get_api_reference`
- [ ] Backend: Integration with Context7 or similar
- [ ] Backend: RBAC policy updated to grant Planner access
- [ ] Backend: Research findings stored in workflow state
- [ ] Tests: Unit tests for MCP servers
- [ ] Tests: Integration tests with rate limiting

**Acceptance Criteria**:
1. **Given** user asks about "latest React patterns", **When** Planner researches, **Then** current 2025 information is included
2. **Given** dependency is mentioned, **When** research runs, **Then** official documentation is consulted
3. **Given** rate limit exceeded, **When** search attempted, **Then** graceful degradation with cached results

**Dependencies**: CORE-003 (MCP Client)

---

#### Story 13.8: Iterative Planning Refinement

**As a** Product Owner,
**I want** to refine the plan through multiple iterations,
**So that** I can progressively improve the requirements.

**Task ID**: INTERACT-008
**Priority**: P1
**Phase**: 10

**Definition of Done**:
- [ ] Backend: Support for "back to interview" from any planning phase
- [ ] Backend: State preservation when returning to earlier phases
- [ ] Backend: Version history of PRD iterations
- [ ] Frontend: "Refine Further" button at each approval gate
- [ ] Frontend: Version selector to compare PRD iterations
- [ ] Frontend: Diff view showing changes between versions
- [ ] Tests: E2E test for multi-iteration workflow

**Acceptance Criteria**:
1. **Given** PRD v1 is displayed, **When** user clicks "Refine", **Then** interview resumes with context
2. **Given** PRD v2 is generated, **When** comparing to v1, **Then** diff shows changes
3. **Given** 3 iterations exist, **When** user selects v2, **Then** that version is displayed for comparison

**Dependencies**: INTERACT-003

---

### PHASE C: Polish and Optimization (Post-MVP)

---

#### Story 13.9: Workflow Progress Dashboard

**As a** Product Owner,
**I want** a visual dashboard showing workflow progress,
**So that** I always know where we are in the process.

**Task ID**: INTERACT-009
**Priority**: P2
**Phase**: 11

**Definition of Done**:
- [ ] Frontend: `WorkflowDashboard.tsx` component
- [ ] Frontend: Visual state machine showing:
  - Interview → Roundtable → PRD → Tasks → Execution → Validation → Deploy
- [ ] Frontend: Current phase highlighted
- [ ] Frontend: Phase descriptions on hover
- [ ] Frontend: Time spent in each phase
- [ ] Frontend: Phase-specific success criteria checklist
- [ ] Tests: Visual regression tests

**Dependencies**: All INTERACT-001 through INTERACT-004

---

#### Story 13.10: Inline PRD Editing

**As a** Product Owner,
**I want** to edit the PRD directly in the UI,
**So that** I can make quick adjustments without full regeneration.

**Task ID**: INTERACT-010
**Priority**: P2
**Phase**: 11

**Definition of Done**:
- [ ] Frontend: Inline markdown editor for PRD sections
- [ ] Frontend: Real-time preview of changes
- [ ] Backend: Endpoint to save PRD modifications
- [ ] Backend: Re-validation of modified PRD
- [ ] Frontend: "Save Changes" and "Discard" buttons
- [ ] Tests: Unit tests for inline editor

**Dependencies**: INTERACT-002, INTERACT-003

---

#### Story 13.11: Real-time Persona Collaboration Indicators

**As a** Product Owner,
**I want** to see which AI persona is currently "speaking",
**So that** I understand who is providing feedback.

**Task ID**: INTERACT-011
**Priority**: P2
**Phase**: 11

**Definition of Done**:
- [ ] Frontend: Persona avatars with "speaking" animation
- [ ] Frontend: Persona name badge on each message
- [ ] Backend: WebSocket events include `persona_id`
- [ ] Frontend: "Planner is thinking...", "CTO is reviewing..."
- [ ] Tests: Visual tests for persona indicators

**Dependencies**: INTERACT-002

---

#### Story 13.12: Dependency Resolver MCP Server

**As a** Planner Agent,
**I want** to check package dependencies and versions,
**So that** I can recommend compatible technology stacks.

**Task ID**: INTERACT-012
**Priority**: P2
**Phase**: 11

**Definition of Done**:
- [ ] Backend: `DependencyResolverMCPServer` created
- [ ] Backend: Tools: `check_package_version`, `find_conflicts`, `get_latest_version`
- [ ] Backend: Support for npm, PyPI, Cargo registries
- [ ] Backend: Caching for frequent lookups
- [ ] Tests: Unit tests with mock registry responses

**Dependencies**: INTERACT-007

---

## Phase Summary

| Phase | Stories | Priority | MVP Required |
|-------|---------|----------|--------------|
| A | 13.1, 13.2, 13.3, 13.4 | P0 | YES |
| B | 13.5, 13.6, 13.7, 13.8 | P1 | RECOMMENDED |
| C | 13.9, 13.10, 13.11, 13.12 | P2 | NO |

---

## MVP Decision Framework

### Current MVP Status: INCOMPLETE

**What Works**:
- User can send a message
- Backend generates PRD and tasks (black box)
- User sees final output in chat
- Deployment approval exists

**What's Missing for True MVP**:
- User cannot answer clarifying questions → INTERACT-001
- User cannot see/approve PRD → INTERACT-002, INTERACT-003
- User cannot review tasks before execution → INTERACT-004

### Recommendation

| Option | Stories Required | Timeline Est. |
|--------|------------------|---------------|
| **Minimal MVP** | INTERACT-001, 002, 003 | 1 week |
| **Complete MVP** | Phase A (001-004) | 2 weeks |
| **Production Ready** | Phase A + B | 3-4 weeks |
| **Full Feature Set** | All Phases | 5-6 weeks |

**Recommended Path**: Complete Phase A (INTERACT-001 through INTERACT-004) before calling MVP complete. Without these, users cannot meaningfully interact with the planning system.

---

## Task Dependencies Graph

```
                     ┌──────────────┐
                     │  INTERACT-001│
                     │  Interview   │
                     └──────┬───────┘
                            │
                     ┌──────▼───────┐
           ┌─────────│  INTERACT-002│─────────┐
           │         │  PRD Display │         │
           │         └──────┬───────┘         │
           │                │                 │
    ┌──────▼───────┐ ┌──────▼───────┐ ┌───────▼──────┐
    │  INTERACT-005│ │  INTERACT-003│ │  INTERACT-006│
    │  Research    │ │  PRD Approval│ │  Complexity  │
    └──────────────┘ └──────┬───────┘ └──────────────┘
                            │
                     ┌──────▼───────┐
                     │  INTERACT-004│
                     │  Task Review │
                     └──────┬───────┘
                            │
                     ┌──────▼───────┐
                     │  INTERACT-008│
                     │  Refinement  │
                     └──────────────┘

Standalone (can parallel):
- INTERACT-007 (Web Research) - depends only on CORE-003
- INTERACT-009 (Dashboard) - depends on Phase A complete
- INTERACT-010 (Inline Edit) - depends on 002, 003
- INTERACT-011 (Personas) - depends on 002
- INTERACT-012 (Dependencies) - depends on 007
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| User answers clarifying questions | 100% of sessions | Track interview completions |
| PRD approval rate (first attempt) | >= 70% | Approvals / Total PRDs |
| Task approval rate | >= 80% | Approvals / Total decompositions |
| Time to PRD approval | < 10 minutes | Timer from start to approval |
| User satisfaction (survey) | >= 4/5 | Post-session survey |
| Iteration count (avg) | <= 2 | Track refinement loops |

---

*Document generated: 2025-12-31*
*For review: Morning session*
*Next action: Prioritize and assign to development wave*
