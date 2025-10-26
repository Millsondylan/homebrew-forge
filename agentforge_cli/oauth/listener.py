"""Local OAuth redirect listener utilities."""

from __future__ import annotations

import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from socket import socket
from typing import Dict, Iterable, Optional
from urllib.parse import parse_qs, urlparse


def validate_redirect_uri(uri: str, allowed_hosts: Iterable[str] = ("127.0.0.1", "localhost")) -> str:
    """Validate that the redirect URI points to an allowed local host."""

    parsed = urlparse(uri)
    if parsed.scheme != "http":
        raise ValueError("Redirect URI must use http scheme for local listeners")
    if parsed.hostname not in allowed_hosts:
        raise ValueError(f"Host '{parsed.hostname}' not permitted for OAuth redirect")
    if parsed.port and parsed.port < 1024:
        raise ValueError("Redirect URI port must be >= 1024")
    return uri


class _OAuthHandler(BaseHTTPRequestHandler):
    server_version = "AgentForgeOAuth/1.0"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler naming)
        parsed = urlparse(self.path)
        if parsed.path not in self.server.allowed_paths:
            self._write_response(HTTPStatus.NOT_FOUND, "Invalid callback path")
            self.server.error = ValueError("Invalid redirect path")
            self.server.event.set()
            return

        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        state = params.get("state")
        if state != self.server.expected_state:
            self._write_response(HTTPStatus.BAD_REQUEST, "State mismatch. Please retry authentication.")
            self.server.error = ValueError("State parameter mismatch")
            self.server.event.set()
            return

        self._write_response(HTTPStatus.OK, "Authentication complete. You may close this window.")
        self.server.result = params
        self.server.event.set()

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - follow BaseHTTPRequestHandler signature
        return  # Suppress noisy CLI output

    def _write_response(self, status: HTTPStatus, message: str) -> None:
        payload = f"<html><body><h1>{status.value} {status.phrase}</h1><p>{message}</p></body></html>".encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class OAuthRedirectServer(HTTPServer):
    """HTTP server that captures a single OAuth redirect and records query parameters."""

    def __init__(self, port: int, expected_state: str, allowed_paths: Iterable[str]) -> None:
        super().__init__(("127.0.0.1", port), _OAuthHandler)
        self.expected_state = expected_state
        self.allowed_paths = tuple(allowed_paths)
        self.event = threading.Event()
        self.result: Optional[Dict[str, str]] = None
        self.error: Optional[Exception] = None


def find_open_port(start: int = 8765, end: int = 9999) -> int:
    for port in range(start, end + 1):
        with socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No open localhost ports available for OAuth listener")


def run_listener(server: OAuthRedirectServer, timeout: float = 120.0) -> Dict[str, str]:
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    try:
        if not server.event.wait(timeout):
            raise TimeoutError("Timed out waiting for OAuth redirect")
        if server.error:
            raise server.error
        if not server.result:
            raise RuntimeError("OAuth redirect did not return parameters")
        return server.result
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


__all__ = ["validate_redirect_uri", "OAuthRedirectServer", "find_open_port", "run_listener"]
