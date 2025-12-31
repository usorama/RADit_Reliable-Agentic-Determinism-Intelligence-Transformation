# 06. Epic 13+ Architecture Components

**Version**: 1.0
**Last Updated**: 2025-12-31
**Status**: Implementation Ready

---

## Overview

This section documents the new architectural components introduced in Epic 13 through Epic 17, building upon the existing DAW foundation.

---

## New Orchestrator States

The Orchestrator state machine is extended to support user approval gates and self-healing workflows.

### Extended OrchestratorStatus Enum

```python
class OrchestratorStatus(str, Enum):
    # Existing States
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    DEPLOYING = "deploying"
    COMPLETED = "completed"
    ERROR = "error"

    # New States (Epic 13 - User Interaction)
    AWAITING_INTERVIEW = "awaiting_interview"          # Waiting for user to answer questions
    AWAITING_PRD_APPROVAL = "awaiting_prd_approval"    # PRD generated, awaiting user approval
    AWAITING_TASK_APPROVAL = "awaiting_task_approval"  # Tasks decomposed, awaiting user approval

    # New States (Epic 15 - Monitor-Diagnose-Heal)
    MONITORING = "monitoring"        # Post-deployment health monitoring
    DIAGNOSING = "diagnosing"        # Analyzing detected error
    HEALING = "healing"              # Applying automated fix
    ESCALATING = "escalating"        # Unfixable error, human needed
```

### State Transition Diagram

```
                    PENDING
                       |
                       v
    +---------------> PLANNING
    |                  |
    |                  v
    |          AWAITING_INTERVIEW <--+
    |                  |             |
    |                  v             |
    |       AWAITING_PRD_APPROVAL ---+ (reject)
    |                  |
    |                  v (approve)
    |       AWAITING_TASK_APPROVAL --+ (reject back to planning)
    |                  |
    |                  v (approve)
    |              EXECUTING
    |                  |
    |                  v
    |              VALIDATING
    |                  |
    |                  v
    |              DEPLOYING
    |                  |
    |                  v
    |              COMPLETED --> MONITORING
    |                               |
    |                               v (anomaly detected)
    |                           DIAGNOSING
    |                               |
    +------ (fixed) <---------- HEALING
                                    |
                                    v (unfixable)
                                ESCALATING
```

---

## New Backend Endpoints (Epic 13)

### Interview Endpoints

```
POST /api/workflow/{workflow_id}/interview-answer
    Request:
        { "question_id": str, "answer": str | list[str], "skip_remaining": bool }
    Response:
        { "next_question": Question | null, "complete": bool }

GET /api/workflow/{workflow_id}/interview-status
    Response:
        { "current_question": int, "total_questions": int, "questions": Question[] }
```

### PRD Review Endpoints

```
POST /api/workflow/{workflow_id}/prd-review
    Request:
        { "action": "approve" | "reject" | "modify", "feedback": str | null }
    Response:
        { "status": OrchestratorStatus, "prd": PRD | null }

GET /api/workflow/{workflow_id}/prd
    Response:
        { "prd": PRD, "personas_feedback": PersonaFeedback[], "version": int }
```

### Task Review Endpoints

```
POST /api/workflow/{workflow_id}/tasks-review
    Request:
        { "action": "approve" | "reject", "feedback": str | null }
    Response:
        { "status": OrchestratorStatus }

GET /api/workflow/{workflow_id}/tasks
    Response:
        { "phases": Phase[], "stories": Story[], "tasks": Task[], "dependencies": Dependency[] }
```

### Kanban Endpoints

```
GET /api/workflow/{workflow_id}/kanban
    Response:
        { "columns": Column[], "tasks": KanbanTask[], "stats": Stats }

PATCH /api/workflow/{workflow_id}/kanban/{task_id}
    Request:
        { "column": str, "priority": int | null }
    Response:
        { "task": KanbanTask }
```

---

## New Frontend Components

### Directory Structure

```
apps/web/src/components/
├── plan/
│   ├── ClarificationFlow.tsx      # INTERACT-001
│   ├── PlanPresentation.tsx       # INTERACT-002
│   ├── ApprovalGate.tsx           # INTERACT-003
│   ├── TaskList.tsx               # INTERACT-004
│   └── ResearchDisplay.tsx        # INTERACT-005 (Production)
├── kanban/
│   ├── KanbanBoard.tsx            # KANBAN-001
│   ├── TaskCard.tsx               # KANBAN-001
│   ├── TaskDetailPanel.tsx        # KANBAN-002
│   └── ColumnHeader.tsx           # KANBAN-001
├── dashboard/
│   └── MetricsDashboard.tsx       # KANBAN-006 (Production)
└── hooks/
    ├── useInterview.ts            # Interview state management
    ├── usePRD.ts                  # PRD state management
    ├── useKanban.ts               # Kanban WebSocket subscription
    └── useWorkflowStatus.ts       # Workflow status polling
```

### Component Specifications

#### ClarificationFlow.tsx (INTERACT-001)
```typescript
interface ClarificationFlowProps {
    workflowId: string;
    onComplete: () => void;
}

// Features:
// - Question display with type-specific inputs (text, multi-choice, checkbox)
// - Progress indicator ("Question 2 of 4")
// - Skip button with confirmation
// - Auto-advance on answer
// - WCAG 2.1 AA accessibility
```

#### PlanPresentation.tsx (INTERACT-002)
```typescript
interface PlanPresentationProps {
    workflowId: string;
    prd: PRD;
    personasFeedback: PersonaFeedback[];
}

// Features:
// - Expandable sections: Overview, User Stories, Tech Specs, Acceptance Criteria, NFRs
// - Persona avatars with critique display
// - Complexity badges
// - Export to PDF button
// - Screen reader compatible
```

#### ApprovalGate.tsx (INTERACT-003)
```typescript
interface ApprovalGateProps {
    workflowId: string;
    artifactType: 'prd' | 'tasks';
    onApprove: () => void;
    onReject: (feedback: string) => void;
}

// Features:
// - Approve / Reject / Request Changes buttons
// - Comment textarea for feedback
// - Confirmation modal before actions
// - Status indicator
```

#### KanbanBoard.tsx (KANBAN-001)
```typescript
interface KanbanBoardProps {
    workflowId: string;
}

// Features:
// - 6 columns: Backlog, Planning, Coding, Validating, Deploying, Done
// - Task cards with drag-drop (Production)
// - Real-time WebSocket updates
// - Column task counts
// - Connection status indicator
```

---

## New MCP Servers (packages/daw-mcp/)

### Web Research MCP Server (INTERACT-007)

```python
# packages/daw-mcp/src/daw_mcp/servers/web_research.py

class WebResearchMCPServer:
    """MCP server for web research capabilities."""

    tools = [
        "web_search",      # Search the web for information
        "fetch_page",      # Fetch and parse a web page
        "summarize_url",   # Summarize content from a URL
        "search_docs",     # Search Context7 for library docs
    ]

    # Rate limits: 10 requests/minute per agent
    # Cache: 15 minute TTL for URL fetches
```

### Model Driver MCP Server (DRIVER-002)

```python
# packages/daw-mcp/src/daw_mcp/servers/model_driver.py

class ModelDriverMCPServer:
    """MCP server for model configuration and introspection."""

    tools = [
        "list_models",       # List available model drivers
        "get_model_config",  # Get configuration for a model
        "estimate_cost",     # Estimate cost for a task
        "recommend_model",   # Get model recommendation by task type
    ]
```

### Sentinel MCP Server (MDH-005 - Future)

```python
# packages/daw-mcp/src/daw_mcp/servers/sentinel.py

class SentinelMCPServer:
    """MCP server for risk scanning and interception."""

    tools = [
        "scan_command",      # Check if command is risky
        "request_approval",  # Request human approval
        "log_interception",  # Log intercepted operation
    ]
```

---

## WebSocket Events

### Interview Events

```typescript
// Server -> Client
{ type: "interview_question", question: Question }
{ type: "interview_complete" }

// Client -> Server
{ type: "interview_answer", questionId: string, answer: string | string[] }
{ type: "interview_skip" }
```

### PRD Events

```typescript
// Server -> Client
{ type: "prd_generated", prd: PRD }
{ type: "prd_status_change", status: "approved" | "rejected" }
```

### Kanban Events

```typescript
// Server -> Client
{ type: "kanban_update", taskId: string, newColumn: string, timestamp: string }
{ type: "kanban_sync", tasks: KanbanTask[] }
{ type: "kanban_agent_activity", agentId: string, taskId: string, action: string }
```

---

## Data Models

### Interview Models

```python
class Question(BaseModel):
    id: str
    type: Literal["text", "multi_choice", "checkbox"]
    text: str
    options: list[str] | None = None  # For multi_choice/checkbox
    required: bool = True
    context: str | None = None  # Help text

class InterviewState(BaseModel):
    workflow_id: str
    questions: list[Question]
    answers: dict[str, str | list[str]]
    current_index: int
    completed: bool = False
```

### Kanban Models

```python
class KanbanColumn(str, Enum):
    BACKLOG = "backlog"
    PLANNING = "planning"
    CODING = "coding"
    VALIDATING = "validating"
    DEPLOYING = "deploying"
    DONE = "done"

class KanbanTask(BaseModel):
    id: str
    title: str
    description: str
    column: KanbanColumn
    priority: int
    assigned_agent: str | None
    dependencies: list[str]
    artifacts: list[str]
    updated_at: datetime
```

---

## Integration Points

### Existing Components Modified

| Component | File | Change |
|-----------|------|--------|
| Orchestrator | `orchestrator/orchestrator.py` | Add new states, approval gates |
| Taskmaster | `agents/planner/taskmaster.py` | Modify `_interview_node` for real responses |
| WebSocket | `api/websocket.py` | Add new event types |
| API Router | `api/routes.py` | Add new endpoints |

### New Dependencies

```toml
# packages/daw-agents/pyproject.toml additions
weasyprint = "^62.0"  # PDF export for PRD
httpx = "^0.27.0"     # Web research HTTP client

# apps/web/package.json additions
"@dnd-kit/core" = "^6.1.0"  # Drag-and-drop for Kanban
"html2pdf.js" = "^0.10.1"   # PDF export in browser
```

---

## Related Documents

- **Master Epic Plan**: `docs/planning/epics/epic_13_through_16_master_plan.md`
- **Functional Requirements**: `docs/planning/prd/sections/02_functional_requirements.md`
- **MVP Scope**: `docs/planning/prd/sections/06_mvp_scope_definition.md`

---

*Version 1.0 | 2025-12-31 | Status: Implementation Ready*
