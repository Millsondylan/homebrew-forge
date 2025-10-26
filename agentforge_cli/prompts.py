"""System prompt management for AgentForge agents."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .config import load_config, save_config


@dataclass
class PromptRender:
    system_prompt: str
    rules: List[str]
    verification: List[str]


class SystemPromptManager:
    """Generate disciplined system prompts for agent runs."""

    def __init__(self) -> None:
        self._config = load_config()

    @property
    def rules(self) -> List[str]:
        return list(self._config.get("prompts", {}).get("rules", []))

    @property
    def base_template(self) -> str:
        return self._config.get("prompts", {}).get("base", "")

    @property
    def default_verification(self) -> List[str]:
        return list(self._config.get("prompts", {}).get("default_verification", []))

    def render(
        self,
        task_description: str,
        *,
        context: Optional[Iterable[str]] = None,
        verification_steps: Optional[Iterable[str]] = None,
    ) -> PromptRender:
        context_lines = [line.strip() for line in (context or []) if line and line.strip()]
        verification = [step.strip() for step in (verification_steps or self.default_verification) if step]
        if not verification:
            verification = ["Run logical checks.", "Run empirical validation."]

        context_section = "\n".join(context_lines) if context_lines else "No relevant memory retrieved."
        rules_section = "\n".join(f"- {rule}" for rule in self.rules)
        verification_section = "\n".join(f"- {step}" for step in verification)

        template = self.base_template or textwrap.dedent(
            """
            You are AgentForge.
            Task: {task_description}

            Discipline:
            {rules}

            Memory:
            {context}

            Verification:
            {verification}
            """
        ).strip()

        system_prompt = template.format(
            task_description=task_description,
            rules=rules_section,
            context=context_section,
            verification=verification_section,
        )
        return PromptRender(system_prompt=system_prompt, rules=self.rules, verification=verification)

    def append_rule(self, rule: str) -> None:
        prompts = self._config.setdefault("prompts", {})
        rules = prompts.setdefault("rules", self.rules)
        if rule not in rules:
            rules.append(rule)
            save_config(self._config)


def default_prompt_manager() -> SystemPromptManager:
    return SystemPromptManager()


__all__ = ["SystemPromptManager", "PromptRender", "default_prompt_manager"]
