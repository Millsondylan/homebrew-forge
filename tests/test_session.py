"""Tests for session management module."""

from pathlib import Path
import tempfile
import json

from agentforge_cli.session import (
    Session,
    TodoItem,
    VerificationState,
    save_session,
    load_session,
    validate_session,
    list_sessions,
    find_session,
    get_latest_session,
    delete_session,
)


def test_session_creation():
    """Test basic session creation."""
    session = Session()

    assert session.session_id is not None
    assert session.created_at is not None
    assert session.current_phase == "discovery"
    assert len(session.todos) == 0


def test_session_with_command():
    """Test session with command context."""
    session = Session(
        command="plan",
        args=["arg1", "arg2"],
        kwargs={"key": "value"}
    )

    assert session.command == "plan"
    assert session.args == ["arg1", "arg2"]
    assert session.kwargs == {"key": "value"}


def test_todo_item_creation():
    """Test TODO item creation."""
    todo = TodoItem(
        id="TODO-001",
        label="core",
        priority=1,
        title="Test TODO",
        description="Test description",
    )

    assert todo.id == "TODO-001"
    assert todo.status == "pending"
    assert todo.label == "core"


def test_session_add_todo():
    """Test adding TODO to session."""
    session = Session()
    todo = TodoItem(
        id="TODO-001",
        label="core",
        priority=1,
        title="Test",
        description="Test",
    )

    session.add_todo(todo)

    assert len(session.todos) == 1
    assert session.todos[0].id == "TODO-001"


def test_session_update_todo_status():
    """Test updating TODO status."""
    session = Session()
    todo = TodoItem(id="TODO-001", label="core", priority=1, title="Test", description="Test")
    session.add_todo(todo)

    session.update_todo_status("TODO-001", "in_progress")
    assert session.todos[0].status == "in_progress"
    assert session.todos[0].started_at is not None

    session.update_todo_status("TODO-001", "completed")
    assert session.todos[0].status == "completed"
    assert session.todos[0].completed_at is not None


def test_session_set_phase():
    """Test setting execution phase."""
    session = Session()

    session.set_phase("planning")
    assert session.current_phase == "planning"
    assert len(session.phase_history) == 1
    assert session.phase_history[0]["phase"] == "discovery"


def test_session_get_progress():
    """Test progress calculation."""
    session = Session()

    # Add TODOs with different statuses
    session.add_todo(TodoItem(id="TODO-001", label="core", priority=1, title="1", description="1"))
    session.add_todo(TodoItem(id="TODO-002", label="core", priority=1, title="2", description="2"))
    session.add_todo(TodoItem(id="TODO-003", label="core", priority=1, title="3", description="3"))

    session.update_todo_status("TODO-001", "completed")
    session.update_todo_status("TODO-002", "in_progress")

    progress = session.get_progress()

    assert progress["total"] == 3
    assert progress["completed"] == 1
    assert progress["in_progress"] == 1
    assert progress["pending"] == 1
    assert progress["percent"] == 33.3


def test_session_serialization():
    """Test session to_dict and from_dict."""
    session = Session(command="test")
    todo = TodoItem(id="TODO-001", label="core", priority=1, title="Test", description="Test")
    session.add_todo(todo)

    # Serialize
    data = session.to_dict()

    assert isinstance(data, dict)
    assert data["command"] == "test"
    assert len(data["todos"]) == 1

    # Deserialize
    restored = Session.from_dict(data)

    assert restored.session_id == session.session_id
    assert restored.command == session.command
    assert len(restored.todos) == 1
    assert restored.todos[0].id == "TODO-001"


def test_save_and_load_session():
    """Test saving and loading session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sessions_dir = Path(tmpdir)

        # Create and save session
        session = Session(command="test")
        session.add_todo(TodoItem(id="TODO-001", label="core", priority=1, title="Test", description="Test"))

        session_file = save_session(session, sessions_dir)

        assert session_file.exists()

        # Load session
        loaded = load_session(session.session_id, sessions_dir)

        assert loaded.session_id == session.session_id
        assert loaded.command == session.command
        assert len(loaded.todos) == 1


def test_validate_session():
    """Test session validation."""
    session = Session()

    # Valid session
    assert validate_session(session) is True

    # Invalid phase
    session.current_phase = "invalid"
    try:
        validate_session(session)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_list_sessions():
    """Test listing sessions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sessions_dir = Path(tmpdir)

        # Create multiple sessions
        session1 = Session(command="plan")
        session2 = Session(command="test")

        save_session(session1, sessions_dir)
        save_session(session2, sessions_dir)

        # List sessions
        sessions = list_sessions(sessions_dir)

        assert len(sessions) == 2
        assert sessions[0]["command"] in ["plan", "test"]


def test_find_session():
    """Test finding session by ID or prefix."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sessions_dir = Path(tmpdir)

        session = Session()
        save_session(session, sessions_dir)

        # Find by exact ID
        found = find_session(session.session_id, sessions_dir)
        assert found == session.session_id

        # Find by prefix
        prefix = session.session_id[:8]
        found = find_session(prefix, sessions_dir)
        assert found == session.session_id

        # Not found
        found = find_session("nonexistent", sessions_dir)
        assert found is None


def test_get_latest_session():
    """Test getting latest session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sessions_dir = Path(tmpdir)

        # Create sessions
        session1 = Session()
        save_session(session1, sessions_dir)

        import time
        time.sleep(0.1)

        session2 = Session()
        save_session(session2, sessions_dir)

        # Get latest
        latest = get_latest_session(sessions_dir)

        assert latest is not None
        # Latest should be session2 (most recent)
        assert latest["session_id"] in [session1.session_id, session2.session_id]


def test_delete_session():
    """Test deleting session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sessions_dir = Path(tmpdir)

        session = Session()
        save_session(session, sessions_dir)

        # Delete session
        result = delete_session(session.session_id, sessions_dir)
        assert result is True

        # Verify deleted
        sessions = list_sessions(sessions_dir)
        assert len(sessions) == 0

        # Delete nonexistent
        result = delete_session("nonexistent", sessions_dir)
        assert result is False
