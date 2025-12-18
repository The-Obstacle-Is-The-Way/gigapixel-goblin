"""Agent module for GIANT navigation.

This module provides the core agent components including:
- Trajectory tracking and serialization
- Conversation context management
"""

from giant.agent.context import ContextManager
from giant.agent.trajectory import Trajectory, Turn

__all__ = ["ContextManager", "Trajectory", "Turn"]
