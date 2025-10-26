"""cto.new authentication provider."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..credential_store import CredentialStore
from ..provider import AuthProvider, OAuthMetadata


class CtoNewProvider(AuthProvider):
    name = "cto_new"
    display_name = "cto.new"
    supports_oauth = False  # Manual token management
    api_key_env: Optional[str] = None

    def oauth_metadata(self, config: Dict[str, Any]) -> Optional[OAuthMetadata]:  # pragma: no cover - not supported
        return None

    def store_session_tokens(
        self,
        store: CredentialStore,
        *,
        session_id: str,
        cookie: str,
        organization_id: str,
    ) -> Dict[str, Any]:
        payload = {
            "session_id": session_id.strip(),
            "cookie": cookie.strip(),
            "organization_id": organization_id.strip(),
        }
        record = self._load_record(store)
        record.setdefault("modes", {})["session"] = payload
        record["active"] = "session"
        store.save(self.name, record)
        return record


__all__ = ["CtoNewProvider"]
