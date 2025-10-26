"""Encrypted credential storage for AgentForge providers."""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet

try:  # pragma: no cover - optional dependency failures handled gracefully
    import keyring
    from keyring.errors import KeyringError
except Exception:  # pragma: no cover
    keyring = None  # type: ignore[assignment]
    KeyringError = Exception  # type: ignore[misc]


class CredentialStore:
    """Persist provider credentials encrypted at rest."""

    def __init__(self, credentials_path: Path, key_path: Path, service_name: str = "agentforge") -> None:
        self.credentials_path = credentials_path
        self.key_path = key_path
        self.service_name = service_name
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(self._load_or_create_key())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def save(self, provider: str, payload: Dict[str, Any]) -> None:
        store = self._load_store()
        serialized = json.dumps(payload).encode("utf-8")
        encrypted = self._fernet.encrypt(serialized).decode("utf-8")
        store.setdefault("providers", {})[provider] = {
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "data": encrypted,
        }
        self._write_store(store)

    def load(self, provider: str) -> Optional[Dict[str, Any]]:
        store = self._load_store()
        entry = store.get("providers", {}).get(provider)
        if not entry:
            return None
        decrypted = self._fernet.decrypt(entry["data"].encode("utf-8"))
        return json.loads(decrypted.decode("utf-8"))

    def delete(self, provider: str) -> None:
        store = self._load_store()
        providers = store.get("providers", {})
        if provider in providers:
            providers.pop(provider)
            self._write_store(store)

    def listed_providers(self) -> Dict[str, Dict[str, Any]]:
        store = self._load_store()
        providers = store.get("providers", {})
        return {name: {"updated_at": data.get("updated_at")} for name, data in providers.items()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_or_create_key(self) -> bytes:
        key = self._read_key_from_keyring()
        if key:
            return key
        if self.key_path.exists():
            return self.key_path.read_bytes()
        key = Fernet.generate_key()
        if not self._persist_key_in_keyring(key):
            self._persist_key_to_file(key)
        return key

    def _read_key_from_keyring(self) -> Optional[bytes]:
        if keyring is None:  # pragma: no cover - environment dependent
            return None
        try:
            stored = keyring.get_password(self.service_name, "credentials_key")
        except KeyringError:  # pragma: no cover - backend issues
            return None
        if stored:
            return stored.encode("utf-8")
        return None

    def _persist_key_in_keyring(self, key: bytes) -> bool:
        if keyring is None:  # pragma: no cover
            return False
        try:
            keyring.set_password(self.service_name, "credentials_key", key.decode("utf-8"))
            return True
        except KeyringError:  # pragma: no cover
            return False

    def _persist_key_to_file(self, key: bytes) -> None:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        with self.key_path.open("wb") as fh:
            fh.write(key)
        os.chmod(self.key_path, stat.S_IRUSR | stat.S_IWUSR)

    def _load_store(self) -> Dict[str, Any]:
        if not self.credentials_path.exists():
            return {"version": 1, "providers": {}}
        with self.credentials_path.open("r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError:
                data = {"version": 1, "providers": {}}
        data.setdefault("version", 1)
        data.setdefault("providers", {})
        return data

    def _write_store(self, data: Dict[str, Any]) -> None:
        tmp_path = self.credentials_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, self.credentials_path)


__all__ = ["CredentialStore"]
