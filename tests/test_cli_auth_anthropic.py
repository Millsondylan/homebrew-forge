from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agentforge_cli.auth import AuthManager, CredentialStore, OAuthMetadata
from agentforge_cli.cli import cli
import agentforge_cli.cli as cli_module


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    home = tmp_path / "af_home"
    monkeypatch.setenv("AGENTFORGE_HOME", str(home))
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    return runner


def _credential_store(tmp_path: Path) -> CredentialStore:
    home = tmp_path / "af_home"
    return CredentialStore(home / "credentials.json", home / ".credentials.key")


def test_anthropic_api_key_storage(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(cli, ["auth", "anthropic", "--api-key", "sk-demo"])
    assert result.exit_code == 0, result.output
    store = _credential_store(tmp_path)
    record = store.load("anthropic")
    assert record and record["modes"]["api_key"]["api_key"] == "sk-demo"


def test_anthropic_oauth_flow(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = OAuthMetadata(
        authorize_url="https://console.anthropic.com/oauth/authorize",
        token_url="https://api.anthropic.com/oauth/token",
        client_id="client-from-config",
        scopes=("user:profile",),
        extra_params={"redirect_uri": "http://127.0.0.1:9999/callback"},
    )

    def fake_metadata(self, name: str) -> OAuthMetadata:  # type: ignore[override]
        assert name == "anthropic"
        return metadata

    monkeypatch.setattr(AuthManager, "oauth_metadata", fake_metadata, raising=False)

    def fake_flow(**kwargs):
        return {
            "tokens": {"access_token": "demo-token", "expires_in": 3600},
            "received_at": "2025-10-26T00:00:00Z",
            "redirect_uri": kwargs.get("redirect_uri"),
            "client_id": kwargs.get("client_id"),
            "scopes": list(kwargs.get("scopes", [])),
        }

    monkeypatch.setattr(cli_module, "perform_pkce_oauth", fake_flow)

    result = runner.invoke(cli, ["auth", "anthropic", "--oauth", "--no-browser"])
    assert result.exit_code == 0, result.output
    store = _credential_store(tmp_path)
    record = store.load("anthropic")
    assert record and "oauth" in record["modes"]
