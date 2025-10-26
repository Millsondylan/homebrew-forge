"""
AgentForge CLI package.
"""

from importlib.metadata import PackageNotFoundError, version

from .app import ForgeApp


def get_version() -> str:
    """Return the installed package version."""
    try:
        return version("agentforge-cli")
    except PackageNotFoundError:
        return "0.0.0"


__all__ = ["ForgeApp", "get_version"]
