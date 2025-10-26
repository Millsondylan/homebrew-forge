"""Authentication provider manager."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, Optional

from .credential_store import CredentialStore
from .provider import AuthProvider, OAuthMetadata
from .providers import (
    AnthropicProvider,
    CtoNewProvider,
    GeminiProvider,
    LocalProvider,
    OllamaProvider,
)


class AuthManager:
    """Coordinate provider authentication flows and credential storage."""

    def __init__(self, store: CredentialStore, config_provider: Callable[[], Dict]) -> None:
        self.store = store
        self._config_provider = config_provider
        self._providers: Dict[str, AuthProvider] = {}
        self._register_defaults()

    # ------------------------------------------------------------------
    # Provider registration and discovery
    # ------------------------------------------------------------------
    def _register_defaults(self) -> None:
        for provider in (
            AnthropicProvider(),
            GeminiProvider(),
            OllamaProvider(),
            LocalProvider(),
            CtoNewProvider(),
        ):
            self.register(provider)

    def register(self, provider: AuthProvider) -> None:
        self._providers[provider.name] = provider

    def providers(self) -> Iterable[AuthProvider]:
        return self._providers.values()

    def provider(self, name: str) -> AuthProvider:
        try:
            return self._providers[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"Unknown provider '{name}'") from exc

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------
    def store_api_key(self, name: str, api_key: str) -> Dict:
        provider = self.provider(name)
        if provider.api_key_env is None:
            raise RuntimeError(f"Provider '{name}' does not accept API keys")
        return provider.store_api_key(self.store, api_key)

    def get_api_key(self, name: str) -> Optional[str]:
        provider = self.provider(name)
        return provider.load_api_key(self.store)

    def clear(self, name: str) -> None:
        provider = self.provider(name)
        provider.clear_credentials(self.store)

    def credential_record(self, name: str) -> Optional[Dict]:
        return self.store.load(name)

    def list_status(self) -> Dict[str, Dict[str, Optional[str]]]:
        status = self.store.listed_providers()
        for provider in self.providers():
            status.setdefault(provider.name, {"updated_at": None})
        return status

    # ------------------------------------------------------------------
    # OAuth helpers
    # ------------------------------------------------------------------
    def oauth_metadata(self, name: str) -> OAuthMetadata:
        provider = self.provider(name)
        if not provider.supports_oauth:
            raise RuntimeError(f"Provider '{name}' does not support OAuth")
        config = self._config_provider()
        metadata = provider.oauth_metadata(config)
        if metadata is None:
            raise ValueError(f"OAuth metadata missing for provider '{name}'")
        return metadata

    def persist_oauth_tokens(self, name: str, payload: Dict) -> Dict:
        provider = self.provider(name)
        return provider.persist_oauth_tokens(self.store, payload)


__all__ = ["AuthManager"]
