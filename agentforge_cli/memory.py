"""Persistent agent memory store with simple vector search."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from . import constants


_TOKEN_PATTERN = re.compile(r"\w+")
_EMBEDDING_DIM = 128


def _tokenize(text: str) -> Iterable[str]:
    for match in _TOKEN_PATTERN.finditer(text.lower()):
        yield match.group(0)


def _vectorize(text: str) -> List[float]:
    vector = [0.0] * _EMBEDDING_DIM
    for token in _tokenize(text):
        idx = hash(token) % _EMBEDDING_DIM
        vector[idx] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(vec_a, vec_b))


@dataclass
class MemoryRecord:
    id: int
    agent_id: str
    content: str
    metadata: Dict[str, object]
    created_at: datetime
    similarity: float


class MemoryStore:
    """Lightweight vector memory backed by SQLite."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._bootstrap()

    def __enter__(self) -> MemoryStore:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def _bootstrap(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                embedding TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_agent ON memories(agent_id)"
        )
        self.conn.commit()

    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, object]] = None) -> int:
        embedding = _vectorize(content)
        now = datetime.utcnow().isoformat()
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO memories(agent_id, content, metadata, embedding, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    content,
                    json.dumps(metadata or {}),
                    json.dumps(embedding),
                    now,
                    now,
                ),
            )
            return cur.lastrowid

    def search(self, query: str, *, limit: int = 5, agent_id: Optional[str] = None) -> List[MemoryRecord]:
        query_vec = _vectorize(query)
        if not query_vec:
            return []
        params: List[object] = []
        sql = "SELECT id, agent_id, content, metadata, embedding, created_at FROM memories"
        if agent_id:
            sql += " WHERE agent_id = ?"
            params.append(agent_id)
        rows = self.conn.execute(sql, params).fetchall()
        scored: List[MemoryRecord] = []
        for row in rows:
            embedding = json.loads(row["embedding"])
            similarity = _cosine_similarity(query_vec, embedding)
            scored.append(
                MemoryRecord(
                    id=row["id"],
                    agent_id=row["agent_id"],
                    content=row["content"],
                    metadata=json.loads(row["metadata"] or "{}"),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    similarity=similarity,
                )
            )
        scored.sort(key=lambda record: record.similarity, reverse=True)
        return scored[:limit]


def default_memory_store() -> MemoryStore:
    constants.refresh_paths()
    return MemoryStore(constants.MEMORY_DB)


__all__ = ["MemoryStore", "MemoryRecord", "default_memory_store"]
