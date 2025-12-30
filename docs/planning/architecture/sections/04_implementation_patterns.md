# 04. Implementation Patterns & Consistency Rules

## Implementation Patterns

### 1. The "Double Entry" Verification Pattern
Every code generation action is paired with a verification action.
-   **Step A (Write)**: Agent generates code.
-   **Step B (Verify)**: System *automatically* runs the code in E2B.
-   **constraint**: The Workflow State cannot transition to "Complete" unless Step B returns exit code 0.

### 2. The "Context Compaction" Pattern
To manage context window limits:
-   **Pre-computation**: Before a task starts, the "Librarian Agent" queries Neo4j for *only* the relevant file nodes.
-   **Summary injection**: Past conversation turns are summarized into a concise "Activity Log" injected into the system prompt.

### 3. The "Tool-First" Design
Agents are *never* allowed to hallucinate file reads. They must use the `read_file` tool.
-   **Enforcement**: The System Prompt explicitly disables "guessing" implementation details.

### 4. The "Monitor-Diagnose-Heal" Loop
A self-healing operational loop:
-   **Monitor**: Detects "Agentic Drift" (looping, unexpected tool usage).
-   **Diagnose**: Uses RAG to find similar past errors and suggests a fix.
-   **Heal**: Attempts to apply a patch and verify it in a fresh sandbox.

## Consistency Rules

### Code Organization
-   **Agents**: Defined in `packages/daw-agents/src/daw_agents/agents/{agent_name}/`. Each agent module contains:
    -   `agent.py` - Main agent class and LangGraph workflow definition
    -   `nodes.py` - Individual workflow node implementations
    -   `state.py` - TypedDict state definitions for the workflow
    -   `models.py` - Agent-specific Pydantic models (optional)
-   **Prompts**: Stored separately in `packages/daw-agents/prompts/{agent_name}/` with semantic versioning (e.g., `prd_generator_v1.0.yaml`)
-   **Schema First**: All agent interactions are typed using `Pydantic` models in `packages/daw-agents/src/daw_agents/schemas/`.

### Error Handling
-   **Agent Level**: If an agent tool call fails, the `ToolNode` catches the exception and feeds the error message back to the agent for a "Self-Correction" attempt (max 3 retries).
-   **System Level**: If the graph gets stuck, the State is checkpointed, and a "Human Intervention" alert is fired.

### Security Architecture
-   **Sandboxing**: All untrusted code (Agent output) runs in **E2B**.
-   **Secret Management**: Secrets (API Keys) are injected into the E2B sandbox environment variables *only* at runtime. They are never written to disk or logs.
-   **Input Sanitization**: User prompts are scanned for "Jailbreak" patterns before being sent to the LLM.

---

## 5. Prompt Template Governance

### Version Control Requirements
All prompts are treated as code artifacts with full version control:
-   Stored in `packages/daw-agents/{agent}/prompts/`
-   Versioned with semantic versioning (e.g., `prd_generator_v1.2.yaml`)
-   Changes require PR review by designated "Prompt Engineers"
-   Changelog maintained for each prompt file

### Prompt Template Structure
```yaml
# packages/daw-agents/planner/prompts/prd_generator_v1.0.yaml
version: "1.0.0"
name: "PRD Generator"
persona: "Senior Product Manager"

system_prompt: |
  You are a Senior Product Manager responsible for...

validation_checklist:
  - "Does the output contain all required sections?"
  - "Are there any hallucinated file references?"
  - "Does the JSON schema validate?"
  - "Are error handling requirements included?"
  - "Are security considerations documented?"

output_schema:
  type: object
  required: [title, overview, requirements, stories]
  properties:
    title: { type: string }
    overview: { type: string }
    # ... additional schema
```

### Prompt Testing Harness
-   Golden input/output pairs stored in `tests/prompts/`
-   CI runs prompt regression tests on every change
-   Semantic similarity scoring against golden outputs
-   Automated schema validation for structured outputs

---

## 6. Validator Agent Pattern

### Separation from Sandbox
The Validator Agent is architecturally distinct from the Sandbox:

| Component | Sandbox | Validator Agent |
|-----------|---------|-----------------|
| Purpose | Isolated execution | Quality assurance |
| Intelligence | Passive container | Active reasoning |
| Model | None | Separate from Executor |
| Output | Raw results | Pass/fail with reasoning |

### Validator Agent Architecture
```
packages/daw-agents/
├── src/daw_agents/agents/validator/
│   ├── __init__.py           # Agent exports
│   ├── agent.py              # Main ValidatorAgent class with LangGraph workflow
│   ├── nodes.py              # Workflow nodes (run_tests, security_scan, etc.)
│   ├── state.py              # ValidatorState TypedDict
│   ├── models.py             # ValidationResult, Finding models
│   └── ensemble.py           # Multi-model validation ensemble
└── prompts/validator/
    └── validator_v1.yaml     # Validation persona and checklists
```

### Validation Workflow (LangGraph)
```python
# Simplified validation state machine
States:
  - run_tests        # Execute test suites
  - security_scan    # SAST/SCA analysis
  - policy_check     # Compliance validation
  - generate_report  # Actionable feedback
  - route_decision   # Pass/Retry/Escalate

Transitions:
  run_tests → security_scan (always)
  security_scan → policy_check (always)
  policy_check → generate_report (always)
  generate_report → route_decision (conditional)

route_decision:
  if all_passed → END
  if fixable AND retries < 3 → executor (retry)
  if critical OR retries >= 3 → human_review (escalate)
```

### Multi-Model Bias Prevention
-   Executor Agent: Uses Model A (e.g., Claude Sonnet)
-   Validator Agent: Uses Model B (e.g., GPT-4o) to avoid bias
-   Critical validations use ensemble of 2+ models

---

## 7. Self-Evolution Patterns

### 7.1 Experience-Driven Learning Pattern
A foundation for autonomous improvement based on stored execution history.

#### Neo4j Experience Schema
```cypher
// Experience node - created after every task completion
CREATE (:Experience {
  id: randomUUID(),
  task_type: "coding",           // planning | coding | validation
  task_id: "CORE-003",           // reference to tasks.json
  success: true,
  prompt_version: "executor_v1.2",
  model_used: "claude-sonnet-4-20250514",
  tokens_used: 5000,
  cost_usd: 0.045,
  duration_ms: 12500,
  retries: 0,
  timestamp: datetime()
})

// Skill relationship - links experiences to reusable patterns
(:Experience)-[:USED_SKILL]->(:Skill {
  name: "pytest_async_fixture",
  pattern: "@pytest.fixture\nasync def ...",
  success_rate: 0.95,
  usage_count: 47
})

// Artifact relationship - links to outputs produced
(:Experience)-[:PRODUCED]->(:Artifact {
  type: "code",
  path: "packages/daw-agents/src/mcp/client.py",
  lines_added: 150,
  test_coverage: 0.82
})

// Insight relationship - reflection results
(:Experience)-[:REFLECTED_AS]->(:Insight {
  what_worked: "Using httpx async client with timeout",
  what_failed: null,
  lesson_learned: "Always set explicit timeout for network calls",
  timestamp: datetime()
})
```

#### Experience Logger Architecture
```
packages/daw-agents/src/daw_agents/evolution/
├── __init__.py
├── experience_logger.py    # ExperienceLogger class
├── reflection.py           # ReflectionHook for post-task learning
├── schemas.py              # Pydantic models for Experience, Skill, Insight
├── queries.py              # Neo4j Cypher queries (if separate)
└── metrics.py              # Success rate calculations (if separate)
```

#### ExperienceLogger Interface
```python
class ExperienceLogger:
    """Stores and queries task execution experiences in Neo4j."""

    async def log_success(
        self,
        task_id: str,
        task_type: TaskType,
        prompt_version: str,
        model_used: str,
        tokens_used: int,
        cost_usd: float,
        duration_ms: int,
        skills_used: list[str] = None,
        artifacts: list[Artifact] = None
    ) -> Experience: ...

    async def log_failure(
        self,
        task_id: str,
        task_type: TaskType,
        error_type: str,
        error_message: str,
        retries: int,
        ...
    ) -> Experience: ...

    async def query_similar_experiences(
        self,
        task_type: TaskType,
        limit: int = 5
    ) -> list[Experience]: ...

    async def get_success_rate(
        self,
        task_type: TaskType = None,
        model: str = None,
        prompt_version: str = None,
        time_window_days: int = 30
    ) -> float: ...
```

### 7.2 Reflection Hook Pattern
Proactive learning triggered after task completion.

#### Integration Point
The Reflection Hook integrates with LangGraph as a callback:

```python
from langgraph.graph import StateGraph
from daw_agents.evolution.reflection import ReflectionHook

# Register reflection hook with orchestrator
orchestrator = StateGraph(OrchestratorState)
reflection_hook = ReflectionHook(
    experience_logger=experience_logger,
    model_router=model_router,
    depth="standard"  # quick | standard | deep
)

# Hook fires after each task completion
orchestrator.add_edge("task_complete", reflection_hook.reflect)
```

#### Reflection Workflow
```
┌─────────────────────────────────────────────────────────────────┐
│                    REFLECTION HOOK FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Task Completes (success or failure)                             │
│           ↓                                                      │
│  ReflectionHook.reflect() triggered (async, non-blocking)        │
│           ↓                                                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ REFLECTION PROMPT:                                          │ │
│  │                                                             │ │
│  │ Given this task execution:                                  │ │
│  │ - Task: {task_description}                                  │ │
│  │ - Outcome: {success/failure}                                │ │
│  │ - Duration: {duration_ms}ms                                 │ │
│  │ - Retries: {retries}                                        │ │
│  │                                                             │ │
│  │ Reflect on:                                                 │ │
│  │ 1. What worked well?                                        │ │
│  │ 2. What patterns should be remembered?                      │ │
│  │ 3. What could be improved next time?                        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│           ↓                                                      │
│  LLM generates Insight                                           │
│           ↓                                                      │
│  Store (:Experience)-[:REFLECTED_AS]->(:Insight) in Neo4j        │
│           ↓                                                      │
│  Main workflow continues (reflection was non-blocking)           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Reflection Depth Modes

| Mode | Overhead | Trigger | Output |
|------|----------|---------|--------|
| `quick` | ~100ms | Always | Metrics only (no LLM call) |
| `standard` | ~2s | Always | Single LLM reflection |
| `deep` | ~10s | On significant events | Multi-model consensus |

### 7.3 Future Evolution Hooks (Placeholder Architecture)

Reserved integration points for Phase 2+ capabilities:

```
packages/daw-agents/src/daw_agents/evolution/
├── experience_logger.py    # Phase 1 (EVOLVE-001) ✓
├── reflection.py           # Phase 1 (EVOLVE-002) ✓
├── schemas.py              # Phase 1 - shared models ✓
├── skill_extractor.py      # Phase 2 (EVOLVE-003) - placeholder
├── skill_library.py        # Phase 2 (EVOLVE-004) - placeholder
├── prompt_optimizer.py     # Phase 3 (EVOLVE-005) - placeholder
└── constitutional.py       # Phase 3 (EVOLVE-006) - placeholder
```

**Design Principle**: Phase 1 creates the data foundation (experiences, insights) that Phase 2-3 will consume for skill extraction and prompt optimization.
