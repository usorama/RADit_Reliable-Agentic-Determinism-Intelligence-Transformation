# Gap Analysis Report: PRD vs Research Paper Requirements

**Date**: 2025-12-30
**Status**: Complete
**Reviewer**: Deterministic Agentic Architect
**Source Reference**: `docs/research/Deterministic SSDLC for Digital Products.md`

---

## Executive Summary

This report analyzes the alignment between the current BMAD documentation (PRD, Architecture, Test Strategy) and the requirements defined in the research paper "Deterministic Agentic Engineering". **8 gaps were identified and validated**, ranging from critical architectural concerns to documentation deficiencies.

**Overall Assessment**: The existing documentation provides a strong foundation but requires enhancements to meet the full deterministic SSDLC requirements. Priority should be given to Gaps 1, 4, and 6 as they directly impact the core determinism guarantees.

---

## Gap Summary

| # | Gap | Severity | Research Paper Ref | Current State | Remediation Priority |
|---|-----|----------|-------------------|---------------|---------------------|
| 1 | Validator Agent vs Sandbox | **Critical** | Lines 55-61 | Conflated | P0 |
| 2 | Complexity Analysis Artifact | **High** | Lines 105-107 | Missing | P1 |
| 3 | Version-controlled Prompt Templates | **High** | Lines 113-118 | Underspecified | P1 |
| 4 | Policy-as-Code Deployment Gating | **Critical** | Lines 193-196 | Generic | P0 |
| 5 | UAT Automation Specificity | **High** | Lines 235-237 | Vague | P1 |
| 6 | Eval Protocol / Benchmark Scoring | **Critical** | Lines 251 | Missing | P0 |
| 7 | Drift Detection Metrics | **Medium** | Lines 218-223 | Undefined | P2 |
| 8 | Hardened MCP Gateway Authorization | **High** | Lines 185-191 | Underspecified | P1 |

---

## Gap 1: Validator Agent vs Sandbox (CRITICAL)

### Research Paper Requirement (Lines 55-61)

> "An Agent OS separates these concerns into distinct roles:
> - **The Planner Agent**: Typically running on a high-reasoning model like o1 or Claude 3.5 Sonnet, responsible for generating strategy.
> - **The Executor Agent**: Running on faster, more cost-effective models, takes an atomic task and executes it.
> - **The Validator Agent**: Running on a **distinct model to avoid bias**, checks the work of the Executor. It runs tests, linters, and security scans. If the work fails validation, it rejects the task."

### Current State

**PRD FR-04** (lines 26-29) defines:
```
## FR-04: Secure Sandbox (The Validator)
-   FR-04.1 Ephemeral Environments: Integration with E2B or Docker Containers.
-   FR-04.2 Network Isolation: Sandbox has restricted internet access.
-   FR-04.3 Resource Limits: CPU/RAM caps to prevent infinite loops.
```

The current specification **conflates the sandbox (execution environment) with the validator (intelligent agent)**. The sandbox is a passive container; the Validator Agent is an active, reasoning component that:
- Runs tests and interprets results
- Performs linting and security scans
- Makes pass/fail decisions with reasoning
- Routes work back for fixes or escalates to humans

### Impact

- No bias prevention (same model generates and validates)
- No intelligent interpretation of test failures
- No separation between execution isolation and quality assurance
- Missing policy compliance checks as first-class validation

### Remediation

**Add new FR-04.4 Validator Agent**:
```markdown
## FR-04: Validation & Quality Assurance

### FR-04.1 Secure Sandbox (Execution Environment)
- Ephemeral E2B/Docker environments for code execution
- Network isolation, resource caps, side-effect containment

### FR-04.2 Validator Agent (Quality Assurance - DISTINCT)
- Runs on a **separate model** from Executor to prevent bias
- Responsibilities:
  - Execute test suites (unit, integration)
  - Run SAST security scans
  - Perform dependency vulnerability checks
  - Validate policy compliance
  - Generate actionable improvement suggestions
- Retry logic: Route fixable failures back to Executor (max 3 retries)
- Escalation: Route critical/unfixable issues to human reviewers
```

**Architecture Update**:
Add `packages/daw-agents/validator/` with:
- `graph.py` - LangGraph validation workflow
- `tools.py` - Test runner, SAST, SCA integrations
- `prompts.yaml` - Validation persona prompts

---

## Gap 2: Complexity Analysis Artifact (HIGH)

### Research Paper Requirement (Lines 105-107)

> "Before a single line of code is written, the Agent OS performs a Complexity Analysis on the PRD. It estimates the 'Cognitive Load' required to implement various features and identifies potential risks, dependencies, and architectural bottlenecks."

### Current State

`readiness_review.md` (line 20) mentions:
```
- [x] **Complexity Assessment**: High complexity in the "Graph Memory" synchronization.
    - *Mitigation*: Start with a simple Vector-only memory for MVP.
```

This is an **informal note**, not a formal PRD requirement with:
- Defined output schema
- Acceptance criteria
- Integration with task sizing

### Impact

- Tasks may be incorrectly sized, leading to agent confusion
- No systematic risk identification before coding begins
- No guidance on model selection based on task complexity

### Remediation

**Add new FR-02.5 Complexity Analysis**:
```markdown
## FR-02.5 Complexity Analysis Engine
- **Input**: Approved PRD document
- **Output**: `complexity_analysis.json` artifact containing:
  - Feature-by-feature cognitive load scores (1-10)
  - Dependency graph with risk ratings
  - Recommended model tier per task (planning: o1/opus, coding: sonnet/haiku)
  - Architectural bottleneck warnings
- **Integration**: Complexity scores inform task decomposition in `tasks.json`
- **Acceptance Criteria**: Analysis must complete before task generation
```

---

## Gap 3: Version-Controlled Prompt Templates (HIGH)

### Research Paper Requirement (Lines 113-118)

> "To ensure the PRD generation and task decomposition are consistent, the system uses version-controlled **Prompt Templates**... The prompt includes instructions for the agent to review its own work against a checklist... before finalizing the output. This internal feedback loop significantly improves the quality."

### Current State

Architecture mentions `prompts.yaml` per agent but lacks:
- Version control governance
- Self-correction checklists
- Review/approval workflows for prompt changes
- Prompt testing harnesses

### Impact

- Prompt drift without traceability
- No quality gate for prompt updates
- Inconsistent agent behavior across versions

### Remediation

**Add to Architecture (04_implementation_patterns.md)**:
```markdown
## Prompt Template Governance

### Version Control Requirements
- All prompts stored in `packages/daw-agents/{agent}/prompts/`
- Prompts versioned with semantic versioning (e.g., `prd_generator_v1.2.yaml`)
- Changes require PR review by designated "Prompt Engineers"

### Self-Correction Checklists
Every prompt template must include a `validation_checklist` section:
```yaml
validation_checklist:
  - "Does the output contain all required sections?"
  - "Are there any hallucinated file references?"
  - "Does the JSON schema validate?"
  - "Are error handling requirements included?"
```

### Prompt Testing
- Golden input/output pairs stored in `tests/prompts/`
- CI runs prompt regression tests on every change
```

---

## Gap 4: Policy-as-Code Deployment Gating (CRITICAL)

### Research Paper Requirement (Lines 193-196)

> "The deployment pipeline itself is managed by the Agent OS using **Policy-as-Code**. Deployment rules are codified and enforced by a Validator Agent. Rules might include 'Must have 90% test coverage,' 'No high-severity vulnerabilities in dependencies,' and 'Must pass UAT scenarios.'"

### Current State

`05_deployment.md` is generic:
```
The DAW Platform itself is containerized using Docker.
- Service A: daw-backend
- Service B: daw-frontend
```

No mention of:
- Test coverage thresholds
- Vulnerability scan gates
- UAT pass requirements
- Zero-Copy Fork for migrations

### Impact

- Deployments may proceed with insufficient quality
- No programmatic enforcement of standards
- Risk of deploying vulnerable code

### Remediation

**Update 05_deployment.md with Policy-as-Code section**:
```markdown
## Deployment Quality Gates (Policy-as-Code)

### Gate 1: Code Quality (BLOCKING)
| Criterion | Threshold | Action |
|-----------|-----------|--------|
| Test Coverage (new code) | >= 80% | Block merge |
| Test Coverage (total) | >= 70% | Block release |
| TypeScript Strict Mode | Enabled | Block commit |

### Gate 2: Security (BLOCKING)
| Criterion | Threshold | Action |
|-----------|-----------|--------|
| SAST Critical Findings | 0 | Block merge |
| SAST High Findings | 0 | Block release |
| SCA Critical CVEs | 0 | Block merge |
| Secrets Detected | 0 | Block commit |

### Gate 3: UAT (BLOCKING for Production)
- All P0 acceptance criteria must pass
- Playwright UAT Agent must complete user journey validation
- Visual regression < 0.1% pixel difference

### Zero-Copy Fork for Migrations
- Database migrations must first apply to zero-copy fork
- Validation suite runs on fork
- Only after pass does migration apply to production
```

---

## Gap 5: UAT Automation Specificity (HIGH)

### Research Paper Requirement (Lines 235-237)

> "AI agents facilitate automated UAT by simulating real user personas. A UAT Agent might adopt the persona of a 'New Customer' and attempt to complete a user journey defined in the PRD. Using tools like **Playwright**, the agent 'sees' the screen and interacts with the UI."

### Current State

Story 3.2 mentions UAT but lacks:
- Specific tooling (Playwright not mentioned)
- Persona definitions
- How UAT outcomes gate releases
- Integration with deployment pipeline

### Impact

- No concrete path to automated UAT
- Manual testing bottleneck remains
- Business journeys not systematically validated

### Remediation

**Add FR-06: Automated UAT Agent**:
```markdown
## FR-06: Automated UAT Agent

### FR-06.1 Playwright Integration
- UAT Agent uses Playwright MCP for browser automation
- Operates on accessibility snapshots (not screenshots) for determinism

### FR-06.2 Persona-Based Testing
- Define user personas in `uat/personas.yaml`:
  - "Power User" - Desktop, fast network, keyboard shortcuts
  - "First-Time User" - Mobile, 3G, help-seeking behavior
  - "Accessibility User" - Screen reader, keyboard-only navigation

### FR-06.3 Business Journey Validation
- PRD acceptance criteria translated to Gherkin scenarios
- UAT Agent executes scenarios using Playwright MCP
- Generate validation reports with screenshots and traces

### FR-06.4 Release Gating
- UAT results feed into deployment quality gates
- P0 journey failures block production deployment
- P1 journey failures generate warnings, require approval
```

---

## Gap 6: Eval Protocol / Benchmark Scoring (CRITICAL)

### Research Paper Requirement (Line 251)

> "**Testing & Validation**: Pytest/Jest (Unit), Playwright (UAT), **Eval Protocol**: Eval Protocol scores agent performance against benchmarks."

### Current State

`test_strategy.md` mentions "Golden PRDs" but lacks:
- Defined eval protocol
- Scoring rubrics
- Pass/fail thresholds that gate releases
- Benchmark dataset definitions

### Impact

- No systematic measurement of agent quality
- No regression detection for agent performance
- No objective release criteria

### Remediation

**Add to test_strategy.md**:
```markdown
## 4. Eval Protocol (Agent Performance Benchmarking)

### 4.1 Golden PRD Benchmarks
- Maintain suite of 10-20 representative PRDs (e.g., "Calculator", "ToDo App", "E-commerce Checkout")
- Expected outputs (tests, code, architecture) stored as golden references
- Agent must achieve >= 85% similarity score on goldens

### 4.2 Performance Metrics
| Metric | Threshold | Gate Level |
|--------|-----------|------------|
| pass@1 (first attempt success) | >= 85% | Release blocking |
| Task Completion Rate | >= 90% | Release blocking |
| pass^8 (8-trial consistency) | >= 60% | Warning |
| Cost per Task | < $0.50 avg | Advisory |

### 4.3 Eval Harness
- Use DeepEval or Braintrust for evaluation framework
- CI integration runs eval suite nightly
- Performance regression > 5% triggers alert
- Results stored in eval_results/ with timestamped reports
```

---

## Gap 7: Drift Detection Metrics (MEDIUM)

### Research Paper Requirement (Lines 218-223)

> "**Drift Detection**: Agents can 'drift' over time as models change or context accumulates. We monitor metrics like 'Tool Usage Frequency' and 'Reasoning Step Count.' A sudden spike in the number of steps required to complete a simple task indicates that the agent is confused or looping."

### Current State

PRD FR-05.1 mentions drift:
```
FR-05.1 Monitor Agent: Inspects agent traces for "Looping" or "Drift"
```

But doesn't define:
- Specific metrics to measure
- Threshold values
- Alerting/actions on drift detection

### Impact

- Agent degradation may go undetected
- No proactive intervention before failures
- Difficult to diagnose performance issues

### Remediation

**Expand FR-05.1**:
```markdown
## FR-05.1 Monitor Agent (Drift Detection)

### Monitored Metrics
| Metric | Baseline | Alert Threshold | Action |
|--------|----------|-----------------|--------|
| Tool Usage Frequency | Per-task baseline | +50% deviation | Log warning |
| Reasoning Step Count | Average per task type | +100% increase | Pause agent |
| Context Window Utilization | Tracked per session | > 90% | Force compaction |
| Retry Rate | Per-task baseline | > 3x baseline | Escalate to human |
| Token Cost per Task | Historical average | +200% increase | Budget alert |

### Alerting
- Integrate with observability stack (Helicone, Datadog)
- Slack/Linear notifications for drift detection
- Weekly drift report generated automatically

### Actions
- Mild drift: Increase monitoring, log for analysis
- Moderate drift: Context compaction, model switch
- Severe drift: Pause agent, human intervention required
```

---

## Gap 8: Hardened MCP Gateway Authorization (HIGH)

### Research Paper Requirement (Lines 185-191)

> "MCP servers must be secured. A 'hardened' MCP gateway enforces authentication and authorization. An agent should not have carte blanche access to a database; it should have a scoped token that allows only specific actions (e.g., SELECT but not DROP). The gateway audits every tool call."

### Current State

PRD mentions schema validation and `.mcpignore`:
- FR-01.3: "Security validation of tool calls against a schema"
- Architecture: `.mcpignore` file patterns

Missing:
- Per-agent permission scoping
- OAuth 2.1 / RFC 8707 requirements
- Tool call audit logging
- Fine-grained RBAC for tools

### Impact

- Agents may have excessive permissions
- No audit trail for forensics/compliance
- Potential for privilege escalation attacks

### Remediation

**Add FR-01.3.2 MCP Security**:
```markdown
## FR-01.3 Tool Layer (MCP) - Security Requirements

### FR-01.3.1 MCP Gateway Authorization
- OAuth 2.1 with RFC 8707 Resource Indicators
- Per-agent scoped tokens (e.g., database agent: SELECT only, no DDL)
- Token TTL: 15 minutes for automated, 1 hour for interactive

### FR-01.3.2 RBAC for Tools
| Agent Role | Allowed Tools | Restrictions |
|------------|---------------|--------------|
| Planner | search, read_file, query_db (SELECT) | No writes |
| Executor | read_file, write_file, git_commit | write_file scoped to project dir |
| Validator | run_tests, security_scan, lint | No file writes |
| Healer | read_file, write_file (patches only) | Requires human approval for production |

### FR-01.3.3 Audit Logging
- Every tool call logged with:
  - Timestamp, agent_id, user_id
  - Tool name, action, parameters
  - Result status, response time
- Hash-chained logs for tamper resistance
- 7-year retention for compliance (SOC 2, ISO 27001)

### FR-01.3.4 Content Injection Prevention
- AI Prompt Shields for tool output sanitization
- Input validation against JSON schemas
- Blocked command patterns: DROP, DELETE, rm -rf, sudo
```

---

## Remediation Roadmap

### Phase 1: Critical Gaps (Weeks 1-2)
1. **Gap 1**: Add Validator Agent as distinct component
2. **Gap 4**: Implement Policy-as-Code deployment gates
3. **Gap 6**: Establish Eval Protocol with golden benchmarks

### Phase 2: High Priority Gaps (Weeks 3-4)
4. **Gap 2**: Add Complexity Analysis engine
5. **Gap 3**: Implement prompt template governance
6. **Gap 5**: Build UAT Agent with Playwright MCP
7. **Gap 8**: Harden MCP gateway with RBAC

### Phase 3: Medium Priority (Week 5+)
8. **Gap 7**: Implement drift detection metrics and alerting

---

## Files to Update

| File | Changes Required |
|------|------------------|
| `prd/sections/02_functional_requirements.md` | Add FR-04.2, FR-01.3.2, FR-02.5, FR-06 |
| `architecture/sections/04_implementation_patterns.md` | Add Prompt Governance, Validator patterns |
| `architecture/sections/05_deployment.md` | Add Policy-as-Code section |
| `test_strategy/test_strategy.md` | Add Eval Protocol section |
| `tasks.json` | Add tasks for all new requirements |
| `stories/epics_stories.md` | Add new user stories for gaps |

---

## Conclusion

All 8 gaps identified by the previous review have been **validated as genuine deficiencies** when compared against the research paper requirements. The remediation roadmap provides a structured approach to achieving full compliance with Deterministic Agentic Engineering principles.

**Next Steps**:
1. Update PRD functional requirements with new FRs
2. Update Architecture with new patterns
3. Generate new tasks in tasks.json
4. Update test strategy with Eval Protocol
5. Add new user stories to epics
