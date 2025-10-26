"""PKCE helpers for OAuth flows."""

from __future__ import annotations

import base64
import hashlib
import secrets
import string


def generate_code_verifier(length: int = 64) -> str:
    if length < 43 or length > 128:
        raise ValueError("PKCE code verifier length must be between 43 and 128")
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return challenge


__all__ = ["generate_code_verifier", "generate_code_challenge"]
