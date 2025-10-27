"""
Discovery automation for AgentForge.

Analyzes repository structure, components, dependencies, and gaps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import subprocess


def discover_codebase(project_root: Path) -> Dict[str, Any]:
    """
    Analyze repository structure and return comprehensive data.

    Args:
        project_root: Root directory of the project

    Returns:
        Dictionary containing codebase structure and metadata
    """
    discovery = {
        "project_root": str(project_root),
        "python_files": [],
        "test_files": [],
        "config_files": [],
        "documentation_files": [],
        "cli_modules": [],
        "total_files": 0,
        "total_lines": 0,
    }

    # Find Python files
    for py_file in project_root.rglob("*.py"):
        if ".git" in str(py_file) or "__pycache__" in str(py_file):
            continue

        rel_path = py_file.relative_to(project_root)
        file_info = {
            "path": str(rel_path),
            "lines": _count_lines(py_file),
        }

        if "test_" in py_file.name or str(rel_path).startswith("tests/"):
            discovery["test_files"].append(file_info)
        elif "cli" in str(rel_path):
            discovery["cli_modules"].append(file_info)
        else:
            discovery["python_files"].append(file_info)

        discovery["total_lines"] += file_info["lines"]
        discovery["total_files"] += 1

    # Find config files
    for pattern in ["*.yaml", "*.yml", "*.toml", "*.json", "*.cfg", "*.ini"]:
        for config_file in project_root.glob(pattern):
            if ".git" in str(config_file):
                continue
            discovery["config_files"].append(str(config_file.relative_to(project_root)))

    # Find documentation
    for pattern in ["*.md", "*.rst", "*.txt"]:
        for doc_file in project_root.rglob(pattern):
            if ".git" in str(doc_file) or "node_modules" in str(doc_file):
                continue
            discovery["documentation_files"].append(str(doc_file.relative_to(project_root)))

    return discovery


def discover_components(project_root: Path) -> Dict[str, Any]:
    """
    Identify existing system components.

    Args:
        project_root: Root directory of the project

    Returns:
        Dictionary of discovered components
    """
    components = {
        "cli_commands": [],
        "modules": [],
        "classes": [],
        "functions": [],
    }

    # Look for CLI commands in cli.py
    cli_file = project_root / "agentforge_cli" / "cli.py"
    if cli_file.exists():
        components["cli_commands"] = _extract_cli_commands(cli_file)

    # Discover modules
    agentforge_dir = project_root / "agentforge_cli"
    if agentforge_dir.exists():
        for py_file in agentforge_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            components["modules"].append(py_file.stem)

    return components


def discover_dependencies(project_root: Path) -> Dict[str, Any]:
    """
    Map technical dependencies.

    Args:
        project_root: Root directory of the project

    Returns:
        Dictionary of dependencies
    """
    dependencies = {
        "python_version": None,
        "packages": [],
        "dev_packages": [],
    }

    # Parse pyproject.toml
    pyproject_file = project_root / "pyproject.toml"
    if pyproject_file.exists():
        content = pyproject_file.read_text()

        # Extract Python version requirement
        if 'requires-python' in content:
            for line in content.split('\n'):
                if 'requires-python' in line:
                    dependencies["python_version"] = line.split('=')[1].strip().strip('"')
                    break

        # Extract dependencies
        in_deps = False
        for line in content.split('\n'):
            if line.strip() == "dependencies = [":
                in_deps = True
                continue
            if in_deps:
                if ']' in line:
                    break
                if line.strip() and not line.strip().startswith('#'):
                    dep = line.strip().strip('",')
                    if dep:
                        dependencies["packages"].append(dep)

    return dependencies


def discover_missing(project_root: Path, requirements: List[str]) -> List[Dict[str, str]]:
    """
    Identify missing components vs requirements.

    Args:
        project_root: Root directory of the project
        requirements: List of required features/commands

    Returns:
        List of missing components with details
    """
    missing = []

    # Check for required commands
    cli_file = project_root / "agentforge_cli" / "cli.py"
    existing_commands = []

    if cli_file.exists():
        existing_commands = _extract_cli_commands(cli_file)

    for requirement in requirements:
        if requirement not in existing_commands:
            missing.append({
                "type": "command",
                "name": requirement,
                "status": "missing",
                "priority": "high" if requirement in ["/plan", "/resume", "/"] else "medium"
            })

    return missing


def generate_discovery_report(
    project_root: Path,
    output_file: Optional[Path] = None,
    requirements: Optional[List[str]] = None
) -> str:
    """
    Generate comprehensive discovery report in Markdown.

    Args:
        project_root: Root directory of the project
        output_file: Optional path to save report
        requirements: Optional list of required features

    Returns:
        Markdown report as string
    """
    codebase = discover_codebase(project_root)
    components = discover_components(project_root)
    dependencies = discover_dependencies(project_root)

    if requirements is None:
        requirements = ["/plan", "/resume", "/"]

    missing = discover_missing(project_root, requirements)

    # Get git info if available
    git_info = _get_git_info(project_root)

    report_lines = [
        "# AgentForge Discovery Report",
        "",
        f"**Generated:** {_get_timestamp()}",
        f"**Project Root:** {project_root}",
    ]

    if git_info:
        report_lines.extend([
            f"**Branch:** {git_info.get('branch', 'unknown')}",
            f"**Latest Commit:** {git_info.get('commit', 'unknown')}",
        ])

    report_lines.extend([
        "",
        "## Executive Summary",
        "",
        f"- **Total Files:** {codebase['total_files']}",
        f"- **Total Lines of Code:** {codebase['total_lines']:,}",
        f"- **Python Modules:** {len(codebase['python_files'])}",
        f"- **Test Files:** {len(codebase['test_files'])}",
        f"- **CLI Modules:** {len(codebase['cli_modules'])}",
        f"- **Configuration Files:** {len(codebase['config_files'])}",
        "",
        "## Codebase Structure",
        "",
        "### Python Files",
        "",
    ])

    for file_info in codebase['python_files'][:10]:  # Top 10
        report_lines.append(f"- `{file_info['path']}` ({file_info['lines']} lines)")

    if len(codebase['python_files']) > 10:
        report_lines.append(f"- ... and {len(codebase['python_files']) - 10} more files")

    report_lines.extend([
        "",
        "### CLI Modules",
        "",
    ])

    for file_info in codebase['cli_modules']:
        report_lines.append(f"- `{file_info['path']}` ({file_info['lines']} lines)")

    report_lines.extend([
        "",
        "### Test Files",
        "",
    ])

    for file_info in codebase['test_files'][:10]:
        report_lines.append(f"- `{file_info['path']}` ({file_info['lines']} lines)")

    if len(codebase['test_files']) > 10:
        report_lines.append(f"- ... and {len(codebase['test_files']) - 10} more test files")

    report_lines.extend([
        "",
        "## Discovered Components",
        "",
        "### CLI Commands",
        "",
    ])

    if components['cli_commands']:
        for cmd in components['cli_commands']:
            report_lines.append(f"- `{cmd}`")
    else:
        report_lines.append("- No CLI commands discovered")

    report_lines.extend([
        "",
        "### Modules",
        "",
    ])

    for module in components['modules']:
        report_lines.append(f"- `{module}`")

    report_lines.extend([
        "",
        "## Dependencies",
        "",
        f"**Python Version:** {dependencies['python_version'] or 'Not specified'}",
        "",
        "**Required Packages:**",
        "",
    ])

    for pkg in dependencies['packages']:
        report_lines.append(f"- `{pkg}`")

    report_lines.extend([
        "",
        "## Missing Components",
        "",
    ])

    if missing:
        for item in missing:
            report_lines.append(
                f"- **{item['name']}** ({item['type']}) - Priority: {item['priority']}"
            )
    else:
        report_lines.append("- All required components present")

    report_lines.extend([
        "",
        "## Recommendations",
        "",
    ])

    if missing:
        report_lines.append("### High Priority")
        report_lines.append("")
        for item in missing:
            if item['priority'] == 'high':
                report_lines.append(f"1. Implement `{item['name']}` {item['type']}")

    report = "\n".join(report_lines)

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(report, encoding='utf-8')

    return report


def _count_lines(file_path: Path) -> int:
    """Count non-empty lines in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def _extract_cli_commands(cli_file: Path) -> List[str]:
    """Extract CLI command names from cli.py."""
    commands = []
    try:
        content = cli_file.read_text(encoding='utf-8')
        for line in content.split('\n'):
            # Look for @cli.command or @<group>.command
            if '@' in line and '.command' in line:
                # Extract command name
                if 'name=' in line:
                    # Extract from name="..." or name='...'
                    parts = line.split('name=')[1]
                    quote = parts[0]
                    cmd_name = parts[1:].split(quote)[0]
                    commands.append(cmd_name)
                elif 'def ' in content[content.index(line):content.index(line) + 200]:
                    # Get function name
                    next_def = content[content.index(line):].split('def ')[1]
                    func_name = next_def.split('(')[0].strip()
                    commands.append(func_name)
    except Exception:
        pass

    return list(set(commands))  # Remove duplicates


def _get_git_info(project_root: Path) -> Optional[Dict[str, str]]:
    """Get git repository information."""
    try:
        # Get current branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5
        )
        branch = result.stdout.strip() if result.returncode == 0 else None

        # Get latest commit
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5
        )
        commit = result.stdout.strip() if result.returncode == 0 else None

        return {"branch": branch, "commit": commit}
    except Exception:
        return None


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    from datetime import datetime
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def load_existing_discovery(discovery_file: Path) -> Optional[Dict[str, Any]]:
    """
    Load existing discovery.json if it exists.

    Args:
        discovery_file: Path to discovery.json

    Returns:
        Discovery data or None if file doesn't exist
    """
    if not discovery_file.exists():
        return None

    try:
        with open(discovery_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def merge_discovery(
    existing: Optional[Dict[str, Any]],
    new: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge existing discovery data with new discovery.

    Args:
        existing: Existing discovery data
        new: New discovery data

    Returns:
        Merged discovery data
    """
    if not existing:
        return new

    # Start with new data
    merged = new.copy()

    # Add notes from existing if present
    if "notes" in existing:
        merged["notes"] = existing["notes"]

    # Add risks from existing if present
    if "risks" in existing:
        merged["risks"] = existing["risks"]

    return merged
