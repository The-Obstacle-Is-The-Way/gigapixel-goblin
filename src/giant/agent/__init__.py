"""Agent module for GIANT navigation.

This module provides the core agent components including:
- Trajectory tracking and serialization
- Conversation context management
- GIANT Agent core loop (Spec-09)
"""

from giant.agent.context import ContextManager
from giant.agent.runner import AgentConfig, GIANTAgent, RunResult
from giant.agent.trajectory import Trajectory, Turn

__all__ = [
    "AgentConfig",
    "ContextManager",
    "GIANTAgent",
    "RunResult",
    "Trajectory",
    "Turn",
]
