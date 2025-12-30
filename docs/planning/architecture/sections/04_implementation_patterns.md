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
-   **Agents**: Defined in `packages/daw-agents`. Each agent has a `graph.py` (workflow), `prompts.yaml` (instructions), and `tools.py` (capabilities).
-   **Schema First**: All agent interactions are typed using `Pydantic` models.

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
packages/daw-agents/validator/
├── graph.py              # LangGraph validation workflow
├── tools.py              # Test runner, SAST, SCA integrations
├── prompts/
│   └── validator_v1.yaml # Validation persona and checklists
└── schemas/
    └── validation_result.py  # Pydantic models for results
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
