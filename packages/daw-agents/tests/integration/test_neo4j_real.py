"""
Real Neo4j VPS Integration Tests.

These tests connect to the actual Hostinger VPS Neo4j instance at:
- URI: bolt://72.60.204.156:7687
- User: neo4j

Tests will skip gracefully if the VPS is unreachable.

Run with:
    pytest tests/integration/test_neo4j_real.py -m 'integration' -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from daw_agents.evolution.schemas import (
    Artifact,
    ArtifactType,
    ExperienceQuery,
    Skill,
    TaskType,
)

from .conftest import skip_if_vps_unreachable

if TYPE_CHECKING:
    from daw_agents.evolution.experience_logger import ExperienceLogger
    from daw_agents.memory.neo4j import Neo4jConnector


# All tests in this module require real VPS connection
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    skip_if_vps_unreachable,
]


class TestNeo4jVPSConnection:
    """Tests for basic Neo4j VPS connectivity."""

    @pytest.mark.asyncio
    async def test_neo4j_vps_connection(
        self,
        neo4j_connector: Neo4jConnector,
    ) -> None:
        """Verify real connection to Hostinger VPS Neo4j.

        This test validates that:
        1. Connection can be established to the VPS
        2. Basic queries execute successfully
        3. Connection health check passes
        """
        # Test 1: Basic connectivity via health check
        is_connected = await neo4j_connector.is_connected()
        assert is_connected is True, "Failed to connect to Neo4j VPS"

        # Test 2: Execute a simple query
        result = await neo4j_connector.query("RETURN 1 AS num", {})
        assert len(result) == 1
        assert result[0]["num"] == 1

        # Test 3: Query Neo4j version to confirm real connection
        version_result = await neo4j_connector.query(
            "CALL dbms.components() YIELD name, versions RETURN name, versions",
            {},
        )
        assert len(version_result) > 0
        # Neo4j should return component information
        assert any("Neo4j" in str(r.get("name", "")) for r in version_result)

    @pytest.mark.asyncio
    async def test_neo4j_vps_database_info(
        self,
        neo4j_connector: Neo4jConnector,
    ) -> None:
        """Query and verify Neo4j database information."""
        # Get database information
        db_result = await neo4j_connector.query(
            """
            CALL dbms.listConfig() YIELD name, value
            WHERE name = 'dbms.default_database'
            RETURN name, value
            """,
            {},
        )

        # We should get configuration info (may be empty in some Neo4j setups)
        # The query itself succeeding is proof of connection
        assert isinstance(db_result, list)


class TestNeo4jNodeOperations:
    """Tests for Neo4j node CRUD operations with real VPS."""

    @pytest.mark.asyncio
    async def test_neo4j_create_and_query_node(
        self,
        neo4j_connector: Neo4jConnector,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Create a real node and query it back.

        This test validates that:
        1. Nodes can be created in the real database
        2. Nodes can be queried by their element ID
        3. Node properties are preserved correctly
        """
        # Create a unique node
        test_name = f"TestPerson_{test_run_id}"
        properties = {
            "name": test_name,
            "age": 42,
            "test_id": test_run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Create the node
        node_id = await neo4j_connector.create_node(
            labels=["TestPerson"],
            properties=properties,
        )
        cleanup_test_nodes.append(node_id)

        # Verify node_id is a valid Neo4j element ID
        assert node_id is not None
        assert isinstance(node_id, str)
        assert len(node_id) > 0

        # Query the node back by ID
        node = await neo4j_connector.get_node_by_id(node_id)

        # Verify node was retrieved
        assert node is not None
        assert "TestPerson" in node["labels"]
        assert node["properties"]["name"] == test_name
        assert node["properties"]["age"] == 42
        assert node["properties"]["test_id"] == test_run_id

    @pytest.mark.asyncio
    async def test_neo4j_query_by_property(
        self,
        neo4j_connector: Neo4jConnector,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Test querying nodes by property values."""
        # Create a unique node with searchable property
        unique_value = f"unique_query_test_{test_run_id}"
        node_id = await neo4j_connector.create_node(
            labels=["TestSearchable"],
            properties={"unique_field": unique_value, "test_id": test_run_id},
        )
        cleanup_test_nodes.append(node_id)

        # Query by the unique property
        results = await neo4j_connector.query(
            """
            MATCH (n:TestSearchable {unique_field: $value})
            RETURN n, elementId(n) as id
            """,
            {"value": unique_value},
        )

        # Verify we found our node
        assert len(results) == 1
        assert results[0]["id"] == node_id


class TestNeo4jRelationshipOperations:
    """Tests for Neo4j relationship operations with real VPS."""

    @pytest.mark.asyncio
    async def test_neo4j_create_relationship(
        self,
        neo4j_connector: Neo4jConnector,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Create a relationship between real nodes.

        This test validates that:
        1. Two nodes can be created
        2. A relationship can be created between them
        3. The relationship can be queried
        """
        # Create first node (Person)
        person_id = await neo4j_connector.create_node(
            labels=["TestPerson"],
            properties={
                "name": f"Alice_{test_run_id}",
                "test_id": test_run_id,
            },
        )
        cleanup_test_nodes.append(person_id)

        # Create second node (Company)
        company_id = await neo4j_connector.create_node(
            labels=["TestCompany"],
            properties={
                "name": f"TechCorp_{test_run_id}",
                "test_id": test_run_id,
            },
        )
        cleanup_test_nodes.append(company_id)

        # Create relationship
        rel_id = await neo4j_connector.create_relationship(
            from_node_id=person_id,
            to_node_id=company_id,
            rel_type="WORKS_AT",
            properties={
                "since": 2020,
                "role": "Engineer",
            },
        )

        # Verify relationship was created
        assert rel_id is not None
        assert isinstance(rel_id, str)

        # Query the relationship
        rel_results = await neo4j_connector.query(
            """
            MATCH (p:TestPerson)-[r:WORKS_AT]->(c:TestCompany)
            WHERE p.test_id = $test_id AND c.test_id = $test_id
            RETURN p.name as person, c.name as company, r.since as since, r.role as role
            """,
            {"test_id": test_run_id},
        )

        # Verify relationship properties
        assert len(rel_results) == 1
        rel = rel_results[0]
        assert f"Alice_{test_run_id}" in rel["person"]
        assert f"TechCorp_{test_run_id}" in rel["company"]
        assert rel["since"] == 2020
        assert rel["role"] == "Engineer"

    @pytest.mark.asyncio
    async def test_neo4j_multiple_relationships(
        self,
        neo4j_connector: Neo4jConnector,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Test creating multiple relationships from a single node."""
        # Create central node
        central_id = await neo4j_connector.create_node(
            labels=["TestCentral"],
            properties={"name": f"Hub_{test_run_id}", "test_id": test_run_id},
        )
        cleanup_test_nodes.append(central_id)

        # Create multiple connected nodes
        connected_ids = []
        for i in range(3):
            node_id = await neo4j_connector.create_node(
                labels=["TestConnected"],
                properties={
                    "name": f"Spoke_{i}_{test_run_id}",
                    "index": i,
                    "test_id": test_run_id,
                },
            )
            cleanup_test_nodes.append(node_id)
            connected_ids.append(node_id)

            # Create relationship
            await neo4j_connector.create_relationship(
                from_node_id=central_id,
                to_node_id=node_id,
                rel_type="CONNECTS_TO",
                properties={"order": i},
            )

        # Verify all relationships exist
        results = await neo4j_connector.query(
            """
            MATCH (c:TestCentral)-[r:CONNECTS_TO]->(n:TestConnected)
            WHERE c.test_id = $test_id
            RETURN count(r) as rel_count
            """,
            {"test_id": test_run_id},
        )

        assert results[0]["rel_count"] == 3


class TestExperienceLoggerReal:
    """Tests for ExperienceLogger with real Neo4j VPS."""

    @pytest.mark.asyncio
    async def test_experience_logger_log_success(
        self,
        experience_logger_real: ExperienceLogger,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Test logging a successful experience to real Neo4j."""
        # Log a successful experience
        exp_id = await experience_logger_real.log_success(
            task_id=f"TEST-{test_run_id}",
            task_type=TaskType.CODING,
            prompt_version="test_v1.0",
            model_used="test-model",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
            retries=0,
        )
        cleanup_test_nodes.append(exp_id)

        # Verify the experience was created
        assert exp_id is not None
        assert isinstance(exp_id, str)

        # Query the experience back
        exp = await experience_logger_real.get_experience_by_id(exp_id)
        assert exp is not None
        assert exp.task_id == f"TEST-{test_run_id}"
        assert exp.task_type == TaskType.CODING
        assert exp.success is True
        assert exp.tokens_used == 1000

    @pytest.mark.asyncio
    async def test_experience_logger_log_failure(
        self,
        experience_logger_real: ExperienceLogger,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Test logging a failed experience to real Neo4j."""
        # Log a failed experience
        exp_id = await experience_logger_real.log_failure(
            task_id=f"FAIL-{test_run_id}",
            task_type=TaskType.VALIDATION,
            prompt_version="test_v1.0",
            model_used="test-model",
            tokens_used=2000,
            cost_usd=0.02,
            duration_ms=10000,
            error_message="Test error message",
            error_type="TestError",
            retries=3,
        )
        cleanup_test_nodes.append(exp_id)

        # Verify the experience was created
        exp = await experience_logger_real.get_experience_by_id(exp_id)
        assert exp is not None
        assert exp.task_id == f"FAIL-{test_run_id}"
        assert exp.success is False
        assert exp.error_message == "Test error message"
        assert exp.error_type == "TestError"
        assert exp.retries == 3

    @pytest.mark.asyncio
    async def test_experience_logger_with_skills(
        self,
        experience_logger_real: ExperienceLogger,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Test logging experience with associated skills."""
        # Create skills
        skills = [
            Skill(
                name=f"test_skill_1_{test_run_id}",
                pattern="pattern_1",
                description="Test skill 1",
            ),
            Skill(
                name=f"test_skill_2_{test_run_id}",
                pattern="pattern_2",
                description="Test skill 2",
            ),
        ]

        # Log experience with skills
        exp_id = await experience_logger_real.log_success(
            task_id=f"SKILL-{test_run_id}",
            task_type=TaskType.CODING,
            prompt_version="test_v1.0",
            model_used="test-model",
            tokens_used=1500,
            cost_usd=0.015,
            duration_ms=7500,
            skills=skills,
        )
        cleanup_test_nodes.append(exp_id)

        # Get related skills
        related_skills = await experience_logger_real.get_related_skills(exp_id)

        # Verify skills were created and linked
        assert len(related_skills) == 2
        skill_names = [s.name for s in related_skills]
        assert f"test_skill_1_{test_run_id}" in skill_names
        assert f"test_skill_2_{test_run_id}" in skill_names

    @pytest.mark.asyncio
    async def test_experience_logger_with_artifacts(
        self,
        experience_logger_real: ExperienceLogger,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Test logging experience with produced artifacts."""
        # Create artifacts
        artifacts = [
            Artifact(
                artifact_type=ArtifactType.CODE,
                path=f"src/test_{test_run_id}.py",
                description="Test code file",
            ),
            Artifact(
                artifact_type=ArtifactType.TEST,
                path=f"tests/test_{test_run_id}.py",
                description="Test file",
            ),
        ]

        # Log experience with artifacts
        exp_id = await experience_logger_real.log_success(
            task_id=f"ARTIFACT-{test_run_id}",
            task_type=TaskType.CODING,
            prompt_version="test_v1.0",
            model_used="test-model",
            tokens_used=2000,
            cost_usd=0.02,
            duration_ms=10000,
            artifacts=artifacts,
        )
        cleanup_test_nodes.append(exp_id)

        # Get related artifacts
        related_artifacts = await experience_logger_real.get_related_artifacts(exp_id)

        # Verify artifacts were created and linked
        assert len(related_artifacts) == 2
        artifact_paths = [a.path for a in related_artifacts]
        assert f"src/test_{test_run_id}.py" in artifact_paths
        assert f"tests/test_{test_run_id}.py" in artifact_paths

    @pytest.mark.asyncio
    async def test_experience_logger_query_experiences(
        self,
        experience_logger_real: ExperienceLogger,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Test querying experiences from real Neo4j."""
        # Create multiple experiences
        for i in range(3):
            exp_id = await experience_logger_real.log_success(
                task_id=f"QUERY-{test_run_id}-{i}",
                task_type=TaskType.CODING,
                prompt_version="test_v1.0",
                model_used="test-model",
                tokens_used=1000 + i * 100,
                cost_usd=0.01 + i * 0.001,
                duration_ms=5000 + i * 1000,
            )
            cleanup_test_nodes.append(exp_id)

        # Query experiences by task type
        query = ExperienceQuery(
            task_type=TaskType.CODING,
            success=True,
            limit=100,
        )
        results = await experience_logger_real.query_similar_experiences(query)

        # Verify we got our test experiences (plus any existing)
        assert len(results) >= 3
        test_task_ids = [e.task_id for e in results if e.task_id.startswith(f"QUERY-{test_run_id}")]
        assert len(test_task_ids) == 3

    @pytest.mark.asyncio
    async def test_experience_logger_success_rate(
        self,
        experience_logger_real: ExperienceLogger,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Test calculating success rate from real Neo4j data."""
        # Create 3 successes and 1 failure
        for i in range(3):
            exp_id = await experience_logger_real.log_success(
                task_id=f"RATE-SUCCESS-{test_run_id}-{i}",
                task_type=TaskType.VALIDATION,
                prompt_version="test_v1.0",
                model_used=f"rate-test-model-{test_run_id}",
                tokens_used=1000,
                cost_usd=0.01,
                duration_ms=5000,
            )
            cleanup_test_nodes.append(exp_id)

        fail_id = await experience_logger_real.log_failure(
            task_id=f"RATE-FAIL-{test_run_id}",
            task_type=TaskType.VALIDATION,
            prompt_version="test_v1.0",
            model_used=f"rate-test-model-{test_run_id}",
            tokens_used=1000,
            cost_usd=0.01,
            duration_ms=5000,
            error_message="Test failure",
        )
        cleanup_test_nodes.append(fail_id)

        # Calculate success rate for our test model
        rate = await experience_logger_real.calculate_success_rate(
            model_used=f"rate-test-model-{test_run_id}",
        )

        # Verify success rate (3 out of 4 = 0.75)
        assert rate.total_count == 4
        assert rate.success_count == 3
        assert rate.success_rate == 0.75


class TestCleanupVerification:
    """Tests to verify that cleanup mechanisms work correctly."""

    @pytest.mark.asyncio
    async def test_cleanup_test_nodes_works(
        self,
        neo4j_connector: Neo4jConnector,
        cleanup_test_nodes: list[str],
        test_run_id: str,
    ) -> None:
        """Verify that cleanup_test_nodes fixture properly cleans up.

        This test creates nodes and verifies they are cleaned up after
        the test completes.
        """
        # Create a node
        node_id = await neo4j_connector.create_node(
            labels=["CleanupTest"],
            properties={"test_id": test_run_id, "cleanup_test": True},
        )
        cleanup_test_nodes.append(node_id)

        # Verify node exists
        node = await neo4j_connector.get_node_by_id(node_id)
        assert node is not None

        # The cleanup happens after this test completes
        # We verify in a separate test that nodes are cleaned

    @pytest.mark.asyncio
    async def test_no_test_pollution(
        self,
        neo4j_connector: Neo4jConnector,
    ) -> None:
        """Verify that test data from other tests is not polluting the database.

        This test checks that we don't have accumulated test nodes.
        """
        # Query for any leftover test nodes (should be minimal)
        result = await neo4j_connector.query(
            """
            MATCH (n)
            WHERE n.cleanup_test = true OR n:CleanupTest
            RETURN count(n) as count
            """,
            {},
        )

        # There might be some nodes if tests are running concurrently,
        # but we should not have hundreds of accumulated nodes
        count = result[0]["count"]
        assert count < 50, f"Found {count} leftover test nodes - cleanup may not be working"
