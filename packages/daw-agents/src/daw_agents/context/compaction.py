"""
Context Compaction module for managing conversation history.

This module implements CORE-006: Context Compaction Logic for the DAW Agent Workbench.

Key Features:
- Token counting using tiktoken
- LLM-based summarization of message groups
- Context window management with recency bias
- Neo4j storage for summaries
- Semantic retrieval of relevant context

Usage:
    ```python
    from daw_agents.context.compaction import ContextCompactor, CompactionConfig
    from daw_agents.models.router import ModelRouter

    router = ModelRouter()
    compactor = ContextCompactor(model_router=router)

    # Compact a long conversation history
    messages = [Message(role="user", content="..."), ...]
    compacted = await compactor.compact(messages, max_tokens=4000)
    ```
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import tiktoken
from pydantic import BaseModel, Field

from daw_agents.memory.neo4j import Neo4jConnector
from daw_agents.models.router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


class Message(BaseModel):
    """Model representing a chat message."""

    role: str = Field(..., description="Role of the message sender (user, assistant, system)")
    content: str = Field(..., description="Content of the message")


class Summary(BaseModel):
    """Model representing a compacted summary of messages."""

    content: str = Field(..., description="The summary text")
    conversation_id: str = Field(..., description="ID of the conversation")
    message_count: int = Field(..., description="Number of messages summarized")
    start_index: int = Field(..., description="Start index of summarized messages")
    end_index: int = Field(..., description="End index of summarized messages")
    token_count: int = Field(default=0, description="Token count of the summary")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when summary was created",
    )


class CompactionConfig(BaseModel):
    """Configuration for context compaction behavior."""

    max_tokens: int = Field(
        default=4000,
        description="Maximum tokens for compacted context",
    )
    summary_model_type: TaskType = Field(
        default=TaskType.FAST,
        description="Task type for summarization (determines model)",
    )
    recent_messages_to_keep: int = Field(
        default=10,
        description="Number of recent messages to keep intact",
    )
    messages_per_summary: int = Field(
        default=20,
        description="Target number of messages per summary",
    )
    encoding_name: str = Field(
        default="cl100k_base",
        description="Tiktoken encoding name for token counting",
    )


class ContextCompactor:
    """
    Manages conversation history compaction for context window management.

    This class provides:
    1. Token counting for messages using tiktoken
    2. LLM-based summarization of message groups
    3. Context compaction with recency bias
    4. Neo4j storage for persistent summaries
    5. Retrieval of relevant summaries

    Architecture:
    - Recent messages (configurable count) are kept intact
    - Older messages are grouped and summarized
    - Summaries are stored in Neo4j for future retrieval
    - Total output stays within token limit

    Example:
        ```python
        router = ModelRouter()
        compactor = ContextCompactor(model_router=router)

        messages = [Message(role="user", content=f"Message {i}") for i in range(100)]
        compacted = await compactor.compact(messages, max_tokens=4000)
        # compacted will have summaries for old messages + recent messages intact
        ```
    """

    def __init__(
        self,
        model_router: ModelRouter,
        neo4j_connector: Neo4jConnector | None = None,
        config: CompactionConfig | None = None,
    ) -> None:
        """
        Initialize the ContextCompactor.

        Args:
            model_router: ModelRouter for LLM calls (summarization)
            neo4j_connector: Optional Neo4j connector for summary storage
            config: Optional configuration (uses defaults if not provided)
        """
        self.model_router = model_router
        self.neo4j_connector = neo4j_connector
        self.config = config or CompactionConfig()
        self._encoding = tiktoken.get_encoding(self.config.encoding_name)

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string using tiktoken.

        Args:
            text: The text to count tokens for

        Returns:
            Number of tokens in the text
        """
        if not text:
            return 0
        return len(self._encoding.encode(text))

    def count_message_tokens(self, messages: list[Message]) -> int:
        """
        Count total tokens in a list of messages.

        This includes both role and content tokens, plus message formatting overhead.

        Args:
            messages: List of Message objects

        Returns:
            Total token count for all messages
        """
        if not messages:
            return 0

        total = 0
        for message in messages:
            # Count role tokens (approximate overhead per message)
            total += self.count_tokens(message.role) + 4  # Role + formatting overhead
            total += self.count_tokens(message.content)
        return total

    async def summarize(self, messages: list[Message]) -> str:
        """
        Summarize a list of messages using the LLM.

        Uses the configured task type (default: FAST) for model selection.

        Args:
            messages: List of messages to summarize

        Returns:
            Summary string

        Raises:
            ValueError: If messages list is empty
        """
        if not messages:
            raise ValueError("Cannot summarize empty messages")

        # Build the summarization prompt
        formatted_messages = "\n".join(
            f"{m.role}: {m.content}" for m in messages
        )

        prompt = f"""Summarize the following conversation concisely, preserving key information and context:

{formatted_messages}

Provide a brief summary that captures:
1. Main topics discussed
2. Key decisions or conclusions
3. Important context for future reference

Summary:"""

        summary = await self.model_router.route(
            task_type=self.config.summary_model_type,
            messages=[{"role": "user", "content": prompt}],
        )

        logger.debug(
            "Summarized %d messages into %d tokens",
            len(messages),
            self.count_tokens(summary),
        )

        return summary

    async def compact(
        self,
        messages: list[Message],
        max_tokens: int | None = None,
        conversation_id: str | None = None,
    ) -> list[Message]:
        """
        Compact conversation history to fit within token limit.

        Strategy:
        1. Keep recent messages intact (configurable count)
        2. Summarize older messages in groups
        3. Return compacted history under token limit

        Args:
            messages: Full conversation history
            max_tokens: Override for max token limit
            conversation_id: Optional conversation ID for summary storage

        Returns:
            Compacted list of messages fitting within token limit
        """
        if not messages:
            return []

        target_max = max_tokens or self.config.max_tokens
        current_tokens = self.count_message_tokens(messages)

        # If already under limit, return as-is
        if current_tokens <= target_max:
            return messages

        logger.info(
            "Compacting %d messages (%d tokens) to fit within %d tokens",
            len(messages),
            current_tokens,
            target_max,
        )

        # Split into recent (keep intact) and old (to summarize)
        keep_count = min(self.config.recent_messages_to_keep, len(messages))
        recent_messages = messages[-keep_count:] if keep_count > 0 else []
        old_messages = messages[:-keep_count] if keep_count > 0 else messages

        # Calculate token budget for summaries
        recent_tokens = self.count_message_tokens(recent_messages)
        summary_budget = target_max - recent_tokens

        if summary_budget <= 0:
            # Even recent messages exceed budget - summarize them too
            logger.warning(
                "Recent messages exceed token budget, summarizing all"
            )
            summary = await self.summarize(messages)
            return [Message(role="system", content=f"[Summary of previous conversation]: {summary}")]

        # Group and summarize old messages
        summaries: list[str] = []
        group_size = self.config.messages_per_summary

        for i in range(0, len(old_messages), group_size):
            group = old_messages[i : i + group_size]
            summary = await self.summarize(group)
            summaries.append(summary)

            # Store summary if Neo4j is configured and conversation_id provided
            if self.neo4j_connector and conversation_id:
                await self.store_summary(
                    summary=summary,
                    conversation_id=conversation_id,
                    metadata={
                        "message_count": len(group),
                        "start_index": i,
                        "end_index": i + len(group) - 1,
                    },
                )

        # Combine summaries into a context message
        combined_summary = "\n---\n".join(summaries)

        # Check if combined summary fits in budget
        summary_tokens = self.count_tokens(combined_summary)
        if summary_tokens > summary_budget:
            # Recursively summarize the summaries
            summary_messages = [Message(role="system", content=s) for s in summaries]
            final_summary = await self.summarize(summary_messages)
            combined_summary = final_summary

        # Build final compacted message list
        compacted = [
            Message(
                role="system",
                content=f"[Summary of previous conversation]:\n{combined_summary}",
            )
        ] + recent_messages

        final_tokens = self.count_message_tokens(compacted)
        logger.info(
            "Compacted to %d messages (%d tokens)",
            len(compacted),
            final_tokens,
        )

        return compacted

    async def store_summary(
        self,
        summary: str,
        conversation_id: str,
        metadata: dict[str, Any],
    ) -> str:
        """
        Store a summary in Neo4j graph.

        Args:
            summary: The summary text
            conversation_id: ID of the conversation
            metadata: Additional metadata (message_count, start_index, etc.)

        Returns:
            The element_id of the created node

        Raises:
            RuntimeError: If Neo4j connector is not configured
        """
        if self.neo4j_connector is None:
            raise RuntimeError("Neo4j connector not configured")

        properties: dict[str, Any] = {
            "content": summary,
            "conversation_id": conversation_id,
            "token_count": self.count_tokens(summary),
            "created_at": datetime.now(UTC).isoformat(),
            **metadata,
        }

        node_id = await self.neo4j_connector.create_node(
            labels=["Summary", "ConversationContext"],
            properties=properties,
        )

        logger.debug("Stored summary node: %s", node_id)
        return node_id

    async def retrieve_relevant(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant summaries from Neo4j.

        Uses text matching for relevance. For semantic search,
        consider integrating vector embeddings.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of summary dictionaries

        Raises:
            RuntimeError: If Neo4j connector is not configured
        """
        if self.neo4j_connector is None:
            raise RuntimeError("Neo4j connector not configured")

        # Basic text search - for production, use vector embeddings
        cypher = """
            MATCH (s:Summary)
            WHERE s.content CONTAINS $query
            RETURN s.content as content, s.conversation_id as conversation_id,
                   s.message_count as message_count, s.created_at as created_at
            ORDER BY s.created_at DESC
            LIMIT $limit
        """

        results = await self.neo4j_connector.query(
            cypher=cypher,
            params={"query": query, "limit": limit},
        )

        logger.debug("Retrieved %d relevant summaries", len(results))
        return results

    async def retrieve_by_conversation(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Retrieve summaries for a specific conversation.

        Args:
            conversation_id: The conversation ID to filter by
            limit: Maximum number of results

        Returns:
            List of summary dictionaries

        Raises:
            RuntimeError: If Neo4j connector is not configured
        """
        if self.neo4j_connector is None:
            raise RuntimeError("Neo4j connector not configured")

        cypher = """
            MATCH (s:Summary)
            WHERE s.conversation_id = $conversation_id
            RETURN s.content as content, s.conversation_id as conversation_id,
                   s.message_count as message_count, s.start_index as start_index,
                   s.end_index as end_index, s.created_at as created_at
            ORDER BY s.start_index ASC
            LIMIT $limit
        """

        results = await self.neo4j_connector.query(
            cypher=cypher,
            params={"conversation_id": conversation_id, "limit": limit},
        )

        return results


__all__ = [
    "CompactionConfig",
    "ContextCompactor",
    "Message",
    "Summary",
]
