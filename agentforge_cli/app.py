"""
Application context utilities for AgentForge CLI runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .auth import AuthManager, CredentialStore
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
    _auth_manager: AuthManager | None = field(default=None, init=False, repr=False)

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
        if self._auth_manager is not None:
            # Refresh credential store paths in case the config root moved.
            self._auth_manager = AuthManager(
                CredentialStore(self.paths["credentials_file"], self.paths["credential_key_file"]),
                load_config,
            )

    def auth(self) -> AuthManager:
        if self._auth_manager is None:
            store = CredentialStore(self.paths["credentials_file"], self.paths["credential_key_file"])
            self._auth_manager = AuthManager(store, load_config)
        return self._auth_manager


__all__ = ["ForgeApp"]
