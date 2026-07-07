"""Agentic generation — the Actor-Critic-Boss loop and the Session 12 agent.

``boss.py`` orchestrates iterative refinement; ``critic.py`` is the read-only
auditor. ``agent_loop.py`` implements the manual Responses API estimation agent.
This layer MAY import ``app.generation.conversation`` (the multi-turn substrate
it runs on); the reverse is forbidden.
"""

from app.generation.agentic.agent_loop import format_trace, run_agent
from app.generation.agentic.agent_schemas import AgentEstimate, AgentResult, AgentStep

__all__ = [
    "AgentEstimate",
    "AgentResult",
    "AgentStep",
    "format_trace",
    "run_agent",
]
