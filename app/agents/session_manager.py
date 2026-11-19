import asyncio
from typing import Any
from app.observability.telemetry import log_structured_event, redact_pii


class AdvisorSessionStore:
    """Manages session state, sliding-window history compaction, and async memory notes."""

    def __init__(self, max_history_turns: int = 10, max_summary_chars: int = 1200) -> None:
        self.max_history_turns = max_history_turns
        self.max_summary_chars = max_summary_chars
        self._sessions: dict[str, dict[str, Any]] = {}

    def get_or_create_session(self, session_id: str, project_id: str = "ctsal200") -> dict[str, Any]:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "session_id": session_id,
                "project_id": project_id,
                "history": [],
                "compacted_summary": "",
                "memory_notes": [],
            }
        return self._sessions[session_id]

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

        log_structured_event(
            event_type="async_memory_consolidation",
            intent=f"Persist {role} turn into session memory for {session_id}",
            outcome=f"Stored sanitized note (total notes: {len(session['memory_notes'])})",
            metadata={"session_id": session_id, "project_id": project_id},
        )
        return session
