"""
Planning workflow automation for AgentForge.

Generates execution plans, TODOs, and manages dependencies.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml


class TodoGenerator:
    """Generates TODO items from plans."""

    def __init__(self):
        self.todo_counter = 0

    def create_todo(
        self,
        title: str,
        description: str,
        label: str = "core",
        priority: int = 1,
        dependencies: Optional[List[str]] = None,
        files_created: Optional[List[str]] = None,
        files_modified: Optional[List[str]] = None,
        verification_logical: str = "",
        verification_empirical: str = "",
        estimated_effort: str = "1 hour",
    ) -> Dict[str, Any]:
        """
        Create a TODO item with full specification.

        Args:
            title: Short title of the TODO
            description: Detailed description
            label: One of 'core', 'support', 'verify'
            priority: Priority level (1 = highest)
            dependencies: List of TODO IDs this depends on
            files_created: List of files to be created
            files_modified: List of files to be modified
            verification_logical: Logical verification criteria
            verification_empirical: Empirical verification criteria
            estimated_effort: Time estimate

        Returns:
            TODO dictionary
        """
        self.todo_counter += 1
        todo_id = f"TODO-{self.todo_counter:03d}"

        return {
            "id": todo_id,
            "label": label,
            "priority": priority,
            "title": title,
            "description": description.strip(),
            "dependencies": dependencies or [],
            "files_created": files_created or [],
            "files_modified": files_modified or [],
            "verification": {
                "logical": verification_logical,
                "empirical": verification_empirical,
            },
            "status": "pending",
            "estimated_effort": estimated_effort,
        }


def generate_todos_for_feature(
    feature_name: str,
    components: List[str],
    base_priority: int = 1
) -> List[Dict[str, Any]]:
    """
    Generate TODOs for implementing a feature.

    Args:
        feature_name: Name of the feature (e.g., "/plan command")
        components: List of components to implement
        base_priority: Base priority level

    Returns:
        List of TODO dictionaries
    """
    generator = TodoGenerator()
    todos = []

    # Create TODOs for each component
    for idx, component in enumerate(components):
        todo = generator.create_todo(
            title=f"Implement {component} for {feature_name}",
            description=f"Create {component} as part of {feature_name} implementation.",
            label="core",
            priority=base_priority + idx,
            estimated_effort="1 hour",
        )
        todos.append(todo)

    return todos


def order_by_dependencies(todos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort TODOs by dependency order using topological sort.

    Args:
        todos: List of TODO dictionaries

    Returns:
        Sorted list of TODOs

    Raises:
        ValueError: If circular dependencies detected
    """
    # Build dependency graph
    graph = defaultdict(list)
    in_degree = defaultdict(int)
    todo_map = {todo["id"]: todo for todo in todos}

    # Initialize in_degree for all nodes
    for todo in todos:
        if todo["id"] not in in_degree:
            in_degree[todo["id"]] = 0

    # Build graph
    for todo in todos:
        for dep in todo.get("dependencies", []):
            if dep in todo_map:
                graph[dep].append(todo["id"])
                in_degree[todo["id"]] += 1

    # Topological sort using Kahn's algorithm
    queue = [todo_id for todo_id in todo_map.keys() if in_degree[todo_id] == 0]
    sorted_ids = []

    while queue:
        # Sort queue by priority for stable ordering
        queue.sort(key=lambda x: todo_map[x].get("priority", 999))
        current = queue.pop(0)
        sorted_ids.append(current)

        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Check for cycles
    if len(sorted_ids) != len(todos):
        raise ValueError("Circular dependencies detected in TODO list")

    # Return sorted TODOs
    return [todo_map[todo_id] for todo_id in sorted_ids]


def detect_cycles(todos: List[Dict[str, Any]]) -> Optional[List[str]]:
    """
    Detect cycles in TODO dependencies.

    Args:
        todos: List of TODO dictionaries

    Returns:
        List of TODO IDs in cycle, or None if no cycle
    """
    todo_map = {todo["id"]: todo for todo in todos}
    visited = set()
    rec_stack = set()

    def visit(todo_id: str, path: List[str]) -> Optional[List[str]]:
        if todo_id in rec_stack:
            # Found cycle
            cycle_start = path.index(todo_id)
            return path[cycle_start:]

        if todo_id in visited:
            return None

        visited.add(todo_id)
        rec_stack.add(todo_id)

        todo = todo_map.get(todo_id)
        if todo:
            for dep in todo.get("dependencies", []):
                if dep in todo_map:
                    result = visit(dep, path + [todo_id])
                    if result:
                        return result

        rec_stack.remove(todo_id)
        return None

    for todo in todos:
        if todo["id"] not in visited:
            cycle = visit(todo["id"], [])
            if cycle:
                return cycle

    return None


def assign_levels(todos: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Assign dependency levels to TODOs.

    Args:
        todos: List of TODO dictionaries

    Returns:
        Dictionary mapping TODO ID to level
    """
    levels = {}
    todo_map = {todo["id"]: todo for todo in todos}

    def get_level(todo_id: str) -> int:
        if todo_id in levels:
            return levels[todo_id]

        todo = todo_map[todo_id]
        deps = todo.get("dependencies", [])

        if not deps:
            levels[todo_id] = 0
            return 0

        max_dep_level = -1
        for dep in deps:
            if dep in todo_map:
                dep_level = get_level(dep)
                max_dep_level = max(max_dep_level, dep_level)

        level = max_dep_level + 1
        levels[todo_id] = level
        return level

    for todo in todos:
        get_level(todo["id"])

    return levels


def format_plan_markdown(
    project_name: str,
    target_version: str,
    phases: List[Dict[str, Any]],
    todos: List[Dict[str, Any]],
    output_file: Optional[Path] = None,
) -> str:
    """
    Generate plan.md in Markdown format.

    Args:
        project_name: Name of the project
        target_version: Target version
        phases: List of phase dictionaries
        todos: List of TODO dictionaries
        output_file: Optional path to save plan

    Returns:
        Markdown content as string
    """
    lines = [
        f"# {project_name} Implementation Plan",
        "",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d')}",
        f"**Target Version:** {target_version}",
        "",
        "## Executive Summary",
        "",
        f"This plan outlines the implementation of {len(todos)} TODOs across {len(phases)} phases.",
        "",
        "## Implementation Roadmap",
        "",
    ]

    # Add phases
    for phase in phases:
        lines.extend([
            f"### {phase['name']}",
            "",
            f"**TODOs:** {len(phase['todos'])}",
            "",
            phase.get("description", ""),
            "",
        ])

    lines.extend([
        "## Dependency Order",
        "",
    ])

    # Group TODOs by level
    levels = assign_levels(todos)
    todos_by_level = defaultdict(list)
    for todo in todos:
        level = levels[todo["id"]]
        todos_by_level[level].append(todo)

    for level in sorted(todos_by_level.keys()):
        lines.append(f"### Level {level}")
        lines.append("")
        for todo in todos_by_level[level]:
            lines.append(f"- **{todo['id']}:** {todo['title']}")
        lines.append("")

    lines.extend([
        "## Success Criteria",
        "",
        "- All TODOs completed with double verification",
        "- Logical and empirical tests passing",
        "- Documentation updated",
        "- No regressions in existing functionality",
        "",
    ])

    content = "\n".join(lines)

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content, encoding='utf-8')

    return content


def format_todos_yaml(
    todos: List[Dict[str, Any]],
    project_name: str,
    target_version: str,
    phases: Optional[List[Dict[str, Any]]] = None,
    output_file: Optional[Path] = None,
) -> str:
    """
    Generate TODOs.yaml in YAML format.

    Args:
        todos: List of TODO dictionaries
        project_name: Name of the project
        target_version: Target version
        phases: Optional list of phases
        output_file: Optional path to save YAML

    Returns:
        YAML content as string
    """
    # Count by label
    core_count = len([t for t in todos if t["label"] == "core"])
    support_count = len([t for t in todos if t["label"] == "support"])
    verify_count = len([t for t in todos if t["label"] == "verify"])

    # Calculate total effort
    total_hours = 0.0
    for todo in todos:
        effort = todo.get("estimated_effort", "1 hour")
        try:
            # Parse effort string like "1 hour", "30 minutes", "1.5 hours"
            if "hour" in effort:
                hours = float(effort.split()[0])
                total_hours += hours
            elif "minute" in effort:
                minutes = float(effort.split()[0])
                total_hours += minutes / 60
        except (ValueError, IndexError):
            total_hours += 1.0  # Default to 1 hour

    data = {
        "version": "1.0",
        "generated": datetime.utcnow().strftime("%Y-%m-%d"),
        "project": f"{project_name} {target_version}",
        "todos": todos,
        "summary": {
            "total_todos": len(todos),
            "core_todos": core_count,
            "support_todos": support_count,
            "verify_todos": verify_count,
            "estimated_total_effort": f"{total_hours:.1f} hours",
        }
    }

    if phases:
        phase_summary = []
        for phase in phases:
            phase_summary.append({
                "name": phase["name"],
                "todos": phase.get("todos", []),
                "status": "pending",
            })
        data["summary"]["phases"] = phase_summary

    content = yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content, encoding='utf-8')

    return content


def generate_plan(
    project_root: Path,
    feature_specs: List[Dict[str, Any]],
    output_dir: Optional[Path] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generate complete execution plan with TODOs.

    Args:
        project_root: Root directory of the project
        feature_specs: List of feature specifications
        output_dir: Optional directory to save outputs

    Returns:
        Tuple of (plan_markdown, todos_list)
    """
    all_todos = []
    phases = []

    # Generate TODOs for each feature
    for spec in feature_specs:
        feature_name = spec.get("name", "Feature")
        components = spec.get("components", [])
        phase_name = spec.get("phase", "Implementation")

        feature_todos = generate_todos_for_feature(
            feature_name,
            components,
            base_priority=len(all_todos) + 1
        )

        all_todos.extend(feature_todos)

        phases.append({
            "name": phase_name,
            "description": spec.get("description", ""),
            "todos": [t["id"] for t in feature_todos],
        })

    # Order TODOs by dependencies
    try:
        ordered_todos = order_by_dependencies(all_todos)
    except ValueError as e:
        # If cycles detected, return unordered
        print(f"Warning: {e}")
        ordered_todos = all_todos

    # Generate plan markdown
    plan_md = format_plan_markdown(
        project_name="AgentForge",
        target_version="0.4.0",
        phases=phases,
        todos=ordered_todos,
        output_file=output_dir / "plan.md" if output_dir else None,
    )

    return plan_md, ordered_todos


def validate_todo_count(todos: List[Dict[str, Any]], minimum: int = 20) -> bool:
    """
    Validate that minimum number of TODOs exist.

    Args:
        todos: List of TODO dictionaries
        minimum: Minimum required TODOs

    Returns:
        True if valid, False otherwise
    """
    return len(todos) >= minimum


def label_todos(todos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Auto-assign labels to TODOs based on keywords.

    Args:
        todos: List of TODO dictionaries

    Returns:
        TODOs with updated labels
    """
    for todo in todos:
        title_lower = todo["title"].lower()
        desc_lower = todo["description"].lower()

        # Check for verification keywords
        if any(word in title_lower or word in desc_lower for word in ["test", "verify", "validation"]):
            todo["label"] = "verify"
        # Check for support keywords
        elif any(word in title_lower or word in desc_lower for word in ["document", "logging", "monitoring", "config"]):
            todo["label"] = "support"
        # Default to core
        elif "label" not in todo or not todo["label"]:
            todo["label"] = "core"

    return todos


def calculate_priorities(todos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculate priorities based on dependencies and labels.

    Args:
        todos: List of TODO dictionaries

    Returns:
        TODOs with updated priorities
    """
    levels = assign_levels(todos)

    for todo in todos:
        level = levels[todo["id"]]

        # Base priority on level
        priority = level * 10

        # Adjust for label
        if todo["label"] == "core":
            priority += 0
        elif todo["label"] == "support":
            priority += 5
        elif todo["label"] == "verify":
            priority += 8

        todo["priority"] = priority

    return todos
