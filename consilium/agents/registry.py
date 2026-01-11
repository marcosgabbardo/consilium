"""Agent registry for discovery, instantiation, and management."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from consilium.config import Settings, get_settings
from consilium.core.enums import AgentType, InvestmentStyle
from consilium.core.models import AgentProfile
from consilium.agents.base import BaseAgent, InvestorAgent, SpecialistAgent
from consilium.llm.client import ClaudeClient
from consilium.llm.prompts import PromptBuilder, PromptLoader


class AgentRegistry:
    """
    Central registry for agent discovery and instantiation.

    Handles:
    - Loading agent configurations from YAML prompts
    - Agent instantiation with dependency injection
    - Agent filtering and lookup
    - Weight override management
    """

    def __init__(
        self,
        settings: Settings | None = None,
        llm_client: ClaudeClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm_client = llm_client
        self._prompt_loader = PromptLoader(self._settings.prompts_dir)
        self._prompt_builder = PromptBuilder(self._prompt_loader)
        self._agents: dict[str, BaseAgent] = {}
        self._profiles: dict[str, AgentProfile] = {}
        self._loaded = False

    def _ensure_llm_client(self) -> ClaudeClient:
        """Ensure LLM client is available."""
        if self._llm_client is None:
            self._llm_client = ClaudeClient(self._settings)
        return self._llm_client

    def _load_profiles(self) -> None:
        """Load all agent profiles from YAML files."""
        if self._loaded:
            return

        prompts_dir = self._settings.prompts_dir

        # Load investor profiles
        investors_dir = prompts_dir / "investors"
        if investors_dir.exists():
            for yaml_file in investors_dir.glob("*.yaml"):
                profile = self._load_profile_from_yaml(yaml_file, AgentType.INVESTOR)
                if profile:
                    self._profiles[profile.id] = profile

        # Load specialist profiles
        specialists_dir = prompts_dir / "specialists"
        if specialists_dir.exists():
            for yaml_file in specialists_dir.glob("*.yaml"):
                profile = self._load_profile_from_yaml(yaml_file, AgentType.SPECIALIST)
                if profile:
                    self._profiles[profile.id] = profile

        self._loaded = True

    def _load_profile_from_yaml(
        self, yaml_path: Path, agent_type: AgentType
    ) -> AgentProfile | None:
        """Load agent profile from YAML file."""
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Get weight from settings override or YAML default
            weight = self._settings.weights.get_weight(data["id"])

            style = None
            if "style" in data:
                try:
                    style = InvestmentStyle(data["style"])
                except ValueError:
                    pass

            return AgentProfile(
                id=data["id"],
                name=data["name"],
                agent_type=agent_type,
                investment_style=style,
                weight=weight,
                description=data.get("description", ""),
                enabled=data.get("enabled", True),
            )
        except Exception as e:
            print(f"Warning: Failed to load agent profile from {yaml_path}: {e}")
            return None

    def _instantiate_investor(self, agent_id: str) -> InvestorAgent:
        """Instantiate an investor agent from YAML config."""
        data = self._prompt_loader.load_investor_prompt(agent_id)
        profile = self._profiles[agent_id]

        return InvestorAgent(
            profile=profile,
            llm_client=self._ensure_llm_client(),
            prompt_builder=self._prompt_builder,
            persona=data.get("persona", ""),
            philosophy=data.get("philosophy", ""),
            principles=data.get("principles", []),
            famous_quotes=data.get("famous_quotes", []),
        )

    def _instantiate_specialist(self, agent_id: str) -> SpecialistAgent:
        """Instantiate a specialist agent from YAML config."""
        data = self._prompt_loader.load_specialist_prompt(agent_id)
        profile = self._profiles[agent_id]

        return SpecialistAgent(
            profile=profile,
            llm_client=self._ensure_llm_client(),
            prompt_builder=self._prompt_builder,
            focus_area=data.get("focus_area", ""),
            methodology=data.get("methodology", ""),
        )

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        """Get or instantiate an agent by ID."""
        self._load_profiles()

        if agent_id not in self._profiles:
            return None

        if agent_id not in self._agents:
            profile = self._profiles[agent_id]
            if profile.agent_type == AgentType.INVESTOR:
                self._agents[agent_id] = self._instantiate_investor(agent_id)
            else:
                self._agents[agent_id] = self._instantiate_specialist(agent_id)

        return self._agents[agent_id]

    def get_profile(self, agent_id: str) -> AgentProfile | None:
        """Get agent profile by ID."""
        self._load_profiles()
        return self._profiles.get(agent_id)

    def list_profiles(
        self,
        agent_type: AgentType | None = None,
        enabled_only: bool = True,
    ) -> list[AgentProfile]:
        """List all agent profiles, optionally filtered."""
        self._load_profiles()

        profiles = list(self._profiles.values())

        if agent_type:
            profiles = [p for p in profiles if p.agent_type == agent_type]

        if enabled_only:
            profiles = [p for p in profiles if p.enabled]

        return sorted(profiles, key=lambda p: (-float(p.weight), p.name))

    def list_agents(
        self,
        agent_type: str | None = None,
        enabled_only: bool = True,
    ) -> list[AgentProfile]:
        """List agent profiles with optional type filter (string version)."""
        atype = None
        if agent_type:
            try:
                atype = AgentType(agent_type.upper())
            except ValueError:
                pass

        return self.list_profiles(agent_type=atype, enabled_only=enabled_only)

    def get_investors(self, filter_ids: list[str] | None = None) -> list[InvestorAgent]:
        """Get all investor agents, optionally filtered by IDs."""
        self._load_profiles()

        investor_ids = [
            p.id
            for p in self._profiles.values()
            if p.agent_type == AgentType.INVESTOR and p.enabled
        ]

        if filter_ids:
            investor_ids = [i for i in investor_ids if i in filter_ids]

        agents = []
        for agent_id in investor_ids:
            agent = self.get_agent(agent_id)
            if agent and isinstance(agent, InvestorAgent):
                agents.append(agent)

        return agents

    def get_specialists(
        self, filter_ids: list[str] | None = None
    ) -> list[SpecialistAgent]:
        """Get all specialist agents, optionally filtered by IDs."""
        self._load_profiles()

        specialist_ids = [
            p.id
            for p in self._profiles.values()
            if p.agent_type == AgentType.SPECIALIST and p.enabled
        ]

        if filter_ids:
            specialist_ids = [i for i in specialist_ids if i in filter_ids]

        agents = []
        for agent_id in specialist_ids:
            agent = self.get_agent(agent_id)
            if agent and isinstance(agent, SpecialistAgent):
                agents.append(agent)

        return agents

    def get_all_agents(
        self, filter_ids: list[str] | None = None
    ) -> tuple[list[InvestorAgent], list[SpecialistAgent]]:
        """Get all agents as (investors, specialists) tuple."""
        return (
            self.get_investors(filter_ids),
            self.get_specialists(filter_ids),
        )
