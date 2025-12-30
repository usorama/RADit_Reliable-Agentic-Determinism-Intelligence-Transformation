"""Integration tests package.

This package contains integration tests that require real external services
such as E2B sandbox, Neo4j, etc. These tests are marked with:

- @pytest.mark.integration: Requires real services
- @pytest.mark.slow: Tests that take longer than usual

To run integration tests:
    pytest tests/integration/ -m 'integration' -v

To skip slow tests:
    pytest tests/integration/ -m 'integration and not slow' -v
"""
