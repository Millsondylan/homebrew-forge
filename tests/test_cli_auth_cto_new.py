from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agentforge_cli.cli import cli
from agentforge_cli.auth.credential_store import CredentialStore
from agentforge_cli.config import get_paths


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    return runner


def test_cto_new_session_store(runner: CliRunner) -> None:
    result = runner.invoke(
        cli,
        [
            "auth",
            "cto-new",
            "--session-id",
            "sess-123",
            "--cookie",
            "cookie-abc",
            "--organization-id",
            "org-789",
        ],
    )
    assert result.exit_code == 0, result.output
    paths = get_paths()
    store = CredentialStore(paths["credentials_file"], paths["credential_key_file"])
    record = store.load("cto_new")
    assert record["modes"]["session"]["organization_id"] == "org-789"
