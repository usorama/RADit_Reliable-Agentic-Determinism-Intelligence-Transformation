# Epic 14: Real-World Integration & Functional Testing

**Created**: 2025-12-30
**Priority**: P0 - Critical
**Status**: Pending
**Rationale**: All existing tests use mocks. No real E2B → Neo4j VPS testing exists. No functional validation of building actual projects.

---

## Problem Statement

Current test suite (1600+ tests) is entirely mocked:
- E2B sandbox tests: All mocked with `MagicMock`
- Neo4j tests: Explicitly avoid "requiring a running Neo4j instance"
- No integration tests with real services
- No functional tests building real projects

The test strategy document defines Level 3 (System Tests) and Level 4 (UAT/Dogfood) that **do not exist in implementation**.

---

## Stories

### INTEG-001: E2B Sandbox Real Connection Tests
**Description**: Create integration tests that actually connect to E2B cloud sandbox
**Dependencies**: None (uses existing E2B wrapper)
**Estimate**: 3 hours

#### Acceptance Criteria
- [ ] Test marked with `@pytest.mark.integration` and `@pytest.mark.slow`
- [ ] Real E2B API key loaded from `.creds/e2b_api_key.txt`
- [ ] Tests execute actual commands in E2B sandbox
- [ ] Tests verify file operations in real sandbox
- [ ] Tests run in CI nightly (not on every PR)

#### Definition of Done
```python
# tests/integration/test_e2b_real.py
@pytest.mark.integration
@pytest.mark.slow
async def test_e2b_real_command_execution():
    """Execute real command in E2B sandbox."""
    sandbox = E2BSandbox.from_env()
    async with sandbox:
        result = await sandbox.run_command("echo 'Hello from E2B'")
        assert result.success
        assert "Hello from E2B" in result.stdout
```

---

### INTEG-002: Neo4j VPS Real Connection Tests
**Description**: Create integration tests connecting to Neo4j on Hostinger VPS
**Dependencies**: None (uses existing Neo4j connector)
**Estimate**: 3 hours

#### Acceptance Criteria
- [ ] Test marked with `@pytest.mark.integration` and `@pytest.mark.slow`
- [ ] Real connection to `bolt://72.60.204.156:7687`
- [ ] Credentials loaded from `.creds/neo4j_vps.txt`
- [ ] Tests create, query, and delete real nodes
- [ ] Tests verify Experience Logger with real Neo4j
- [ ] Cleanup after tests (no test data pollution)

#### Definition of Done
```python
# tests/integration/test_neo4j_real.py
@pytest.mark.integration
@pytest.mark.slow
async def test_neo4j_vps_connection():
    """Verify real connection to Hostinger VPS Neo4j."""
    config = Neo4jConfig(
        uri="bolt://72.60.204.156:7687",
        user="neo4j",
        password=load_creds("neo4j_vps.txt")
    )
    connector = Neo4jConnector.get_instance(config)
    assert await connector.is_connected()
```

---

### INTEG-003: E2B → Neo4j End-to-End Test
**Description**: Test complete flow: E2B executes code that stores results in Neo4j
**Dependencies**: INTEG-001, INTEG-002
**Estimate**: 4 hours

#### Acceptance Criteria
- [ ] E2B sandbox executes Python script
- [ ] Script connects to Neo4j VPS and stores data
- [ ] Test verifies data was stored correctly
- [ ] Full round-trip validation
- [ ] Network connectivity from E2B to Hostinger verified

#### Definition of Done
```python
# tests/integration/test_e2b_neo4j_e2e.py
@pytest.mark.integration
@pytest.mark.slow
async def test_e2b_stores_to_neo4j():
    """E2B sandbox stores experience data in Neo4j VPS."""
    async with E2BSandbox.from_env() as sandbox:
        # Write Python script that connects to Neo4j
        script = '''
import neo4j
driver = neo4j.GraphDatabase.driver(
    "bolt://72.60.204.156:7687",
    auth=("neo4j", "daw_graph_2024")
)
with driver.session() as session:
    session.run(
        "CREATE (e:E2BTest {id: $id, timestamp: datetime()})",
        {"id": "e2b-test-123"}
    )
print("SUCCESS")
'''
        await sandbox.write_file("/test_neo4j.py", script)
        result = await sandbox.run_command("pip install neo4j && python /test_neo4j.py")
        assert "SUCCESS" in result.stdout

    # Verify in Neo4j directly
    connector = Neo4jConnector.get_instance(config)
    results = await connector.query(
        "MATCH (e:E2BTest {id: 'e2b-test-123'}) RETURN e"
    )
    assert len(results) == 1

    # Cleanup
    await connector.query("MATCH (e:E2BTest) DELETE e")
```

---

### FUNC-001: Dogfood Test - Build Calculator Feature
**Description**: Use the DAW workbench to build an actual calculator feature
**Dependencies**: ORCHESTRATOR-001
**Estimate**: 6 hours

#### Acceptance Criteria
- [ ] Submit PRD: "Build a calculator with basic arithmetic"
- [ ] Planner Agent decomposes into tasks
- [ ] Executor Agent generates code
- [ ] Validator Agent verifies tests pass
- [ ] Generated calculator actually works
- [ ] Full agent pipeline validated end-to-end

#### Test Scenarios
1. **Happy Path**: PRD → Tasks → Code → Tests → Pass
2. **Retry Path**: Code fails → Agent retries → Eventually passes
3. **Human Escalation**: After N failures, system requests help

---

### FUNC-002: Dogfood Test - Build Settings Page
**Description**: Use DAW to build a settings page for the DAW dashboard
**Dependencies**: FUNC-001, FRONTEND-002
**Estimate**: 8 hours

#### Acceptance Criteria
- [ ] PRD: "Add a settings page to the DAW dashboard with theme toggle"
- [ ] Planner generates frontend tasks (React components)
- [ ] Executor generates TypeScript/React code
- [ ] Generated component integrates with existing dashboard
- [ ] Visual regression tests pass
- [ ] This is the "dogfood" test from test strategy doc

---

### FUNC-003: Regression Test Suite with Real Services
**Description**: Automated regression suite that runs nightly with real services
**Dependencies**: INTEG-001, INTEG-002, INTEG-003
**Estimate**: 4 hours

#### Acceptance Criteria
- [ ] GitHub Actions workflow for nightly runs
- [ ] Real E2B + Real Neo4j + Real LLM calls
- [ ] Golden PRD benchmarks executed
- [ ] Results stored in `eval_results/`
- [ ] Regression detection against baseline
- [ ] Slack/PagerDuty alerts on failure

#### CI Configuration
```yaml
# .github/workflows/integration-nightly.yml
name: Nightly Integration Tests
on:
  schedule:
    - cron: '0 3 * * *'  # 3 AM UTC

jobs:
  integration:
    runs-on: ubuntu-latest
    steps:
      - name: Run Integration Tests
        env:
          E2B_API_KEY: ${{ secrets.E2B_API_KEY }}
          NEO4J_URI: bolt://72.60.204.156:7687
          NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
        run: |
          pytest tests/integration/ -m "integration and slow" --tb=short
```

---

## Task Summary

| Task ID | Description | Est. Hours | Dependencies |
|---------|-------------|------------|--------------|
| INTEG-001 | E2B Real Connection Tests | 3 | None |
| INTEG-002 | Neo4j VPS Real Connection Tests | 3 | None |
| INTEG-003 | E2B → Neo4j E2E Test | 4 | INTEG-001, INTEG-002 |
| FUNC-001 | Dogfood: Build Calculator | 6 | ORCHESTRATOR-001 |
| FUNC-002 | Dogfood: Build Settings Page | 8 | FUNC-001 |
| FUNC-003 | Nightly Regression Suite | 4 | INTEG-001, INTEG-002 |

**Total**: 28 hours estimated

---

## Success Criteria for Epic 13

1. **Integration Tests Exist**: `tests/integration/` directory with real service tests
2. **Markers Defined**: `@pytest.mark.integration` and `@pytest.mark.slow` in `pytest.ini`
3. **CI Workflow**: Nightly GitHub Action runs integration tests
4. **Dogfood Validation**: At least one feature built using DAW itself
5. **No Mock Dependencies**: Integration tests use ZERO mocks for external services
6. **Documentation**: README in `tests/integration/` explaining setup

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| E2B API costs | Use minimal sandbox time, aggressive cleanup |
| Neo4j VPS down | Health check before tests, skip with warning |
| LLM costs | Cache responses for regression, use smaller models |
| Flaky tests | Retry logic, deterministic test data |
| Network issues | Timeout handling, graceful degradation |

---

*This epic addresses the critical gap between our test strategy documentation and actual implementation.*
