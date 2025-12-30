# Product Requirements Document: ToDo Application

**Version**: 1.0.0
**Status**: Golden Benchmark PRD
**Complexity**: Low-Medium
**Category**: Productivity Application

---

## 1. Overview

Build a command-line ToDo application that allows users to manage tasks with CRUD operations. This benchmark validates the DAW system's ability to handle state management, data persistence, and basic entity relationships.

---

## 2. User Stories

### US-001: Create Task
**Priority**: P0
**As a** user
**I want to** create a new task with a title
**So that** I can track things I need to do

**Acceptance Criteria**:
- Task created with unique ID (auto-generated)
- Task has required title (non-empty string)
- Task created with status "pending" by default
- Task created with current timestamp
- Optional description field

### US-002: List Tasks
**Priority**: P0
**As a** user
**I want to** view all my tasks
**So that** I can see what needs to be done

**Acceptance Criteria**:
- Display all tasks with ID, title, status, and created date
- Support filtering by status (pending, completed, all)
- Empty list message when no tasks exist
- Tasks ordered by creation date (newest first)

### US-003: View Task Details
**Priority**: P1
**As a** user
**I want to** view details of a specific task
**So that** I can see full information

**Acceptance Criteria**:
- Display task ID, title, description, status, created_at, updated_at
- Show error message if task not found
- Display completion date if task is completed

### US-004: Update Task
**Priority**: P0
**As a** user
**I want to** update task title or description
**So that** I can correct or add details

**Acceptance Criteria**:
- Update title (non-empty string validation)
- Update description (optional, can be empty)
- Update sets updated_at timestamp
- Cannot update non-existent task
- Return updated task details

### US-005: Complete Task
**Priority**: P0
**As a** user
**I want to** mark a task as completed
**So that** I can track my progress

**Acceptance Criteria**:
- Change status from "pending" to "completed"
- Set completed_at timestamp
- Cannot complete already completed task (idempotent or error)
- Cannot complete non-existent task

### US-006: Delete Task
**Priority**: P0
**As a** user
**I want to** delete a task
**So that** I can remove tasks I no longer need

**Acceptance Criteria**:
- Remove task from storage
- Return confirmation of deletion
- Cannot delete non-existent task
- Soft delete option (mark as deleted vs remove)

### US-007: Reopen Task
**Priority**: P1
**As a** user
**I want to** reopen a completed task
**So that** I can continue working on it

**Acceptance Criteria**:
- Change status from "completed" to "pending"
- Clear completed_at timestamp
- Cannot reopen pending task
- Update updated_at timestamp

### US-008: Add Due Date
**Priority**: P2
**As a** user
**I want to** set a due date for a task
**So that** I can track deadlines

**Acceptance Criteria**:
- Optional due_date field (datetime)
- Validate date is in the future when setting
- List tasks can filter by overdue
- Display warning for overdue tasks

### US-009: Data Persistence
**Priority**: P0
**As a** user
**I want my** tasks to persist between sessions
**So that** I don't lose my data

**Acceptance Criteria**:
- Tasks saved to JSON file
- Tasks loaded on application start
- Handle corrupted file gracefully
- Create new file if not exists

---

## 3. Technical Requirements

### 3.1 Technology Stack
- **Language**: Python 3.11+
- **Data Storage**: JSON file (tasks.json)
- **Testing**: pytest
- **Linting**: ruff
- **Type Checking**: mypy

### 3.2 Architecture

```
todo_app/
├── src/
│   └── todo/
│       ├── __init__.py
│       ├── models.py        # Task model and enums
│       ├── repository.py    # Data persistence (JSON)
│       ├── service.py       # Business logic
│       └── exceptions.py    # Custom exceptions
├── tests/
│   └── test_todo/
│       ├── __init__.py
│       ├── test_models.py
│       ├── test_repository.py
│       └── test_service.py
├── data/
│   └── tasks.json           # Data file (created at runtime)
└── pyproject.toml
```

### 3.3 Data Model

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

class TaskStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"

class Task(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    due_date: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = None
    completed_at: datetime | None = None
```

### 3.4 API Design

```python
# service.py
class TodoService:
    def __init__(self, repository: TaskRepository) -> None: ...

    def create_task(self, title: str, description: str = "") -> Task: ...
    def get_task(self, task_id: UUID) -> Task: ...
    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]: ...
    def update_task(self, task_id: UUID, title: str | None = None,
                    description: str | None = None) -> Task: ...
    def complete_task(self, task_id: UUID) -> Task: ...
    def reopen_task(self, task_id: UUID) -> Task: ...
    def delete_task(self, task_id: UUID) -> bool: ...

# repository.py
class TaskRepository:
    def __init__(self, file_path: str = "data/tasks.json") -> None: ...

    def save(self, task: Task) -> None: ...
    def find_by_id(self, task_id: UUID) -> Task | None: ...
    def find_all(self) -> list[Task]: ...
    def delete(self, task_id: UUID) -> bool: ...
    def _load(self) -> None: ...
    def _persist(self) -> None: ...

# exceptions.py
class TaskNotFoundError(Exception): ...
class InvalidTaskError(Exception): ...
class TaskAlreadyCompletedError(Exception): ...
```

---

## 4. Non-Functional Requirements

### 4.1 Performance
- All operations must complete in < 100ms
- Support up to 10,000 tasks in storage

### 4.2 Quality
- Test coverage >= 80%
- 0 linting errors
- 0 type errors
- All tests must pass

### 4.3 Reliability
- Graceful handling of corrupted data files
- Atomic file writes (temp file + rename)
- Backup creation before destructive operations

### 4.4 Documentation
- All public functions must have docstrings
- README with usage examples

---

## 5. Out of Scope

- Multi-user support
- Categories/tags
- Task priorities
- Subtasks
- Web or mobile interface
- Database storage (SQLite, PostgreSQL)

---

## 6. Success Criteria

| Metric | Target |
|--------|--------|
| Test Coverage | >= 80% |
| Lint Errors | 0 |
| Type Errors | 0 |
| All Tests Pass | Yes |
| Task Completion | 100% |
| CRUD Operations | All working |

---

*Golden Benchmark PRD for DAW Evaluation System*
