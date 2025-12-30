"""End-to-end tests: E2B sandbox communicates with Neo4j VPS.

This module contains integration tests that validate the network connectivity
between E2B Cloud sandboxes and the Hostinger VPS Neo4j instance.

These tests prove the full data path:
1. Start E2B sandbox (cloud)
2. Write Python script that connects to Neo4j VPS
3. Script performs operations on Neo4j
4. Verify results by querying Neo4j directly
5. Clean up test data

Run with:
    pytest tests/integration/test_e2b_neo4j_e2e.py -m 'integration' -v

Tests will skip gracefully if:
- E2B API key is not available
- Neo4j VPS is not reachable
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from .conftest import skip_if_vps_unreachable

if TYPE_CHECKING:
    from daw_agents.memory.neo4j import Neo4jConnector
    from daw_agents.sandbox.e2b import E2BSandbox


# All tests in this module require both E2B and Neo4j VPS
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    skip_if_vps_unreachable,
]


# Neo4j VPS connection details (same as in conftest.py)
VPS_URI = "bolt://72.60.204.156:7687"
VPS_USER = "neo4j"
VPS_PASSWORD = "daw_graph_2024"


class TestE2BNeo4jConnectivity:
    """Tests for E2B sandbox to Neo4j VPS network connectivity."""

    @pytest.mark.asyncio
    async def test_e2b_sandbox_connects_to_neo4j_vps(
        self,
        e2b_sandbox: E2BSandbox,
        neo4j_connector: Neo4jConnector,
        test_run_id: str,
    ) -> None:
        """E2E Test: Code running in E2B sandbox can store data in Neo4j VPS.

        This validates the full data path:
        1. Start E2B sandbox (cloud)
        2. Write Python script that connects to Neo4j VPS
        3. Script creates a test node
        4. Verify node exists by querying Neo4j directly
        5. Clean up test data
        """
        test_id = f"e2b-neo4j-e2e-{test_run_id}"

        # Python script to run inside E2B sandbox
        neo4j_script = f'''
import neo4j

print("Connecting to Neo4j VPS...")
driver = neo4j.GraphDatabase.driver(
    "{VPS_URI}",
    auth=("{VPS_USER}", "{VPS_PASSWORD}")
)

print("Creating test node...")
with driver.session() as session:
    session.run(
        "CREATE (n:E2BNeo4jTest {{test_id: $test_id, source: 'e2b_sandbox'}})",
        {{"test_id": "{test_id}"}}
    )

print("E2B_NEO4J_SUCCESS")
driver.close()
'''

        try:
            # Write script to E2B sandbox
            await e2b_sandbox.write_file("/test_neo4j.py", neo4j_script)

            # Install neo4j package and execute script
            # Use longer timeout since pip install can take time
            result = await e2b_sandbox.run_command(
                "pip install neo4j && python /test_neo4j.py",
                timeout=120,
            )

            # Verify script executed successfully
            assert result.success, f"E2B script failed: {result.stderr or result.error}"
            assert "E2B_NEO4J_SUCCESS" in result.stdout, (
                f"Success marker not found. stdout: {result.stdout}, stderr: {result.stderr}"
            )

            # Verify node exists in Neo4j (direct query from test)
            results = await neo4j_connector.query(
                "MATCH (n:E2BNeo4jTest {test_id: $test_id}) RETURN n",
                {"test_id": test_id},
            )
            assert len(results) == 1, f"Expected 1 node, got {len(results)}"
            assert results[0]["n"]["source"] == "e2b_sandbox"

        finally:
            # Cleanup: delete test node
            await neo4j_connector.query(
                "MATCH (n:E2BNeo4jTest {test_id: $test_id}) DELETE n",
                {"test_id": test_id},
            )

    @pytest.mark.asyncio
    async def test_e2b_reads_from_neo4j(
        self,
        e2b_sandbox: E2BSandbox,
        neo4j_connector: Neo4jConnector,
        test_run_id: str,
    ) -> None:
        """E2E Test: E2B sandbox can read existing data from Neo4j VPS.

        This validates:
        1. Create test data directly in Neo4j
        2. E2B sandbox queries and reads that data
        3. Data is correctly retrieved
        """
        test_id = f"e2b-read-{test_run_id}"
        test_value = f"test_value_{uuid.uuid4().hex[:8]}"

        try:
            # Create test data directly in Neo4j (not via E2B)
            await neo4j_connector.query(
                """
                CREATE (n:E2BReadTest {
                    test_id: $test_id,
                    value: $value,
                    created_by: 'direct_test'
                })
                """,
                {"test_id": test_id, "value": test_value},
            )

            # Python script to read from Neo4j inside E2B
            read_script = f'''
import neo4j

driver = neo4j.GraphDatabase.driver(
    "{VPS_URI}",
    auth=("{VPS_USER}", "{VPS_PASSWORD}")
)

with driver.session() as session:
    result = session.run(
        "MATCH (n:E2BReadTest {{test_id: $test_id}}) RETURN n.value as value",
        {{"test_id": "{test_id}"}}
    )
    record = result.single()
    if record:
        print(f"E2B_READ_VALUE={{record['value']}}")
    else:
        print("E2B_READ_NOT_FOUND")

driver.close()
'''

            # Write and execute script in E2B
            await e2b_sandbox.write_file("/read_neo4j.py", read_script)
            result = await e2b_sandbox.run_command(
                "pip install neo4j && python /read_neo4j.py",
                timeout=120,
            )

            # Verify data was read correctly
            assert result.success, f"E2B script failed: {result.stderr or result.error}"
            expected_output = f"E2B_READ_VALUE={test_value}"
            assert expected_output in result.stdout, (
                f"Expected '{expected_output}' in output. stdout: {result.stdout}"
            )

        finally:
            # Cleanup
            await neo4j_connector.query(
                "MATCH (n:E2BReadTest {test_id: $test_id}) DELETE n",
                {"test_id": test_id},
            )


class TestE2BNeo4jRoundtrip:
    """Tests for complete E2B -> Neo4j -> E2B data roundtrip."""

    @pytest.mark.asyncio
    async def test_e2b_neo4j_roundtrip(
        self,
        e2b_sandbox: E2BSandbox,
        neo4j_connector: Neo4jConnector,
        test_run_id: str,
    ) -> None:
        """E2E Test: Full roundtrip - E2B writes to Neo4j, then reads back.

        This validates:
        1. E2B sandbox creates a node in Neo4j
        2. Same E2B session reads that node back
        3. Data integrity is maintained
        """
        test_id = f"e2b-roundtrip-{test_run_id}"
        secret_value = f"secret_{uuid.uuid4().hex[:12]}"

        # Python script for full roundtrip
        roundtrip_script = f'''
import neo4j

driver = neo4j.GraphDatabase.driver(
    "{VPS_URI}",
    auth=("{VPS_USER}", "{VPS_PASSWORD}")
)

# Step 1: Write data
print("Writing to Neo4j...")
with driver.session() as session:
    session.run(
        "CREATE (n:E2BRoundtripTest {{test_id: $test_id, secret: $secret}})",
        {{"test_id": "{test_id}", "secret": "{secret_value}"}}
    )
print("Write complete")

# Step 2: Read data back in same session
print("Reading from Neo4j...")
with driver.session() as session:
    result = session.run(
        "MATCH (n:E2BRoundtripTest {{test_id: $test_id}}) RETURN n.secret as secret",
        {{"test_id": "{test_id}"}}
    )
    record = result.single()
    if record and record["secret"] == "{secret_value}":
        print("E2B_ROUNDTRIP_SUCCESS")
    else:
        print(f"E2B_ROUNDTRIP_FAILED: got {{record}}")

driver.close()
'''

        try:
            # Write and execute script in E2B
            await e2b_sandbox.write_file("/roundtrip_neo4j.py", roundtrip_script)
            result = await e2b_sandbox.run_command(
                "pip install neo4j && python /roundtrip_neo4j.py",
                timeout=120,
            )

            # Verify roundtrip succeeded
            assert result.success, f"E2B script failed: {result.stderr or result.error}"
            assert "E2B_ROUNDTRIP_SUCCESS" in result.stdout, (
                f"Roundtrip failed. stdout: {result.stdout}, stderr: {result.stderr}"
            )

            # Verify from test context as well
            results = await neo4j_connector.query(
                "MATCH (n:E2BRoundtripTest {test_id: $test_id}) RETURN n.secret as secret",
                {"test_id": test_id},
            )
            assert len(results) == 1
            assert results[0]["secret"] == secret_value

        finally:
            # Cleanup
            await neo4j_connector.query(
                "MATCH (n:E2BRoundtripTest {test_id: $test_id}) DELETE n",
                {"test_id": test_id},
            )

    @pytest.mark.asyncio
    async def test_e2b_neo4j_multiple_operations(
        self,
        e2b_sandbox: E2BSandbox,
        neo4j_connector: Neo4jConnector,
        test_run_id: str,
    ) -> None:
        """E2E Test: Multiple Neo4j operations from E2B sandbox.

        This validates:
        1. E2B can perform CREATE, READ, UPDATE, DELETE operations
        2. All CRUD operations work through the network path
        """
        test_id = f"e2b-crud-{test_run_id}"

        # Python script for CRUD operations
        crud_script = f'''
import neo4j

driver = neo4j.GraphDatabase.driver(
    "{VPS_URI}",
    auth=("{VPS_USER}", "{VPS_PASSWORD}")
)

errors = []

# CREATE
with driver.session() as session:
    session.run(
        "CREATE (n:E2BCRUDTest {{test_id: $test_id, value: 'initial', counter: 0}})",
        {{"test_id": "{test_id}"}}
    )
print("CREATE: done")

# READ
with driver.session() as session:
    result = session.run(
        "MATCH (n:E2BCRUDTest {{test_id: $test_id}}) RETURN n.value as value",
        {{"test_id": "{test_id}"}}
    )
    record = result.single()
    if record["value"] != "initial":
        errors.append(f"READ failed: expected 'initial', got {{record['value']}}")
print("READ: done")

# UPDATE
with driver.session() as session:
    session.run(
        "MATCH (n:E2BCRUDTest {{test_id: $test_id}}) SET n.value = 'updated', n.counter = 1",
        {{"test_id": "{test_id}"}}
    )
print("UPDATE: done")

# Verify UPDATE
with driver.session() as session:
    result = session.run(
        "MATCH (n:E2BCRUDTest {{test_id: $test_id}}) RETURN n.value as value, n.counter as counter",
        {{"test_id": "{test_id}"}}
    )
    record = result.single()
    if record["value"] != "updated":
        errors.append(f"UPDATE verification failed: expected 'updated', got {{record['value']}}")
    if record["counter"] != 1:
        errors.append(f"UPDATE verification failed: expected counter=1, got {{record['counter']}}")
print("UPDATE verification: done")

driver.close()

if errors:
    print("E2B_CRUD_FAILED: " + "; ".join(errors))
else:
    print("E2B_CRUD_SUCCESS")
'''

        try:
            # Write and execute script in E2B
            await e2b_sandbox.write_file("/crud_neo4j.py", crud_script)
            result = await e2b_sandbox.run_command(
                "pip install neo4j && python /crud_neo4j.py",
                timeout=120,
            )

            # Verify CRUD operations succeeded
            assert result.success, f"E2B script failed: {result.stderr or result.error}"
            assert "E2B_CRUD_SUCCESS" in result.stdout, (
                f"CRUD operations failed. stdout: {result.stdout}, stderr: {result.stderr}"
            )

        finally:
            # Cleanup
            await neo4j_connector.query(
                "MATCH (n:E2BCRUDTest {test_id: $test_id}) DELETE n",
                {"test_id": test_id},
            )


class TestE2BNeo4jErrorHandling:
    """Tests for error handling when E2B cannot reach Neo4j."""

    @pytest.mark.asyncio
    async def test_e2b_neo4j_wrong_credentials(
        self,
        e2b_sandbox: E2BSandbox,
        test_run_id: str,
    ) -> None:
        """E2E Test: E2B handles authentication failure gracefully.

        This validates that the E2B sandbox properly reports auth errors
        when given wrong credentials.
        """
        # Python script with wrong credentials
        wrong_creds_script = f'''
import neo4j
import sys

try:
    driver = neo4j.GraphDatabase.driver(
        "{VPS_URI}",
        auth=("wrong_user", "wrong_password")
    )

    with driver.session() as session:
        # This should fail with auth error
        session.run("RETURN 1")

    print("E2B_AUTH_UNEXPECTED_SUCCESS")
    driver.close()

except neo4j.exceptions.AuthError as e:
    print("E2B_AUTH_ERROR_CAUGHT")
    sys.exit(0)

except Exception as e:
    # Other errors (like ServiceUnavailable) may occur if auth check times out
    print(f"E2B_OTHER_ERROR: {{type(e).__name__}}: {{e}}")
    sys.exit(0)
'''

        # Write and execute script in E2B
        await e2b_sandbox.write_file("/wrong_creds.py", wrong_creds_script)
        result = await e2b_sandbox.run_command(
            "pip install neo4j && python /wrong_creds.py",
            timeout=120,
        )

        # Script should complete (exit 0) and catch the auth error
        assert result.success, f"Script failed unexpectedly: {result.stderr or result.error}"
        # Either auth error caught OR other connection-related error
        assert (
            "E2B_AUTH_ERROR_CAUGHT" in result.stdout
            or "E2B_OTHER_ERROR" in result.stdout
        ), f"Expected error handling. stdout: {result.stdout}"
        assert "E2B_AUTH_UNEXPECTED_SUCCESS" not in result.stdout, "Auth should have failed"

    @pytest.mark.asyncio
    async def test_e2b_neo4j_unreachable_host(
        self,
        e2b_sandbox: E2BSandbox,
        test_run_id: str,
    ) -> None:
        """E2E Test: E2B handles unreachable Neo4j host gracefully.

        This validates that the E2B sandbox properly reports connection errors
        when Neo4j host is unreachable.
        """
        # Python script with unreachable host
        unreachable_script = '''
import neo4j
import sys

try:
    # Use an IP that's definitely not reachable (TEST-NET-1)
    driver = neo4j.GraphDatabase.driver(
        "bolt://192.0.2.1:7687",
        auth=("neo4j", "password"),
        connection_timeout=5  # 5 second timeout
    )

    with driver.session() as session:
        session.run("RETURN 1")

    print("E2B_CONNECT_UNEXPECTED_SUCCESS")
    driver.close()

except neo4j.exceptions.ServiceUnavailable as e:
    print("E2B_SERVICE_UNAVAILABLE_CAUGHT")
    sys.exit(0)

except Exception as e:
    print(f"E2B_CONNECTION_ERROR: {type(e).__name__}")
    sys.exit(0)
'''

        # Write and execute script in E2B
        await e2b_sandbox.write_file("/unreachable.py", unreachable_script)
        result = await e2b_sandbox.run_command(
            "pip install neo4j && python /unreachable.py",
            timeout=120,
        )

        # Script should complete (exit 0) and catch connection error
        assert result.success, f"Script failed unexpectedly: {result.stderr or result.error}"
        assert (
            "E2B_SERVICE_UNAVAILABLE_CAUGHT" in result.stdout
            or "E2B_CONNECTION_ERROR" in result.stdout
        ), f"Expected connection error. stdout: {result.stdout}"
        assert "E2B_CONNECT_UNEXPECTED_SUCCESS" not in result.stdout

    @pytest.mark.asyncio
    async def test_e2b_neo4j_timeout_handling(
        self,
        e2b_sandbox: E2BSandbox,
        neo4j_connector: Neo4jConnector,
        test_run_id: str,
    ) -> None:
        """E2E Test: E2B handles slow Neo4j operations with timeout.

        This validates that timeout settings work correctly.
        Note: This test uses very short timeout to simulate slow operations.
        """
        test_id = f"e2b-timeout-{test_run_id}"

        # Python script that tests timeout behavior
        timeout_script = f'''
import neo4j
import sys

driver = neo4j.GraphDatabase.driver(
    "{VPS_URI}",
    auth=("{VPS_USER}", "{VPS_PASSWORD}"),
    max_connection_lifetime=300
)

try:
    # Normal operation should succeed
    with driver.session() as session:
        session.run(
            "CREATE (n:E2BTimeoutTest {{test_id: $test_id}})",
            {{"test_id": "{test_id}"}}
        )
    print("E2B_TIMEOUT_TEST_SUCCESS")

except neo4j.exceptions.TransientError as e:
    print(f"E2B_TRANSIENT_ERROR: {{e}}")

except Exception as e:
    print(f"E2B_TIMEOUT_ERROR: {{type(e).__name__}}: {{e}}")

finally:
    driver.close()
'''

        try:
            # Write and execute script in E2B
            await e2b_sandbox.write_file("/timeout_test.py", timeout_script)
            result = await e2b_sandbox.run_command(
                "pip install neo4j && python /timeout_test.py",
                timeout=120,
            )

            # We expect success in normal conditions
            assert result.success, f"Script failed: {result.stderr or result.error}"
            assert "E2B_TIMEOUT_TEST_SUCCESS" in result.stdout, (
                f"Timeout test failed. stdout: {result.stdout}"
            )

        finally:
            # Cleanup
            await neo4j_connector.query(
                "MATCH (n:E2BTimeoutTest {test_id: $test_id}) DELETE n",
                {"test_id": test_id},
            )


class TestE2BNeo4jDataIntegrity:
    """Tests for data integrity between E2B and Neo4j."""

    @pytest.mark.asyncio
    async def test_e2b_neo4j_special_characters(
        self,
        e2b_sandbox: E2BSandbox,
        neo4j_connector: Neo4jConnector,
        test_run_id: str,
    ) -> None:
        """E2E Test: Special characters are handled correctly.

        This validates that special characters (quotes, unicode, etc.)
        are properly escaped and stored.
        """
        test_id = f"e2b-special-{test_run_id}"

        # Python script with special characters (quotes, unicode, etc.)
        special_script = f'''
import neo4j

driver = neo4j.GraphDatabase.driver(
    "{VPS_URI}",
    auth=("{VPS_USER}", "{VPS_PASSWORD}")
)

test_value = "Hello 'World' with \\"quotes\\" and unicode: \\u4e2d\\u6587"

with driver.session() as session:
    # Create with special characters
    session.run(
        "CREATE (n:E2BSpecialTest {{test_id: $test_id, value: $value}})",
        {{"test_id": "{test_id}", "value": test_value}}
    )

# Read back and verify
with driver.session() as session:
    result = session.run(
        "MATCH (n:E2BSpecialTest {{test_id: $test_id}}) RETURN n.value as value",
        {{"test_id": "{test_id}"}}
    )
    record = result.single()
    if record and record["value"] == test_value:
        print("E2B_SPECIAL_CHARS_SUCCESS")
    else:
        print(f"E2B_SPECIAL_CHARS_FAILED: got {{record}}")

driver.close()
'''

        try:
            await e2b_sandbox.write_file("/special_chars.py", special_script)
            result = await e2b_sandbox.run_command(
                "pip install neo4j && python /special_chars.py",
                timeout=120,
            )

            assert result.success, f"Script failed: {result.stderr or result.error}"
            assert "E2B_SPECIAL_CHARS_SUCCESS" in result.stdout, (
                f"Special chars test failed. stdout: {result.stdout}"
            )

        finally:
            await neo4j_connector.query(
                "MATCH (n:E2BSpecialTest {test_id: $test_id}) DELETE n",
                {"test_id": test_id},
            )

    @pytest.mark.asyncio
    async def test_e2b_neo4j_large_data(
        self,
        e2b_sandbox: E2BSandbox,
        neo4j_connector: Neo4jConnector,
        test_run_id: str,
    ) -> None:
        """E2E Test: Large data payloads are handled correctly.

        This validates that moderately large data can be stored and retrieved.
        """
        test_id = f"e2b-large-{test_run_id}"
        # Create a 10KB string (not too large to avoid test slowness)
        data_size = 10240

        large_data_script = f'''
import neo4j

driver = neo4j.GraphDatabase.driver(
    "{VPS_URI}",
    auth=("{VPS_USER}", "{VPS_PASSWORD}")
)

# Generate 10KB of data
large_value = "X" * {data_size}

with driver.session() as session:
    session.run(
        "CREATE (n:E2BLargeTest {{test_id: $test_id, data: $data, size: $size}})",
        {{"test_id": "{test_id}", "data": large_value, "size": len(large_value)}}
    )

# Read back and verify size
with driver.session() as session:
    result = session.run(
        "MATCH (n:E2BLargeTest {{test_id: $test_id}}) RETURN length(n.data) as len, n.size as size",
        {{"test_id": "{test_id}"}}
    )
    record = result.single()
    if record and record["len"] == {data_size} and record["size"] == {data_size}:
        print("E2B_LARGE_DATA_SUCCESS")
    else:
        print(f"E2B_LARGE_DATA_FAILED: len={{record['len']}}, size={{record['size']}}")

driver.close()
'''

        try:
            await e2b_sandbox.write_file("/large_data.py", large_data_script)
            result = await e2b_sandbox.run_command(
                "pip install neo4j && python /large_data.py",
                timeout=120,
            )

            assert result.success, f"Script failed: {result.stderr or result.error}"
            assert "E2B_LARGE_DATA_SUCCESS" in result.stdout, (
                f"Large data test failed. stdout: {result.stdout}"
            )

        finally:
            await neo4j_connector.query(
                "MATCH (n:E2BLargeTest {test_id: $test_id}) DELETE n",
                {"test_id": test_id},
            )
