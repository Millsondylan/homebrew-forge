"""
Session management for AgentForge.

Handles session state persistence, restoration, and management for
plan/resume workflows.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TodoItem:
    """Represents a single TODO item in a session."""
    id: str
    label: str  # core, support, verify
    priority: int
    title: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    verification_logical: Optional[str] = None
    verification_empirical: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, failed
    estimated_effort: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TodoItem:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class VerificationState:
    """Tracks verification results."""
    logical_status: Optional[str] = None  # passed, failed, pending
    logical_notes: Optional[str] = None
    logical_timestamp: Optional[str] = None
    empirical_status: Optional[str] = None  # passed, failed, pending
    empirical_notes: Optional[str] = None
    empirical_timestamp: Optional[str] = None
    integration_status: Optional[str] = None
    integration_notes: Optional[str] = None
    integration_timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VerificationState:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class Session:
    """Represents a complete session state."""

    # Identity
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Command context
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)

    # Execution state
    current_phase: str = "discovery"  # discovery, planning, execution, verification, documentation
    phase_history: List[Dict[str, str]] = field(default_factory=list)

    # TODOs
    todos: List[TodoItem] = field(default_factory=list)
    current_todo_id: Optional[str] = None

    # Verification
    verification: VerificationState = field(default_factory=VerificationState)

    # Context and outputs
    context: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert nested dataclasses
        data["verification"] = self.verification.to_dict()
        data["todos"] = [todo.to_dict() for todo in self.todos]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Session:
        """Create session from dictionary."""
        # Convert nested structures
        if "verification" in data:
            data["verification"] = VerificationState.from_dict(data["verification"])
        if "todos" in data:
            data["todos"] = [TodoItem.from_dict(todo) for todo in data["todos"]]
        return cls(**data)

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow().isoformat()

    def add_todo(self, todo: TodoItem) -> None:
        """Add a TODO item to the session."""
        self.todos.append(todo)
        self.update_timestamp()

    def update_todo_status(self, todo_id: str, status: str) -> None:
        """Update the status of a TODO."""
        for todo in self.todos:
            if todo.id == todo_id:
                todo.status = status
                if status == "in_progress":
                    todo.started_at = datetime.utcnow().isoformat()
                elif status == "completed":
                    todo.completed_at = datetime.utcnow().isoformat()
                self.update_timestamp()
                break

    def set_phase(self, phase: str) -> None:
        """Set the current execution phase."""
        self.phase_history.append({
            "phase": self.current_phase,
            "ended_at": datetime.utcnow().isoformat()
        })
        self.current_phase = phase
        self.update_timestamp()

    def get_pending_todos(self) -> List[TodoItem]:
        """Get all pending TODOs."""
        return [todo for todo in self.todos if todo.status == "pending"]

    def get_completed_todos(self) -> List[TodoItem]:
        """Get all completed TODOs."""
        return [todo for todo in self.todos if todo.status == "completed"]

    def get_progress(self) -> Dict[str, Any]:
        """Get progress statistics."""
        total = len(self.todos)
        if total == 0:
            return {"total": 0, "completed": 0, "pending": 0, "in_progress": 0, "failed": 0, "percent": 0}

        completed = len([t for t in self.todos if t.status == "completed"])
        pending = len([t for t in self.todos if t.status == "pending"])
        in_progress = len([t for t in self.todos if t.status == "in_progress"])
        failed = len([t for t in self.todos if t.status == "failed"])

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "in_progress": in_progress,
            "failed": failed,
            "percent": round((completed / total) * 100, 1)
        }


def save_session(session: Session, sessions_dir: Path) -> Path:
    """
    Save session to JSON file.

    Args:
        session: Session object to save
        sessions_dir: Directory to save sessions in

    Returns:
        Path to saved session file
    """
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / f"session_{session.session_id}.json"

    session.update_timestamp()

    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

    return session_file


def load_session(session_id: str, sessions_dir: Path) -> Session:
    """
    Load session from JSON file.

    Args:
        session_id: Session ID to load
        sessions_dir: Directory containing sessions

    Returns:
        Loaded Session object

    Raises:
        FileNotFoundError: If session file doesn't exist
        ValueError: If session data is invalid
    """
    session_file = sessions_dir / f"session_{session_id}.json"

    if not session_file.exists():
        raise FileNotFoundError(f"Session {session_id} not found at {session_file}")

    with open(session_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    try:
        session = Session.from_dict(data)
    except (TypeError, KeyError) as exc:
        raise ValueError(f"Invalid session data in {session_file}: {exc}") from exc

    return session


def validate_session(session: Session) -> bool:
    """
    Validate session structure and data.

    Args:
        session: Session to validate

    Returns:
        True if valid, raises ValueError if invalid
    """
    if not session.session_id:
        raise ValueError("Session must have session_id")

    if not session.created_at:
        raise ValueError("Session must have created_at timestamp")

    if session.current_phase not in ["discovery", "planning", "execution", "verification", "documentation"]:
        raise ValueError(f"Invalid phase: {session.current_phase}")

    # Validate TODOs
    for todo in session.todos:
        if not todo.id:
            raise ValueError("TODO must have id")
        if todo.status not in ["pending", "in_progress", "completed", "failed"]:
            raise ValueError(f"Invalid TODO status: {todo.status}")
        if todo.label not in ["core", "support", "verify"]:
            raise ValueError(f"Invalid TODO label: {todo.label}")

    return True


def list_sessions(sessions_dir: Path) -> List[Dict[str, Any]]:
    """
    List all sessions in directory.

    Args:
        sessions_dir: Directory containing sessions

    Returns:
        List of session metadata dictionaries
    """
    if not sessions_dir.exists():
        return []

    sessions = []

    for session_file in sorted(sessions_dir.glob("session_*.json"), reverse=True):
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Extract key metadata
            metadata = {
                "session_id": data.get("session_id"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "command": data.get("command"),
                "current_phase": data.get("current_phase"),
                "todo_count": len(data.get("todos", [])),
                "completed_todos": len([t for t in data.get("todos", []) if t.get("status") == "completed"]),
                "file": session_file.name
            }
            sessions.append(metadata)
        except (json.JSONDecodeError, KeyError):
            # Skip invalid session files
            continue

    return sessions


def find_session(session_id_or_prefix: str, sessions_dir: Path) -> Optional[str]:
    """
    Find session by ID or prefix.

    Args:
        session_id_or_prefix: Full session ID or prefix
        sessions_dir: Directory containing sessions

    Returns:
        Full session ID if found, None otherwise
    """
    sessions = list_sessions(sessions_dir)

    # Try exact match first
    for session in sessions:
        if session["session_id"] == session_id_or_prefix:
            return session["session_id"]

    # Try prefix match
    matches = [s for s in sessions if s["session_id"].startswith(session_id_or_prefix)]

    if len(matches) == 1:
        return matches[0]["session_id"]
    elif len(matches) > 1:
        raise ValueError(f"Ambiguous session prefix '{session_id_or_prefix}' matches {len(matches)} sessions")

    return None


def get_latest_session(sessions_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Get the most recently updated session.

    Args:
        sessions_dir: Directory containing sessions

    Returns:
        Session metadata dict or None if no sessions exist
    """
    sessions = list_sessions(sessions_dir)
    return sessions[0] if sessions else None


def delete_session(session_id: str, sessions_dir: Path) -> bool:
    """
    Delete a session file.

    Args:
        session_id: Session ID to delete
        sessions_dir: Directory containing sessions

    Returns:
        True if deleted, False if not found
    """
    session_file = sessions_dir / f"session_{session_id}.json"

    if session_file.exists():
        session_file.unlink()
        return True

    return False
