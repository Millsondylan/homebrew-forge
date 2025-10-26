from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

from agentforge_cli.auth import AuthManager, CredentialStore


@pytest.fixture
def credential_store(tmp_path: Path) -> CredentialStore:
    return CredentialStore(tmp_path / "credentials.json", tmp_path / ".key")


@pytest.fixture
def config() -> Dict:
    return {
        "providers": {
            "anthropic": {
                "oauth": {
                    "authorize_url": "https://console.anthropic.com/oauth/authorize",
                    "token_url": "https://api.anthropic.com/oauth/token",
                    "client_id": "test-client",
                    "scopes": ["user:profile"],
                }
            },
            "gemini": {
                "oauth": {
                    "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                    "token_url": "https://oauth2.googleapis.com/token",
                    "client_id": "gemini-client",
                    "scopes": ["https://www.googleapis.com/auth/generative-language.retriever"],
                }
            },
            "ollama": {
                "http": {"base_url": "http://localhost:11434"}
            },
            "local": {},
        }
    }


def test_store_and_load_api_key(credential_store: CredentialStore, config: Dict) -> None:
    manager = AuthManager(credential_store, lambda: config)
    manager.store_api_key("anthropic", "sk-test-123")
    assert manager.get_api_key("anthropic") == "sk-test-123"
    record = manager.credential_record("anthropic")
    assert record and record["active"] == "api_key"


def test_oauth_metadata_fetch(credential_store: CredentialStore, config: Dict) -> None:
    manager = AuthManager(credential_store, lambda: config)
    metadata = manager.oauth_metadata("anthropic")
    assert metadata.authorize_url.endswith("/oauth/authorize")
    assert "user:profile" in metadata.scopes


def test_list_status_includes_registered_providers(credential_store: CredentialStore, config: Dict) -> None:
    manager = AuthManager(credential_store, lambda: config)
    status = manager.list_status()
    assert "anthropic" in status
    manager.store_api_key("gemini", "gm-test")
    updated = manager.list_status()["gemini"]["updated_at"]
    assert updated is not None


def test_ollama_endpoint_roundtrip(credential_store: CredentialStore, config: Dict) -> None:
    manager = AuthManager(credential_store, lambda: config)
    provider = manager.provider("ollama")
    provider.store_endpoint(credential_store, "http://localhost:11434")
    assert provider.load_endpoint(credential_store) == "http://localhost:11434"
