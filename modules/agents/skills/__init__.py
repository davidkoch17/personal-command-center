"""Agent skills package — on-demand `claude -p` skills surfaced in the dashboard."""
from modules.agents.skills.idea_validator import runner as idea_validator
from modules.agents.skills import research

__all__ = ["idea_validator", "research"]
