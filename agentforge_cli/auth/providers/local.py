"""Local provider for offline models or mock adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ..credential_store import CredentialStore
from ..provider import AuthProvider, OAuthMetadata


class LocalProvider(AuthProvider):
    name = "local"
    display_name = "Local"
    api_key_env: Optional[str] = None
    supports_oauth = False

    def oauth_metadata(self, config: Dict[str, Any]) -> Optional[OAuthMetadata]:  # pragma: no cover - not supported
        return None

    def store_workspace(self, store: CredentialStore, workspace: Path) -> Dict[str, Any]:
        record = self._load_record(store)
        record.setdefault("modes", {})["filesystem"] = {"workspace": str(workspace)}
        record["active"] = "filesystem"
        store.save(self.name, record)
        return record

    def load_workspace(self, store: CredentialStore) -> Optional[Path]:
        record = store.load(self.name)
        if not record:
            return None
        value = record.get("modes", {}).get("filesystem", {}).get("workspace")
        return Path(value) if value else None


__all__ = ["LocalProvider"]
