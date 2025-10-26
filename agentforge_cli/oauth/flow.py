"""Reusable OAuth flow helpers built on PKCE."""

from __future__ import annotations

import time
import webbrowser
from typing import Dict, Iterable, Optional
from urllib.parse import urlencode, urlparse

import requests

from .listener import OAuthRedirectServer, find_open_port, run_listener, validate_redirect_uri
from .pkce import generate_code_challenge, generate_code_verifier


def perform_pkce_oauth(
    authorize_url: str,
    token_url: str,
    client_id: str,
    scopes: Iterable[str],
    redirect_uri: Optional[str] = None,
    extra_authorize_params: Optional[Dict[str, str]] = None,
    open_browser: bool = True,
    manual_code: Optional[str] = None,
    timeout: float = 180.0,
    audience: Optional[str] = None,
) -> Dict[str, any]:
    """Run an OAuth authorization code flow with PKCE."""

    if not client_id:
        raise ValueError("client_id is required for OAuth")

    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    state = generate_code_verifier(48)

    listener: Optional[OAuthRedirectServer] = None
    redirect = redirect_uri
    local_listener = False
    if redirect is None:
        port = find_open_port()
        redirect = f"http://127.0.0.1:{port}/callback"
    parsed_redirect = urlparse(redirect)
    if parsed_redirect.hostname in {"127.0.0.1", "localhost"}:
        validate_redirect_uri(redirect)
        port = parsed_redirect.port or find_open_port()
        path = parsed_redirect.path or "/callback"
        listener = OAuthRedirectServer(port, state, [path])
        redirect = f"http://127.0.0.1:{port}{path}"
        local_listener = manual_code is None

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect,
        "scope": " ".join(scopes),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if extra_authorize_params:
        params.update(extra_authorize_params)

    auth_url = f"{authorize_url}?{urlencode(params)}"

    if open_browser and manual_code is None:
        webbrowser.open(auth_url, new=1)

    code: Optional[str] = manual_code
    if code is None:
        if listener is not None:
            result = run_listener(listener, timeout=timeout)
            code = result.get("code")
        else:
            raise RuntimeError("No listener available and manual authorization code not provided")
    if not code:
        raise RuntimeError("Authorization code missing from OAuth flow")

    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": redirect,
    }
    if audience:
        data["audience"] = audience

    response = requests.post(token_url, data=data, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return {
        "tokens": payload,
        "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "redirect_uri": redirect,
        "client_id": client_id,
        "scopes": list(scopes),
    }


__all__ = ["perform_pkce_oauth"]
