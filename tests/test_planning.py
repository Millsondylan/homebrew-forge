"""Tests for planning module."""

from pathlib import Path
import tempfile
import yaml

from agentforge_cli.planning import (
    TodoGenerator,
    generate_todos_for_feature,
    order_by_dependencies,
    detect_cycles,
    assign_levels,
    format_plan_markdown,
    format_todos_yaml,
    generate_plan,
    validate_todo_count,
    label_todos,
    calculate_priorities,
)


def test_todo_generator():
    """Test TODO generator creates proper structure."""
    generator = TodoGenerator()

    todo = generator.create_todo(
        title="Test TODO",
        description="Test description",
        label="core",
        priority=1,
    )

    assert todo["id"] == "TODO-001"
    assert todo["title"] == "Test TODO"
    assert todo["description"] == "Test description"
    assert todo["label"] == "core"
    assert todo["priority"] == 1
    assert todo["status"] == "pending"
    assert "verification" in todo


def test_generate_todos_for_feature():
    """Test feature TODO generation."""
    todos = generate_todos_for_feature(
        feature_name="Test Feature",
        components=["Component A", "Component B", "Component C"],
        base_priority=1
    )

    assert len(todos) == 3
    assert todos[0]["id"] == "TODO-001"
    assert todos[1]["id"] == "TODO-002"
    assert todos[2]["id"] == "TODO-003"
    assert "Component A" in todos[0]["title"]


def test_order_by_dependencies():
    """Test dependency ordering."""
    todos = [
        {
            "id": "TODO-001",
            "title": "First",
            "dependencies": [],
            "label": "core",
            "priority": 1,
        },
        {
            "id": "TODO-002",
            "title": "Second",
            "dependencies": ["TODO-001"],
            "label": "core",
            "priority": 2,
        },
        {
            "id": "TODO-003",
            "title": "Third",
            "dependencies": ["TODO-002"],
            "label": "core",
            "priority": 3,
        },
    ]

    ordered = order_by_dependencies(todos)

    assert ordered[0]["id"] == "TODO-001"
    assert ordered[1]["id"] == "TODO-002"
    assert ordered[2]["id"] == "TODO-003"


def test_detect_cycles_no_cycle():
    """Test cycle detection with no cycles."""
    todos = [
        {"id": "TODO-001", "dependencies": []},
        {"id": "TODO-002", "dependencies": ["TODO-001"]},
        {"id": "TODO-003", "dependencies": ["TODO-002"]},
    ]

    cycle = detect_cycles(todos)
    assert cycle is None


def test_detect_cycles_with_cycle():
    """Test cycle detection with actual cycle."""
    todos = [
        {"id": "TODO-001", "dependencies": ["TODO-003"]},
        {"id": "TODO-002", "dependencies": ["TODO-001"]},
        {"id": "TODO-003", "dependencies": ["TODO-002"]},
    ]

    cycle = detect_cycles(todos)
    assert cycle is not None
    assert len(cycle) > 0


def test_assign_levels():
    """Test level assignment."""
    todos = [
        {"id": "TODO-001", "dependencies": []},
        {"id": "TODO-002", "dependencies": ["TODO-001"]},
        {"id": "TODO-003", "dependencies": ["TODO-001", "TODO-002"]},
    ]

    levels = assign_levels(todos)

    assert levels["TODO-001"] == 0
    assert levels["TODO-002"] == 1
    assert levels["TODO-003"] == 2


def test_format_plan_markdown():
    """Test plan markdown generation."""
    todos = [
        {
            "id": "TODO-001",
            "title": "First TODO",
            "dependencies": [],
            "label": "core",
            "priority": 1,
        },
    ]

    phases = [
        {
            "name": "Phase 1",
            "description": "First phase",
            "todos": ["TODO-001"],
        }
    ]

    markdown = format_plan_markdown(
        project_name="Test Project",
        target_version="1.0.0",
        phases=phases,
        todos=todos,
    )

    assert "# Test Project Implementation Plan" in markdown
    assert "Target Version:** 1.0.0" in markdown
    assert "Phase 1" in markdown


def test_format_todos_yaml():
    """Test YAML formatting."""
    todos = [
        {
            "id": "TODO-001",
            "title": "Test TODO",
            "description": "Description",
            "label": "core",
            "priority": 1,
            "dependencies": [],
            "estimated_effort": "1 hour",
            "status": "pending",
            "files_created": [],
            "files_modified": [],
            "verification": {
                "logical": "Test logic",
                "empirical": "Test empirical",
            },
        },
    ]

    yaml_content = format_todos_yaml(
        todos,
        project_name="Test",
        target_version="1.0",
    )

    # Parse to verify valid YAML
    data = yaml.safe_load(yaml_content)

    assert data["project"] == "Test 1.0"
    assert data["summary"]["total_todos"] == 1
    assert len(data["todos"]) == 1


def test_generate_plan():
    """Test complete plan generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        feature_specs = [
            {
                "name": "Feature A",
                "phase": "Phase 1",
                "description": "First feature",
                "components": ["Comp 1", "Comp 2"],
            }
        ]

        plan_md, todos = generate_plan(
            project_root,
            feature_specs,
        )

        assert "Implementation Plan" in plan_md
        assert len(todos) == 2


def test_validate_todo_count():
    """Test TODO count validation."""
    todos = [{"id": f"TODO-{i:03d}"} for i in range(1, 21)]

    assert validate_todo_count(todos, minimum=20) is True
    assert validate_todo_count(todos, minimum=21) is False


def test_label_todos():
    """Test auto-labeling."""
    todos = [
        {"id": "TODO-001", "title": "Write unit tests", "description": "Testing"},
        {"id": "TODO-002", "title": "Add documentation", "description": "Docs"},
        {"id": "TODO-003", "title": "Implement feature", "description": "Core"},
    ]

    labeled = label_todos(todos)

    assert labeled[0]["label"] == "verify"  # tests
    assert labeled[1]["label"] == "support"  # documentation
    assert labeled[2]["label"] == "core"  # feature


def test_calculate_priorities():
    """Test priority calculation."""
    todos = [
        {"id": "TODO-001", "dependencies": [], "label": "core"},
        {"id": "TODO-002", "dependencies": ["TODO-001"], "label": "support"},
        {"id": "TODO-003", "dependencies": ["TODO-002"], "label": "verify"},
    ]

    prioritized = calculate_priorities(todos)

    # Level 0 core should have lowest priority value
    assert prioritized[0]["priority"] == 0
    # Level 1 support should have higher priority
    assert prioritized[1]["priority"] > prioritized[0]["priority"]
    # Level 2 verify should have highest priority
    assert prioritized[2]["priority"] > prioritized[1]["priority"]


def test_plan_generation_with_output():
    """Test plan generation with file output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        output_dir = Path(tmpdir) / "output"

        feature_specs = [
            {
                "name": "Test Feature",
                "phase": "Test Phase",
                "description": "Test",
                "components": ["A", "B", "C"],
            }
        ]

        plan_md, todos = generate_plan(
            project_root,
            feature_specs,
            output_dir=output_dir
        )

        # Check files were created
        assert (output_dir / "plan.md").exists()

        # Verify content
        plan_content = (output_dir / "plan.md").read_text()
        assert "Implementation Plan" in plan_content
