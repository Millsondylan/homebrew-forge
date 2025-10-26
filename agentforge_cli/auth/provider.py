"""Auth provider base classes and metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .credential_store import CredentialStore


@dataclass(frozen=True)
class OAuthMetadata:
    """Static metadata describing an OAuth authorization flow."""

    authorize_url: str
    token_url: str
    client_id: str
    scopes: tuple[str, ...]
    audience: Optional[str] = None
    extra_params: Dict[str, str] = field(default_factory=dict)


class AuthProvider(ABC):
    """Common interface for authentication providers."""

    name: str
    display_name: str
    api_key_env: Optional[str] = None
    supports_oauth: bool = False

    def store_api_key(self, store: CredentialStore, api_key: str) -> Dict[str, Any]:
        """Persist an API key and activate it for the provider."""

        sanitized = api_key.strip()
        if not sanitized:
            raise ValueError("API key cannot be empty")
        record = self._load_record(store)
        record.setdefault("modes", {})["api_key"] = {"api_key": sanitized}
        record["active"] = "api_key"
        store.save(self.name, record)
        return record

    def load_api_key(self, store: CredentialStore) -> Optional[str]:
        record = store.load(self.name)
        if not record:
            return None
        api = record.get("modes", {}).get("api_key", {})
        return api.get("api_key")

    def load_oauth_tokens(self, store: CredentialStore) -> Optional[Dict[str, Any]]:
        record = store.load(self.name)
        if not record:
            return None
        return record.get("modes", {}).get("oauth")

    def clear_credentials(self, store: CredentialStore) -> None:
        store.delete(self.name)

    @abstractmethod
    def oauth_metadata(self, config: Dict[str, Any]) -> Optional[OAuthMetadata]:
        """Return OAuth metadata if the provider supports OAuth."""

    def persist_oauth_tokens(self, store: CredentialStore, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.supports_oauth:
            raise RuntimeError(f"Provider {self.name} does not support OAuth")
        record = self._load_record(store)
        record.setdefault("modes", {})["oauth"] = payload
        record["active"] = "oauth"
        store.save(self.name, record)
        return record

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_record(self, store: CredentialStore) -> Dict[str, Any]:
        record = store.load(self.name)
        if record is None:
            record = {"modes": {}, "active": None, "provider": self.name}
        return record


__all__ = ["AuthProvider", "OAuthMetadata"]
