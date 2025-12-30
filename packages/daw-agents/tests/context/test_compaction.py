"""
Tests for Context Compaction module.

These tests cover:
- ContextCompactor initialization
- Token counting for text and messages
- Message summarization with LLM
- Context compaction with max_tokens limit
- Summary storage in Neo4j
- Relevant summary retrieval from Neo4j

Tests use mocking to avoid requiring running Neo4j or LLM services.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daw_agents.context.compaction import (
    CompactionConfig,
    ContextCompactor,
    Message,
    Summary,
)
from daw_agents.memory.neo4j import Neo4jConfig, Neo4jConnector
from daw_agents.models.router import ModelRouter, TaskType


class TestCompactionConfig:
    """Tests for CompactionConfig."""

    def test_default_config(self) -> None:
        """Test that config has sensible defaults."""
        config = CompactionConfig()
        assert config.max_tokens == 4000
        assert config.summary_model_type == TaskType.FAST
        assert config.recent_messages_to_keep == 10
        assert config.messages_per_summary == 20
        assert config.encoding_name == "cl100k_base"

    def test_custom_config(self) -> None:
        """Test that config accepts custom values."""
        config = CompactionConfig(
            max_tokens=8000,
            summary_model_type=TaskType.PLANNING,
            recent_messages_to_keep=5,
            messages_per_summary=10,
            encoding_name="o200k_base",
        )
        assert config.max_tokens == 8000
        assert config.summary_model_type == TaskType.PLANNING
        assert config.recent_messages_to_keep == 5
        assert config.messages_per_summary == 10
        assert config.encoding_name == "o200k_base"


class TestMessage:
    """Tests for Message model."""

    def test_message_creation(self) -> None:
        """Test that Message can be created with role and content."""
        msg = Message(role="user", content="Hello, world!")
        assert msg.role == "user"
        assert msg.content == "Hello, world!"

    def test_message_to_dict(self) -> None:
        """Test that Message can be converted to dict."""
        msg = Message(role="assistant", content="Hi there!")
        msg_dict = msg.model_dump()
        assert msg_dict == {"role": "assistant", "content": "Hi there!"}


class TestSummary:
    """Tests for Summary model."""

    def test_summary_creation(self) -> None:
        """Test that Summary can be created with required fields."""
        summary = Summary(
            content="This is a summary",
            conversation_id="conv-123",
            message_count=10,
            start_index=0,
            end_index=9,
        )
        assert summary.content == "This is a summary"
        assert summary.conversation_id == "conv-123"
        assert summary.message_count == 10
        assert summary.start_index == 0
        assert summary.end_index == 9
        assert summary.token_count >= 0  # Will be calculated


class TestContextCompactorInit:
    """Tests for ContextCompactor initialization."""

    def teardown_method(self) -> None:
        """Reset Neo4j singleton after each test."""
        Neo4jConnector._instance = None
        Neo4jConnector._driver = None
        Neo4jConnector._config = None

    def test_init_with_model_router(self) -> None:
        """Test that ContextCompactor can be initialized with ModelRouter."""
        router = ModelRouter()
        compactor = ContextCompactor(model_router=router)
        assert compactor.model_router is router
        assert compactor.neo4j_connector is None
        assert compactor.config is not None

    def test_init_with_neo4j_connector(self) -> None:
        """Test that ContextCompactor can be initialized with Neo4jConnector."""
        router = ModelRouter()
        neo4j_config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_db.driver.return_value = MagicMock()
            connector = Neo4jConnector.get_instance(neo4j_config)

        compactor = ContextCompactor(model_router=router, neo4j_connector=connector)
        assert compactor.model_router is router
        assert compactor.neo4j_connector is connector

    def test_init_with_custom_config(self) -> None:
        """Test that ContextCompactor accepts custom config."""
        router = ModelRouter()
        config = CompactionConfig(max_tokens=2000)
        compactor = ContextCompactor(model_router=router, config=config)
        assert compactor.config.max_tokens == 2000


class TestTokenCounting:
    """Tests for token counting functionality."""

    @pytest.fixture
    def compactor(self) -> ContextCompactor:
        """Create a ContextCompactor instance."""
        router = ModelRouter()
        return ContextCompactor(model_router=router)

    def test_count_tokens_empty_string(self, compactor: ContextCompactor) -> None:
        """Test that empty string returns 0 tokens."""
        assert compactor.count_tokens("") == 0

    def test_count_tokens_simple_text(self, compactor: ContextCompactor) -> None:
        """Test that simple text returns positive token count."""
        token_count = compactor.count_tokens("Hello, world!")
        assert token_count > 0
        assert token_count < 10  # "Hello, world!" should be ~4 tokens

    def test_count_tokens_long_text(self, compactor: ContextCompactor) -> None:
        """Test that long text returns proportionally more tokens."""
        short_text = "Hello"
        long_text = "Hello " * 100
        short_count = compactor.count_tokens(short_text)
        long_count = compactor.count_tokens(long_text)
        assert long_count > short_count

    def test_count_message_tokens_single_message(
        self, compactor: ContextCompactor
    ) -> None:
        """Test token count for a single message."""
        messages = [Message(role="user", content="Hello, world!")]
        token_count = compactor.count_message_tokens(messages)
        assert token_count > 0

    def test_count_message_tokens_multiple_messages(
        self, compactor: ContextCompactor
    ) -> None:
        """Test token count for multiple messages."""
        messages = [
            Message(role="user", content="Hello!"),
            Message(role="assistant", content="Hi there!"),
            Message(role="user", content="How are you?"),
        ]
        token_count = compactor.count_message_tokens(messages)
        single_count = compactor.count_message_tokens([messages[0]])
        assert token_count > single_count

    def test_count_message_tokens_empty_list(
        self, compactor: ContextCompactor
    ) -> None:
        """Test token count for empty message list."""
        assert compactor.count_message_tokens([]) == 0


class TestSummarization:
    """Tests for message summarization."""

    @pytest.fixture
    def compactor(self) -> ContextCompactor:
        """Create a ContextCompactor instance with mocked router."""
        router = MagicMock(spec=ModelRouter)
        return ContextCompactor(model_router=router)

    @pytest.mark.asyncio
    async def test_summarize_returns_string(self, compactor: ContextCompactor) -> None:
        """Test that summarize returns a summary string."""
        compactor.model_router.route = AsyncMock(
            return_value="Summary: User greeted and assistant responded."
        )

        messages = [
            Message(role="user", content="Hello!"),
            Message(role="assistant", content="Hi there! How can I help you?"),
        ]
        summary = await compactor.summarize(messages)

        assert isinstance(summary, str)
        assert len(summary) > 0
        compactor.model_router.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_uses_fast_model(self, compactor: ContextCompactor) -> None:
        """Test that summarize uses the FAST task type by default."""
        compactor.model_router.route = AsyncMock(return_value="Summary text")

        messages = [Message(role="user", content="Hello!")]
        await compactor.summarize(messages)

        call_args = compactor.model_router.route.call_args
        assert call_args[1]["task_type"] == TaskType.FAST

    @pytest.mark.asyncio
    async def test_summarize_empty_messages_raises(
        self, compactor: ContextCompactor
    ) -> None:
        """Test that summarizing empty messages raises ValueError."""
        with pytest.raises(ValueError, match="Cannot summarize empty messages"):
            await compactor.summarize([])

    @pytest.mark.asyncio
    async def test_summarize_includes_message_content(
        self, compactor: ContextCompactor
    ) -> None:
        """Test that summarize prompt includes message content."""
        compactor.model_router.route = AsyncMock(return_value="Summary text")

        messages = [
            Message(role="user", content="What is the capital of France?"),
            Message(role="assistant", content="The capital of France is Paris."),
        ]
        await compactor.summarize(messages)

        call_args = compactor.model_router.route.call_args
        prompt_messages = call_args[1]["messages"]
        # The prompt should contain the message content
        prompt_text = str(prompt_messages)
        assert "capital of France" in prompt_text or "Paris" in prompt_text


class TestCompaction:
    """Tests for context compaction."""

    @pytest.fixture
    def compactor(self) -> ContextCompactor:
        """Create a ContextCompactor instance with mocked router."""
        router = MagicMock(spec=ModelRouter)
        config = CompactionConfig(
            max_tokens=100,
            recent_messages_to_keep=2,
            messages_per_summary=3,
        )
        return ContextCompactor(model_router=router, config=config)

    @pytest.mark.asyncio
    async def test_compact_returns_list_of_messages(
        self, compactor: ContextCompactor
    ) -> None:
        """Test that compact returns a list of Message objects."""
        messages = [Message(role="user", content="Hello!")]
        result = await compactor.compact(messages)
        assert isinstance(result, list)
        assert all(isinstance(m, Message) for m in result)

    @pytest.mark.asyncio
    async def test_compact_under_limit_returns_original(
        self, compactor: ContextCompactor
    ) -> None:
        """Test that messages under token limit are returned unchanged."""
        messages = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello"),
        ]
        result = await compactor.compact(messages)
        assert len(result) == len(messages)
        assert result[0].content == messages[0].content

    @pytest.mark.asyncio
    async def test_compact_over_limit_reduces_tokens(
        self, compactor: ContextCompactor
    ) -> None:
        """Test that messages over token limit are compacted."""
        compactor.model_router.route = AsyncMock(return_value="Brief summary")

        # Create many messages that exceed the token limit
        messages = [
            Message(role="user", content=f"Message number {i} with some content")
            for i in range(20)
        ]

        result = await compactor.compact(messages)

        # Result should have fewer tokens than original
        original_tokens = compactor.count_message_tokens(messages)
        result_tokens = compactor.count_message_tokens(result)
        assert result_tokens <= compactor.config.max_tokens
        assert result_tokens < original_tokens

    @pytest.mark.asyncio
    async def test_compact_keeps_recent_messages(
        self, compactor: ContextCompactor
    ) -> None:
        """Test that recent messages are kept intact."""
        compactor.model_router.route = AsyncMock(return_value="Summary")

        messages = [
            Message(role="user", content=f"Old message {i}") for i in range(10)
        ] + [
            Message(role="user", content="Recent message 1"),
            Message(role="assistant", content="Recent message 2"),
        ]

        result = await compactor.compact(messages)

        # Last messages should be preserved
        assert result[-1].content == "Recent message 2"
        assert result[-2].content == "Recent message 1"

    @pytest.mark.asyncio
    async def test_compact_empty_messages(self, compactor: ContextCompactor) -> None:
        """Test that compacting empty messages returns empty list."""
        result = await compactor.compact([])
        assert result == []

    @pytest.mark.asyncio
    async def test_compact_with_max_tokens_override(
        self, compactor: ContextCompactor
    ) -> None:
        """Test that max_tokens can be overridden."""
        compactor.model_router.route = AsyncMock(return_value="Summary")

        messages = [
            Message(role="user", content=f"Message {i}") for i in range(10)
        ]

        result = await compactor.compact(messages, max_tokens=50)

        # Should respect the override
        result_tokens = compactor.count_message_tokens(result)
        assert result_tokens <= 50


class TestNeo4jStorage:
    """Tests for Neo4j summary storage."""

    def teardown_method(self) -> None:
        """Reset Neo4j singleton after each test."""
        Neo4jConnector._instance = None
        Neo4jConnector._driver = None
        Neo4jConnector._config = None

    @pytest.fixture
    def mock_neo4j_connector(self) -> Neo4jConnector:
        """Create a mocked Neo4j connector."""
        neo4j_config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_db.driver.return_value = mock_driver
            connector = Neo4jConnector.get_instance(neo4j_config)
            connector._driver = mock_driver
            return connector

    @pytest.fixture
    def compactor_with_neo4j(
        self, mock_neo4j_connector: Neo4jConnector
    ) -> ContextCompactor:
        """Create a ContextCompactor with Neo4j connector."""
        router = MagicMock(spec=ModelRouter)
        return ContextCompactor(
            model_router=router, neo4j_connector=mock_neo4j_connector
        )

    @pytest.mark.asyncio
    async def test_store_summary_returns_node_id(
        self, compactor_with_neo4j: ContextCompactor
    ) -> None:
        """Test that store_summary returns the node ID."""
        mock_connector = compactor_with_neo4j.neo4j_connector
        assert mock_connector is not None
        mock_connector.create_node = AsyncMock(return_value="4:test:summary123")

        node_id = await compactor_with_neo4j.store_summary(
            summary="Test summary",
            conversation_id="conv-123",
            metadata={"message_count": 10},
        )

        assert node_id == "4:test:summary123"
        mock_connector.create_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_summary_creates_correct_node(
        self, compactor_with_neo4j: ContextCompactor
    ) -> None:
        """Test that store_summary creates node with correct labels and properties."""
        mock_connector = compactor_with_neo4j.neo4j_connector
        assert mock_connector is not None
        mock_connector.create_node = AsyncMock(return_value="node_id")

        await compactor_with_neo4j.store_summary(
            summary="Test summary",
            conversation_id="conv-123",
            metadata={"message_count": 10, "start_index": 0},
        )

        call_args = mock_connector.create_node.call_args
        labels = call_args[1]["labels"]
        properties = call_args[1]["properties"]

        assert "Summary" in labels
        assert properties["content"] == "Test summary"
        assert properties["conversation_id"] == "conv-123"
        assert properties["message_count"] == 10

    @pytest.mark.asyncio
    async def test_store_summary_without_neo4j_raises(
        self,
    ) -> None:
        """Test that store_summary without Neo4j raises RuntimeError."""
        router = MagicMock(spec=ModelRouter)
        compactor = ContextCompactor(model_router=router)

        with pytest.raises(RuntimeError, match="Neo4j connector not configured"):
            await compactor.store_summary(
                summary="Test",
                conversation_id="conv-123",
                metadata={},
            )


class TestNeo4jRetrieval:
    """Tests for Neo4j summary retrieval."""

    def teardown_method(self) -> None:
        """Reset Neo4j singleton after each test."""
        Neo4jConnector._instance = None
        Neo4jConnector._driver = None
        Neo4jConnector._config = None

    @pytest.fixture
    def mock_neo4j_connector(self) -> Neo4jConnector:
        """Create a mocked Neo4j connector."""
        neo4j_config = Neo4jConfig(password="test")

        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_db.driver.return_value = mock_driver
            connector = Neo4jConnector.get_instance(neo4j_config)
            connector._driver = mock_driver
            return connector

    @pytest.fixture
    def compactor_with_neo4j(
        self, mock_neo4j_connector: Neo4jConnector
    ) -> ContextCompactor:
        """Create a ContextCompactor with Neo4j connector."""
        router = MagicMock(spec=ModelRouter)
        return ContextCompactor(
            model_router=router, neo4j_connector=mock_neo4j_connector
        )

    @pytest.mark.asyncio
    async def test_retrieve_relevant_returns_list(
        self, compactor_with_neo4j: ContextCompactor
    ) -> None:
        """Test that retrieve_relevant returns a list of summaries."""
        mock_connector = compactor_with_neo4j.neo4j_connector
        assert mock_connector is not None
        mock_connector.query = AsyncMock(
            return_value=[
                {"content": "Summary 1", "conversation_id": "conv-1"},
                {"content": "Summary 2", "conversation_id": "conv-2"},
            ]
        )

        results = await compactor_with_neo4j.retrieve_relevant(
            query="test query", limit=5
        )

        assert isinstance(results, list)
        assert len(results) == 2
        mock_connector.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_relevant_respects_limit(
        self, compactor_with_neo4j: ContextCompactor
    ) -> None:
        """Test that retrieve_relevant respects the limit parameter."""
        mock_connector = compactor_with_neo4j.neo4j_connector
        assert mock_connector is not None
        mock_connector.query = AsyncMock(return_value=[])

        await compactor_with_neo4j.retrieve_relevant(query="test", limit=3)

        call_args = mock_connector.query.call_args
        # Check that limit is in the query or params
        cypher = call_args[1]["cypher"]
        params = call_args[1].get("params", {})
        assert "LIMIT" in cypher or "limit" in params

    @pytest.mark.asyncio
    async def test_retrieve_relevant_without_neo4j_raises(
        self,
    ) -> None:
        """Test that retrieve_relevant without Neo4j raises RuntimeError."""
        router = MagicMock(spec=ModelRouter)
        compactor = ContextCompactor(model_router=router)

        with pytest.raises(RuntimeError, match="Neo4j connector not configured"):
            await compactor.retrieve_relevant(query="test")

    @pytest.mark.asyncio
    async def test_retrieve_by_conversation_id(
        self, compactor_with_neo4j: ContextCompactor
    ) -> None:
        """Test retrieving summaries by conversation ID."""
        mock_connector = compactor_with_neo4j.neo4j_connector
        assert mock_connector is not None
        mock_connector.query = AsyncMock(
            return_value=[
                {"content": "Summary 1", "conversation_id": "conv-123"},
            ]
        )

        results = await compactor_with_neo4j.retrieve_by_conversation(
            conversation_id="conv-123"
        )

        assert len(results) == 1
        assert results[0]["conversation_id"] == "conv-123"


class TestEndToEndCompaction:
    """End-to-end tests for context compaction workflow."""

    def teardown_method(self) -> None:
        """Reset Neo4j singleton after each test."""
        Neo4jConnector._instance = None
        Neo4jConnector._driver = None
        Neo4jConnector._config = None

    @pytest.mark.asyncio
    async def test_full_compaction_workflow(self) -> None:
        """Test complete compaction workflow: compact and store."""
        # Setup mocks
        router = MagicMock(spec=ModelRouter)
        router.route = AsyncMock(return_value="Summary of conversation")

        neo4j_config = Neo4jConfig(password="test")
        with patch("daw_agents.memory.neo4j.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_db.driver.return_value = mock_driver
            connector = Neo4jConnector.get_instance(neo4j_config)
            connector._driver = mock_driver

        connector.create_node = AsyncMock(return_value="node_id")

        config = CompactionConfig(
            max_tokens=50,
            recent_messages_to_keep=2,
            messages_per_summary=5,
        )

        compactor = ContextCompactor(
            model_router=router, neo4j_connector=connector, config=config
        )

        # Create messages that exceed token limit
        messages = [
            Message(role="user", content=f"Message {i} with content")
            for i in range(15)
        ]

        # Compact
        compacted = await compactor.compact(
            messages, conversation_id="conv-test"
        )

        # Verify compaction occurred
        assert len(compacted) < len(messages)
        assert compactor.count_message_tokens(compacted) <= 50

        # Verify summary was stored (via the compact method with conversation_id)
        # This depends on implementation - may need adjustment
