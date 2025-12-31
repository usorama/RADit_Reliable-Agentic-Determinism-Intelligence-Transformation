# Epic 13: Holistic Observability & Self-Healing System

## Vision

Build an intelligent, AI-powered observability platform that:
1. **Collects** metrics, logs, and traces from all system components
2. **Analyzes** data using cost-effective local SLMs (Ollama) with escalation to OpenAI
3. **Detects** anomalies and predicts failures before they impact users
4. **Heals** automatically when possible, escalates intelligently when not
5. **Learns** from incidents to improve future response

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         OBSERVABILITY PLATFORM                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  DATA COLLECTION LAYER                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Metrics    │  │    Logs      │  │   Traces     │  │   Health     │        │
│  │  Prometheus  │  │   Vector     │  │  OpenTelemetry│  │   Probes    │        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │
│         │                 │                 │                 │                 │
│         └────────────────┬┴─────────────────┴─────────────────┘                 │
│                          ▼                                                       │
│  STORAGE LAYER                                                                   │
│  ┌────────────────────────────────────────────────────────────────┐             │
│  │  Unified Event Store (Redis Streams / PostgreSQL TimescaleDB)  │             │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │             │
│  │  │  Metrics    │  │    Logs     │  │   Events    │            │             │
│  │  │  (TSDB)     │  │  (Indexed)  │  │  (Stream)   │            │             │
│  │  └─────────────┘  └─────────────┘  └─────────────┘            │             │
│  └────────────────────────────────────────────────────────────────┘             │
│                          │                                                       │
│                          ▼                                                       │
│  AI ANALYSIS ENGINE                                                              │
│  ┌────────────────────────────────────────────────────────────────┐             │
│  │                                                                 │             │
│  │  ┌─────────────────────────────────────────────────────────┐   │             │
│  │  │  TIER 1: Ollama SLM (Mistral 7B / Phi-3 / Llama 3.2)   │   │             │
│  │  │  • Anomaly detection (pattern matching)                  │   │             │
│  │  │  • Log classification (error types, severity)           │   │             │
│  │  │  • Quick triage (known issue matching)                  │   │             │
│  │  │  • Metric threshold analysis                             │   │             │
│  │  │  • Cost: FREE (local inference)                          │   │             │
│  │  │  • Latency: <500ms                                       │   │             │
│  │  └──────────────────────────┬──────────────────────────────┘   │             │
│  │                             │ Escalate if:                      │             │
│  │                             │ • Confidence < 70%                │             │
│  │                             │ • Unknown pattern                 │             │
│  │                             │ • Multi-component correlation     │             │
│  │                             ▼                                   │             │
│  │  ┌─────────────────────────────────────────────────────────┐   │             │
│  │  │  TIER 2: OpenAI GPT-4o (Escalation Only)               │   │             │
│  │  │  • Root cause analysis (complex correlations)           │   │             │
│  │  │  • Incident summary generation                          │   │             │
│  │  │  • Remediation planning                                 │   │             │
│  │  │  • Post-mortem insights                                 │   │             │
│  │  │  • Cost: ~$0.01-0.05 per escalation                     │   │             │
│  │  │  • Latency: 2-5s                                        │   │             │
│  │  └─────────────────────────────────────────────────────────┘   │             │
│  │                                                                 │             │
│  └────────────────────────────────────────────────────────────────┘             │
│                          │                                                       │
│                          ▼                                                       │
│  ACTION ENGINE                                                                   │
│  ┌────────────────────────────────────────────────────────────────┐             │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │             │
│  │  │Self-Healing │  │  Alerting   │  │  Runbooks   │            │             │
│  │  │ (Auto-fix)  │  │ (Notify)    │  │ (Guided)    │            │             │
│  │  └─────────────┘  └─────────────┘  └─────────────┘            │             │
│  └────────────────────────────────────────────────────────────────┘             │
│                                                                                  │
│  VISUALIZATION LAYER                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                           │
│  │   Grafana    │  │  AI Insights │  │   Incident   │                           │
│  │  Dashboards  │  │     UI       │  │  Timeline    │                           │
│  └──────────────┘  └──────────────┘  └──────────────┘                           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Design Principles

1. **Cost-Effective**: Local SLMs handle 90%+ of analysis; OpenAI only for complex cases
2. **Project-Agnostic**: Core system is configuration-driven, adaptable to any project
3. **Self-Healing First**: Attempt automated remediation before alerting humans
4. **Progressive Escalation**: SLM → OpenAI → Human (only when necessary)
5. **Learning System**: Store successful resolutions to improve future responses
6. **Observable Observer**: The observability system monitors itself

## Story Breakdown

### Wave 1: Data Collection Foundation (OBS-001 to OBS-004)

| Story ID | Title | Description | Dependencies | Effort |
|----------|-------|-------------|--------------|--------|
| OBS-001 | Metrics Collection Infrastructure | Deploy Prometheus + exporters for Docker, host, and application metrics | None | M |
| OBS-002 | Centralized Log Aggregation | Deploy Vector for log collection with structured parsing | None | M |
| OBS-003 | Health Check Framework | Unified health probe system with configurable checks | None | S |
| OBS-004 | Event Correlation Pipeline | Redis Streams for real-time event ingestion and correlation | OBS-001, OBS-002 | M |

### Wave 2: AI Analysis Engine (OBS-005 to OBS-009)

| Story ID | Title | Description | Dependencies | Effort |
|----------|-------|-------------|--------------|--------|
| OBS-005 | Ollama SLM Integration | Deploy Ollama with Mistral 7B/Phi-3 for local inference | None | M |
| OBS-006 | Anomaly Detection Agent | SLM-powered anomaly detection on metrics and logs | OBS-004, OBS-005 | L |
| OBS-007 | Log Classification Agent | Automatic log severity and category classification | OBS-002, OBS-005 | M |
| OBS-008 | OpenAI Escalation Pipeline | GPT-4o integration for complex analysis escalation | OBS-006, OBS-007 | M |
| OBS-009 | Root Cause Analysis Agent | Multi-signal correlation for RCA with GPT-4o | OBS-008 | L |

### Wave 3: Self-Healing & Actions (OBS-010 to OBS-013)

| Story ID | Title | Description | Dependencies | Effort |
|----------|-------|-------------|--------------|--------|
| OBS-010 | Remediation Action Registry | Configurable action definitions (restart, scale, rollback) | None | M |
| OBS-011 | Self-Healing Executor | Automated execution of remediation actions | OBS-010, OBS-006 | L |
| OBS-012 | Alert Routing Framework | Multi-channel alerting (Slack, Email, PagerDuty) | OBS-006 | M |
| OBS-013 | Runbook Automation | Guided remediation playbooks with AI assistance | OBS-011 | M |

### Wave 4: Visualization & Insights (OBS-014 to OBS-016)

| Story ID | Title | Description | Dependencies | Effort |
|----------|-------|-------------|--------------|--------|
| OBS-014 | Grafana Dashboard Setup | Pre-built dashboards for system health, performance, errors | OBS-001 | M |
| OBS-015 | AI Insights Dashboard | Custom UI for AI-generated insights and recommendations | OBS-009 | L |
| OBS-016 | Incident Timeline View | Visual timeline of incidents with context and actions | OBS-011, OBS-012 | M |

### Wave 5: Learning & Extraction (OBS-017 to OBS-019)

| Story ID | Title | Description | Dependencies | Effort |
|----------|-------|-------------|--------------|--------|
| OBS-017 | Knowledge Base Builder | Store successful resolutions for future pattern matching | OBS-011 | M |
| OBS-018 | Configuration Schema | Project-agnostic configuration format for portability | All | M |
| OBS-019 | Standalone Package Extraction | Extract as independent observability framework | OBS-018 | L |

## Story Details

### OBS-001: Metrics Collection Infrastructure

**Objective**: Deploy comprehensive metrics collection covering all system components.

**Acceptance Criteria**:
- [ ] Prometheus deployed in Docker with persistent storage
- [ ] Node Exporter for host metrics (CPU, memory, disk, network)
- [ ] cAdvisor for Docker container metrics
- [ ] Custom application metrics endpoint in FastAPI backend
- [ ] Redis and Neo4j exporters configured
- [ ] Retention policy: 15 days local, archive to S3 (optional)
- [ ] Scrape interval: 15s for critical, 60s for standard

**Metrics to Collect**:
```yaml
host:
  - node_cpu_seconds_total
  - node_memory_MemAvailable_bytes
  - node_filesystem_avail_bytes
  - node_network_receive_bytes_total

containers:
  - container_cpu_usage_seconds_total
  - container_memory_usage_bytes
  - container_network_receive_bytes_total

application:
  - http_requests_total{method, path, status}
  - http_request_duration_seconds{quantile}
  - active_websocket_connections
  - llm_request_duration_seconds
  - llm_token_usage_total

databases:
  - neo4j_transaction_active
  - redis_connected_clients
  - redis_used_memory_bytes
```

**Files to Create**:
- `packages/observability/docker/prometheus/prometheus.yml`
- `packages/observability/docker/prometheus/alerts.yml`
- `packages/observability/exporters/app_exporter.py`

---

### OBS-005: Ollama SLM Integration

**Objective**: Deploy Ollama with small language models for cost-effective local AI inference.

**Acceptance Criteria**:
- [ ] Ollama deployed in Docker with GPU passthrough (if available) or CPU fallback
- [ ] Mistral 7B model loaded as primary
- [ ] Phi-3 Mini as lightweight fallback
- [ ] Python client wrapper with retry and timeout handling
- [ ] Prompt templates for observability tasks
- [ ] Response parsing and confidence scoring
- [ ] Benchmark: <500ms for anomaly detection, <2s for classification

**Model Selection Strategy**:
```python
class ModelRouter:
    def select_model(self, task_type: TaskType, urgency: Urgency) -> str:
        if urgency == Urgency.CRITICAL:
            return "phi3:mini"  # Fastest, good enough for triage
        elif task_type == TaskType.ANOMALY_DETECTION:
            return "mistral:7b"  # Best accuracy for patterns
        elif task_type == TaskType.LOG_CLASSIFICATION:
            return "phi3:medium"  # Good balance
        else:
            return "mistral:7b"  # Default
```

**Prompt Templates**:
```python
ANOMALY_DETECTION_PROMPT = """
You are an SRE monitoring system. Analyze these metrics:

{metrics_json}

Compare to baseline (last 24h average):
{baseline_json}

Respond with:
1. ANOMALY_DETECTED: true/false
2. CONFIDENCE: 0.0-1.0
3. SEVERITY: INFO/WARNING/CRITICAL
4. PATTERN: <brief description>
5. RECOMMENDATION: <action if needed>

JSON response only.
"""
```

**Files to Create**:
- `packages/observability/ai/ollama_client.py`
- `packages/observability/ai/prompts/anomaly_detection.py`
- `packages/observability/ai/prompts/log_classification.py`
- `packages/observability/ai/model_router.py`

---

### OBS-006: Anomaly Detection Agent

**Objective**: Real-time anomaly detection using SLM with pattern learning.

**Acceptance Criteria**:
- [ ] Sliding window analysis (1min, 5min, 15min, 1hr windows)
- [ ] Baseline calculation from historical data
- [ ] Multi-dimensional anomaly detection (metrics + logs combined)
- [ ] Confidence threshold for escalation (< 70% → OpenAI)
- [ ] False positive suppression using feedback loop
- [ ] Pattern library for known anomalies
- [ ] Sub-second detection for critical metrics

**Detection Algorithm**:
```python
async def detect_anomalies(
    metrics: MetricsSnapshot,
    logs: LogWindow,
    baseline: BaselineStats
) -> AnomalyResult:

    # Step 1: Statistical pre-filter (fast, no LLM)
    statistical_anomalies = await self.statistical_detector.detect(
        metrics, baseline,
        z_score_threshold=3.0
    )

    if not statistical_anomalies:
        return AnomalyResult(detected=False)

    # Step 2: SLM analysis for context
    prompt = self.build_prompt(metrics, logs, statistical_anomalies)
    response = await self.ollama.generate(
        model="mistral:7b",
        prompt=prompt,
        timeout=0.5  # 500ms max
    )

    result = self.parse_response(response)

    # Step 3: Escalate if low confidence
    if result.confidence < 0.7 or result.severity == Severity.CRITICAL:
        result = await self.escalate_to_openai(result, metrics, logs)

    return result
```

---

### OBS-011: Self-Healing Executor

**Objective**: Automated remediation with safety guardrails.

**Acceptance Criteria**:
- [ ] Action registry with pre-approved remediation steps
- [ ] Docker-based execution (restart, scale, rollback)
- [ ] Dry-run mode for validation
- [ ] Rollback capability for all actions
- [ ] Rate limiting (max 3 actions per service per hour)
- [ ] Audit trail for all actions
- [ ] Human approval required for destructive actions
- [ ] Circuit breaker to prevent healing loops

**Remediation Actions**:
```yaml
actions:
  restart_container:
    trigger: container_unhealthy
    command: docker restart {container_name}
    cooldown: 300s
    max_attempts: 3
    requires_approval: false

  scale_service:
    trigger: high_cpu_sustained
    command: docker service scale {service}={replicas}
    cooldown: 600s
    max_attempts: 2
    requires_approval: true

  rollback_deployment:
    trigger: error_rate_spike
    command: git revert HEAD && deploy.sh
    cooldown: 3600s
    max_attempts: 1
    requires_approval: true

  clear_cache:
    trigger: cache_memory_high
    command: redis-cli FLUSHDB
    cooldown: 600s
    max_attempts: 1
    requires_approval: false
```

**Safety Guardrails**:
```python
class HealingGuardrails:
    def can_execute(self, action: RemediationAction) -> bool:
        # Rate limit check
        if self.actions_in_window(action.service, hours=1) >= 3:
            return False

        # Circuit breaker check
        if self.is_circuit_open(action.service):
            return False

        # Prevent healing loops
        if self.last_action_failed(action.service):
            return False

        # Business hours check for destructive actions
        if action.destructive and not self.is_business_hours():
            return False

        return True
```

---

## Package Structure

```
packages/observability/
├── __init__.py
├── pyproject.toml
├── README.md
├── config/
│   ├── schema.json           # Project-agnostic config schema
│   ├── daw.yaml              # DAW-specific configuration
│   └── defaults.yaml         # Default values
├── collectors/
│   ├── __init__.py
│   ├── metrics.py            # Prometheus integration
│   ├── logs.py               # Vector/log aggregation
│   ├── traces.py             # OpenTelemetry
│   └── health.py             # Health probes
├── storage/
│   ├── __init__.py
│   ├── event_store.py        # Redis Streams abstraction
│   ├── metrics_store.py      # Time-series queries
│   └── knowledge_base.py     # Resolution patterns
├── ai/
│   ├── __init__.py
│   ├── ollama_client.py      # Ollama SLM wrapper
│   ├── openai_client.py      # OpenAI escalation
│   ├── model_router.py       # Model selection logic
│   ├── prompts/
│   │   ├── anomaly_detection.py
│   │   ├── log_classification.py
│   │   ├── root_cause_analysis.py
│   │   └── remediation_planning.py
│   └── agents/
│       ├── anomaly_detector.py
│       ├── log_classifier.py
│       ├── rca_agent.py
│       └── healing_agent.py
├── actions/
│   ├── __init__.py
│   ├── registry.py           # Action definitions
│   ├── executor.py           # Safe action execution
│   ├── guardrails.py         # Safety checks
│   └── runbooks.py           # Guided remediation
├── alerting/
│   ├── __init__.py
│   ├── router.py             # Alert routing logic
│   ├── slack.py
│   ├── email.py
│   └── pagerduty.py
├── dashboard/
│   ├── __init__.py
│   ├── api.py                # Dashboard API
│   └── templates/            # Grafana dashboard JSON
├── docker/
│   ├── docker-compose.observability.yml
│   ├── prometheus/
│   ├── grafana/
│   └── ollama/
└── tests/
    ├── test_anomaly_detection.py
    ├── test_self_healing.py
    └── test_escalation.py
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Metrics | Prometheus | Industry standard, pull-based, excellent ecosystem |
| Logs | Vector + Loki | Low memory, fast parsing, Grafana integration |
| Traces | OpenTelemetry | Vendor-agnostic, growing standard |
| Storage | Redis Streams | Fast, persistent, pub/sub built-in |
| Local AI | Ollama | Easy deployment, multiple models, CPU/GPU support |
| Cloud AI | OpenAI GPT-4o | Best reasoning, cost-effective for escalation |
| Dashboards | Grafana | Unified view, extensive plugins |
| Alerting | Custom + Slack | Flexible routing, AI-enhanced messages |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| MTTR (Mean Time to Recovery) | < 5 minutes | Time from detection to resolution |
| Self-Healing Success Rate | > 80% | Auto-resolved / Total incidents |
| False Positive Rate | < 5% | False alerts / Total alerts |
| Detection Latency | < 30 seconds | Time from event to detection |
| Cost per Incident | < $0.10 | AI inference + compute costs |
| Human Escalation Rate | < 20% | Incidents requiring human |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Healing loops causing more damage | Circuit breakers, rate limits, cooldowns |
| SLM hallucinations in diagnosis | Confidence thresholds, human verification for critical |
| OpenAI costs spiraling | Strict escalation criteria, cost budgets |
| Alert fatigue | Intelligent deduplication, severity-based routing |
| Missing critical issues | Multi-layer detection, health check redundancy |

## Implementation Order

1. **Phase 1 (Week 1-2)**: Data Collection (OBS-001 to OBS-004)
2. **Phase 2 (Week 3-4)**: AI Analysis (OBS-005 to OBS-009)
3. **Phase 3 (Week 5-6)**: Self-Healing (OBS-010 to OBS-013)
4. **Phase 4 (Week 7)**: Dashboards (OBS-014 to OBS-016)
5. **Phase 5 (Week 8)**: Extraction (OBS-017 to OBS-019)

## Next Steps

1. Create tasks.json entries for all OBS-* stories
2. Set up Ollama on VPS (can share with DAW)
3. Begin OBS-001 implementation
4. Design project-agnostic configuration schema

---

*Epic Owner*: TBD
*Created*: 2025-12-31
*Status*: PLANNING
