"""
AgentForge CLI package.
"""

from importlib.metadata import version, PackageNotFoundError


def get_version() -> str:
    """Return the installed package version."""
    try:
        return version("agentforge-cli")
    except PackageNotFoundError:
        return "0.0.0"


__all__ = ["get_version"]
