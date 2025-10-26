"""Google Gemini authentication provider."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..provider import AuthProvider, OAuthMetadata


class GeminiProvider(AuthProvider):
    name = "gemini"
    display_name = "Google Gemini"
    api_key_env = "GEMINI_API_KEY"
    supports_oauth = True

    def oauth_metadata(self, config: Dict[str, Any]) -> Optional[OAuthMetadata]:
        provider_cfg: Dict[str, Any] = config.get("providers", {}).get(self.name, {})
        oauth_cfg: Dict[str, Any] = provider_cfg.get("oauth", {})
        authorize_url = oauth_cfg.get("authorize_url")
        token_url = oauth_cfg.get("token_url")
        client_id = oauth_cfg.get("client_id")
        scopes = tuple(oauth_cfg.get("scopes", []))
        if not (authorize_url and token_url and client_id and scopes):
            return None
        audience = oauth_cfg.get("audience")
        extra_params = oauth_cfg.get("extra_params", {})
        return OAuthMetadata(
            authorize_url=authorize_url,
            token_url=token_url,
            client_id=client_id,
            scopes=scopes,
            audience=audience,
            extra_params=extra_params,
        )


__all__ = ["GeminiProvider"]
