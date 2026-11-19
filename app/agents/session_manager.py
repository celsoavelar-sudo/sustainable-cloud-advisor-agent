import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any
from app.observability.telemetry import log_structured_event, redact_pii


class AdvisorSessionStore:
    """Manages persistent session state, history compaction, and async memory consolidation."""

    def __init__(
        self,
        db_path: str = ".advisor_sessions.sqlite3",
        max_history_turns: int = 10,
        max_summary_chars: int = 1200,
    ) -> None:
        self.db_path = db_path
        self.max_history_turns = max_history_turns
        self.max_summary_chars = max_summary_chars
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    history_json TEXT NOT NULL,
                    compacted_summary TEXT NOT NULL,
                    memory_notes_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _save_session(self, session: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, project_id, history_json, compacted_summary, memory_notes_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    project_id = excluded.project_id,
                    history_json = excluded.history_json,
                    compacted_summary = excluded.compacted_summary,
                    memory_notes_json = excluded.memory_notes_json
                """,
                (
                    session["session_id"],
                    session["project_id"],
                    json.dumps(session["history"]),
                    session["compacted_summary"],
                    json.dumps(session["memory_notes"]),
                ),
            )
            conn.commit()

    def get_or_create_session(self, session_id: str, project_id: str = "ctsal200") -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT session_id, project_id, history_json, compacted_summary, memory_notes_json
                FROM sessions WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is not None:
            return {
                "session_id": row[0],
                "project_id": row[1],
                "history": json.loads(row[2]),
                "compacted_summary": row[3],
                "memory_notes": json.loads(row[4]),
            }

        session = {
            "session_id": session_id,
            "project_id": project_id,
            "history": [],
            "compacted_summary": "",
            "memory_notes": [],
        }
        self._save_session(session)
        return session

    def compact_history(self, session_id: str) -> str:
        """Compacts older turns when history exceeds max_history_turns to prevent context bloat."""
        session = self.get_or_create_session(session_id)
        history: list[dict[str, str]] = session["history"]
        if len(history) <= self.max_history_turns:
            return session["compacted_summary"]

        overflow = history[: len(history) - self.max_history_turns]
        session["history"] = history[-self.max_history_turns :]

        condensed_lines = [
            f"{turn.get('role', 'user')}: {redact_pii(turn.get('content', ''))[:140]}"
            for turn in overflow
        ]
        merged = (session["compacted_summary"] + "\n" + "\n".join(condensed_lines)).strip()
        session["compacted_summary"] = merged[-self.max_summary_chars :]
        self._save_session(session)

        log_structured_event(
            event_type="history_compaction",
            intent=f"Compact {len(overflow)} older turns for session {session_id}",
            outcome=f"Retained {len(session['history'])} recent turns and updated summary",
            metadata={"session_id": session_id, "compacted_turns": len(overflow)},
        )
        return session["compacted_summary"]

    async def record_turn_and_consolidate_async(
        self,
        session_id: str,
        role: str,
        content: str,
        project_id: str = "ctsal200",
    ) -> dict[str, Any]:
        """Appends a turn and consolidates memory asynchronously without blocking the caller."""
        session = self.get_or_create_session(session_id, project_id=project_id)
        clean_content = redact_pii(content)
        session["history"].append({"role": role, "content": clean_content})
        self.compact_history(session_id)

        await asyncio.sleep(0)
        note = f"[{role}] {clean_content[:180]}"
        if note not in session["memory_notes"]:
            session["memory_notes"].append(note)
            session["memory_notes"] = session["memory_notes"][-25:]

        self._save_session(session)
        log_structured_event(
            event_type="async_memory_consolidation",
            intent=f"Persist {role} turn into session memory for {session_id}",
            outcome=f"Stored sanitized note (total notes: {len(session['memory_notes'])})",
            metadata={"session_id": session_id, "project_id": project_id},
        )
        return session
