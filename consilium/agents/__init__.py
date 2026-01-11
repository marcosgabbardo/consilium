"""Agent framework for investor personalities and specialists."""

from consilium.agents.base import BaseAgent, InvestorAgent, SpecialistAgent
from consilium.agents.registry import AgentRegistry

__all__ = ["BaseAgent", "InvestorAgent", "SpecialistAgent", "AgentRegistry"]
