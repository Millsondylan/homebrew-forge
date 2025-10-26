"""Ollama provider for local model runtime."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..credential_store import CredentialStore
from ..provider import AuthProvider, OAuthMetadata


class OllamaProvider(AuthProvider):
    name = "ollama"
    display_name = "Ollama"
    api_key_env: Optional[str] = None
    supports_oauth = False

    def oauth_metadata(self, config: Dict[str, Any]) -> Optional[OAuthMetadata]:  # pragma: no cover - not supported
        return None

    def store_endpoint(self, store: CredentialStore, base_url: str) -> Dict[str, Any]:
        sanitized = base_url.rstrip("/")
        if not sanitized.startswith("http"):
            raise ValueError("Ollama endpoint must be an HTTP(S) URL")
        record = self._load_record(store)
        record.setdefault("modes", {})["local"] = {"base_url": sanitized}
        record["active"] = "local"
        store.save(self.name, record)
        return record

    def load_endpoint(self, store: CredentialStore) -> Optional[str]:
        record = store.load(self.name)
        if not record:
            return None
        return record.get("modes", {}).get("local", {}).get("base_url")


__all__ = ["OllamaProvider"]
