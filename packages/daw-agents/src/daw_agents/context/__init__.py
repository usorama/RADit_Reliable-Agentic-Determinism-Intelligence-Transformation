"""
Context management module for DAW Agent Workbench.

This module provides:
- ContextCompactor: Manages conversation history compaction
- CompactionConfig: Configuration for compaction behavior
- Message: Message model for chat messages
- Summary: Summary model for compacted message groups
"""

from daw_agents.context.compaction import (
    CompactionConfig,
    ContextCompactor,
    Message,
    Summary,
)

__all__ = [
    "CompactionConfig",
    "ContextCompactor",
    "Message",
    "Summary",
]
