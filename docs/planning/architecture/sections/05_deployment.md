# 05. Deployment & Development Architecture

## Deployment Architecture

The DAW Platform itself is containerized using Docker.
-   **Service A**: `daw-backend` (FastAPI + LangGraph)
-   **Service B**: `daw-frontend` (Next.js)
-   **Service C**: `daw-graph` (Neo4j)
-   **Service D**: `daw-redis` (LangGraph Checkpoint Storage/Celery Broker)

This stack can be deployed to any K8s cluster or via `docker-compose` for local usage.

---

## Deployment Quality Gates (Policy-as-Code)

All deployments are governed by codified policies enforced automatically. No deployment proceeds unless all blocking gates pass.

### Gate 1: Code Quality (BLOCKING)

| Criterion | Threshold | Action |
|-----------|-----------|--------|
| Test Coverage (new code) | >= 80% | Block merge |
| Test Coverage (total) | >= 70% | Block release |
| TypeScript Strict Mode | Enabled | Block commit |
| Linting (Ruff/ESLint) | 0 errors | Block commit |

### Gate 2: Security (BLOCKING)

| Criterion | Threshold | Action |
|-----------|-----------|--------|
| SAST Critical Findings | 0 | Block merge |
| SAST High Findings | 0 | Block release |
| SCA Critical CVEs | 0 | Block merge |
| Secrets Detected | 0 | Block commit |
| Dependency Age | < 90 days behind latest | Warning |

### Gate 3: Performance (WARNING)

| Criterion | Threshold | Action |
|-----------|-----------|--------|
| API Response Time (p95) | < 500ms | Warning |
| Bundle Size Increase | < 10% | Warning |
| Memory Usage | < 512MB per container | Warning |

### Gate 4: UAT (BLOCKING for Production)

| Criterion | Requirement | Action |
|-----------|-------------|--------|
| P0 User Journeys | All pass | Block production deploy |
| P1 User Journeys | >= 90% pass | Warning |
| Visual Regression | < 0.1% diff | Block production deploy |

### Zero-Copy Fork for Database Migrations

Database migrations follow a safe deployment pattern:
1. Create zero-copy fork of production database (instant, no data duplication)
2. Apply migration to fork
3. Run full validation suite on fork
4. If all tests pass, apply migration to production
5. If any test fails, discard fork with zero production impact

```yaml
# .github/workflows/deploy.yml (simplified)
migration_job:
  steps:
    - name: Create DB Fork
      run: pgtools fork create --source production --name migration-test
    - name: Apply Migration
      run: pgtools fork migrate --name migration-test
    - name: Validate
      run: pytest tests/db/ --fork migration-test
    - name: Apply to Production (if validation passed)
      if: success()
      run: pgtools migrate --target production
    - name: Discard Fork
      run: pgtools fork delete --name migration-test
```

### GitOps Deployment (ArgoCD)

```yaml
# Deployment controlled by ArgoCD with policy sync
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: daw-production
  annotations:
    argocd.argoproj.io/sync-wave: "2"  # After policy validation
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - Validate=true
```

---

## Development Environment

### Prerequisites
-   Python 3.12+, Node 22 LTS, Docker Desktop.
-   E2B API Key, OpenAI/Anthropic API Key.
-   Clerk API Keys.

### Setup Commands
```bash
# Clone and Setup
git clone <repo>
cd deterministic-agent-workbench
./scripts/setup_dev.sh  # Installs uv (Python) and pnpm (JS)

# Start Local Dev Stack
docker-compose up -d graph redis
pnpm dev
uv run start-backend
```

---

## CI/CD Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CI/CD Pipeline                            │
├─────────────────────────────────────────────────────────────┤
│ Pre-Commit (Local)                                          │
│  └── Linting, Type Check, Secrets Scan                      │
├─────────────────────────────────────────────────────────────┤
│ Pull Request (GitHub Actions)                               │
│  ├── Unit Tests + Coverage                                  │
│  ├── SAST Security Scan                                     │
│  ├── SCA Vulnerability Check                                │
│  └── Prompt Regression Tests                                │
├─────────────────────────────────────────────────────────────┤
│ Merge to Main                                               │
│  ├── Integration Tests                                      │
│  ├── Build Artifacts                                        │
│  └── Deploy to Staging                                      │
├─────────────────────────────────────────────────────────────┤
│ Production Deploy                                           │
│  ├── UAT Agent Validation                                   │
│  ├── Zero-Copy Fork Migration (if applicable)               │
│  ├── Canary Deployment (5% → 25% → 100%)                    │
│  └── Automated Rollback on Failure                          │
└─────────────────────────────────────────────────────────────┘
```
