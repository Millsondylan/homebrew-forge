from __future__ import annotations

import threading
import time

import pytest
import requests

from agentforge_cli.oauth import OAuthRedirectServer, find_open_port, run_listener, validate_redirect_uri


def test_validate_redirect_uri_accepts_localhost() -> None:
    uri = "http://127.0.0.1:8888/callback"
    assert validate_redirect_uri(uri) == uri


def test_validate_redirect_uri_rejects_remote_host() -> None:
    with pytest.raises(ValueError):
        validate_redirect_uri("http://example.com/callback")


def test_oauth_listener_captures_parameters() -> None:
    port = find_open_port()
    server = OAuthRedirectServer(port, "state-123", ["/callback"])

    def trigger_request() -> None:
        time.sleep(0.2)
        requests.get(
            f"http://127.0.0.1:{port}/callback",
            params={"code": "abc", "state": "state-123"},
            timeout=5,
        )

    thread = threading.Thread(target=trigger_request, daemon=True)
    thread.start()
    params = run_listener(server, timeout=5)
    assert params["code"] == "abc"
    assert params["state"] == "state-123"


def test_oauth_listener_rejects_bad_state() -> None:
    port = find_open_port()
    server = OAuthRedirectServer(port, "expected", ["/callback"])

    def trigger_request() -> None:
        time.sleep(0.2)
        requests.get(
            f"http://127.0.0.1:{port}/callback",
            params={"code": "xyz", "state": "wrong"},
            timeout=5,
        )

    thread = threading.Thread(target=trigger_request, daemon=True)
    thread.start()
    with pytest.raises(ValueError):
        run_listener(server, timeout=5)
