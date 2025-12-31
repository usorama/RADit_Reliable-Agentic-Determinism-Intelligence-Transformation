# 06. MVP vs Future Scope Definition

**Document Version**: 1.0
**Last Updated**: 2025-12-31
**Status**: Approved

---

## Overview

This section defines the clear boundary between MVP (Minimum Viable Product) requirements and Future/Backlog scope. This distinction is critical for:

1. **Resource Allocation**: Focus development on highest-impact features first
2. **Expectation Management**: Stakeholders understand what's in v1.0 vs roadmap
3. **Decision Making**: Clear criteria for scope creep prevention
4. **Release Planning**: Well-defined milestones and deliverables

---

## Scope Categories

| Category | Definition | Timeline | Exit Criteria |
|----------|------------|----------|---------------|
| **MVP** | Required for first user deployment | 2-3 weeks | User can complete full workflow with approval gates |
| **Production** | Required for enterprise/commercial readiness | +2-3 weeks | Self-healing, analytics, multi-model support |
| **Future** | Competitive differentiation / nice-to-have | Backlog | Market-driven prioritization |

---

## MVP Definition (CURRENT PHASE)

### Core Principle
> **MVP = Working Planning Loop + User Control + Progress Visibility**

Users must be able to:
1. Submit requirements and answer clarifying questions
2. See, review, and approve the generated PRD
3. Review tasks before execution begins
4. Track progress via live visualization

### MVP Feature Set

| ID | Feature | Scope | FR Reference |
|----|---------|-------|--------------|
| INTERACT-001 | Interview Response Collection | MVP | FR-08.1 |
| INTERACT-002 | PRD Presentation Display | MVP | FR-08.2 |
| INTERACT-003 | PRD Approval Gate | MVP | FR-08.3 |
| INTERACT-004 | Task List Review | MVP | FR-08.4 |
| KANBAN-001 | Core Kanban Board | MVP | FR-08.5 |
| KANBAN-002 | Task Card Details | MVP | FR-08.5 |
| KANBAN-003 | Live Status Streaming | MVP | FR-08.5 |

### MVP User Journey

```
User: "Build me a todo app"
        |
        v
Planner: "A few questions..."    <-- INTERACT-001
        |
        v
User answers questions
        |
        v
PRD displayed for review          <-- INTERACT-002
        |
        v
User: [Approve PRD]               <-- INTERACT-003
        |
        v
Tasks displayed
        |
        v
User: [Approve Tasks]             <-- INTERACT-004
        |
        v
Kanban shows progress             <-- KANBAN-001/002/003
        |
        v
User watches cards move through columns
        |
        v
Deployment complete
```

### MVP Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Interview completion rate | 100% | All sessions complete interview flow |
| PRD approval (first attempt) | >= 70% | Approvals / Total PRDs |
| Task approval rate | >= 80% | Approvals / Total decompositions |
| Kanban sync accuracy | 100% | UI state = tasks.json state |

---

## Production Scope (POST-MVP)

### Core Principle
> **Production = Self-Healing + Analytics + Cost Optimization**

Enterprise readiness requires autonomous error recovery, detailed analytics, and efficient resource utilization.

### Production Feature Set

| ID | Feature | Scope | FR Reference |
|----|---------|-------|--------------|
| INTERACT-005 | Research Evidence Display | Production | FR-08.6 |
| INTERACT-006 | Complexity Visualization | Production | FR-02.5 |
| INTERACT-007 | Web Research MCP Server | Production | FR-08.7 |
| INTERACT-008 | Iterative Planning Refinement | Production | FR-08.8 |
| KANBAN-004 | Drag-and-Drop Prioritization | Production | FR-08.5 |
| KANBAN-005 | Agent Assignment Display | Production | FR-08.5 |
| KANBAN-006 | Metrics Dashboard | Production | FR-08.5 |
| MDH-001 | Monitor Node Integration | Production | FR-09.1 |
| MDH-002 | Diagnose Node Implementation | Production | FR-09.2 |
| MDH-003 | Heal Node Implementation | Production | FR-09.3 |
| MDH-004 | Escalation & Human Override | Production | FR-09.4 |
| EVOLVE-003 | Skill Extraction Library | Production | FR-07.3.1 |
| EVOLVE-004 | Model Performance Analytics | Production | FR-07.3.2 |
| DRIVER-001 | Model Driver Abstraction | Production | FR-10.1 |
| DRIVER-002 | Model Driver MCP Server | Production | FR-10.2 |
| DRIVER-003 | Cost Optimization Router | Production | FR-10.3 |

### Production Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Self-healing success rate | >= 70% | Heals / Total fixable errors |
| Mean time to heal | < 5 min | Avg healing duration |
| Skill reuse rate | >= 30% | Tasks using extracted skills |
| Model cost reduction | >= 20% | Via intelligent routing |
| pass@1 rate | >= 90% | First attempt success |

---

## Future Backlog

### Core Principle
> **Future = Differentiation + Advanced Automation**

Features that provide competitive advantage but aren't required for core functionality.

### Future Feature Set

| ID | Feature | Scope | Rationale |
|----|---------|-------|-----------|
| INTERACT-009 | Workflow Progress Dashboard | Future | Nice-to-have UX |
| INTERACT-010 | Inline PRD Editing | Future | Convenience feature |
| INTERACT-011 | Persona Collaboration Indicators | Future | UX polish |
| INTERACT-012 | Dependency Resolver MCP | Future | Advanced tooling |
| KANBAN-007 | Multi-Workflow Board | Future | Enterprise scale |
| KANBAN-008 | Custom Column Configuration | Future | Flexibility |
| KANBAN-009 | Swimlane Views | Future | Visualization options |
| MDH-005 | Sentinel Agent | Future | Advanced security |
| MDH-006 | Predictive Issue Detection | Future | Proactive AI |
| MDH-007 | Auto-Rollback Capability | Future | Risk mitigation |
| EVOLVE-005 | Prompt Optimization (DSPy) | Future | Auto-improvement |
| EVOLVE-006 | A/B Testing Infrastructure | Future | Experimentation |
| EVOLVE-007 | Constitutional Safety | Future | Safety guardrails |
| DRIVER-004 | Local Model Support | Future | Offline capability |
| DRIVER-005 | Model Ensemble Voting | Future | Decision quality |

---

## Scope Change Management

### Criteria for MVP Promotion

A Future item can be promoted to MVP if ALL conditions are met:

1. **User-Blocking**: Current MVP cannot function without it
2. **Minimal Effort**: Implementation < 2 days
3. **No Dependencies**: Does not require other Future items
4. **Team Agreement**: Documented decision with rationale

### Criteria for MVP Demotion

An MVP item can be demoted to Production/Future if ALL conditions are met:

1. **Workaround Exists**: Users can complete workflow without it
2. **Time Pressure**: Schedule demands prioritization
3. **Reversible**: Can be added post-launch without breaking changes
4. **Team Agreement**: Documented decision with rationale

---

## Epic Summary by Scope

| Epic | MVP Tasks | Production Tasks | Future Tasks | Total |
|------|-----------|------------------|--------------|-------|
| Epic 13 (User Interaction) | 4 | 4 | 4 | 12 |
| Epic 14 (Kanban) | 3 | 3 | 3 | 9 |
| Epic 15 (Monitor-Diagnose-Heal) | 0 | 4 | 3 | 7 |
| Epic 16 (Self-Evolution) | 0 | 2 | 3 | 5 |
| Epic 17 (Multi-Model Driver) | 0 | 3 | 2 | 5 |
| **Total** | **7** | **16** | **15** | **38** |

---

## Related Documents

- **Master Epic Plan**: `docs/planning/epics/epic_13_through_16_master_plan.md`
- **MVP Readiness Assessment**: `docs/planning/mvp_readiness_assessment.md`
- **User Interaction Stories**: `docs/planning/stories/epic_13_user_interaction.md`
- **Task Definitions**: `docs/planning/tasks.json`

---

*Version 1.0 | 2025-12-31 | Status: Approved*
