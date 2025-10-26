"""
Application context utilities for AgentForge CLI runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .config import get_paths, load_config


@dataclass
class ForgeApp:
    """
    Container for runtime state shared across CLI commands.

    The context keeps the latest configuration snapshot alongside resolved
    filesystem paths so subcommands can refresh or mutate configuration in a
    consistent way.
    """

    config: Dict[str, Any]
    paths: Dict[str, Any]
    state: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def bootstrap(cls) -> ForgeApp:
        """
        Create a context using the persisted configuration on disk.
        """
        return cls(config=load_config(), paths=get_paths())

    def refresh(self) -> None:
        """
        Reload on-disk configuration and paths to capture mutations made by
        previous commands.
        """
        self.config = load_config()
        self.paths = get_paths()


__all__ = ["ForgeApp"]
