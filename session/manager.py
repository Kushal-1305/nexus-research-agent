



# session/manager.py

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

_DEFAULT_SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "sessions")
SESSIONS_DIR = os.environ.get("SESSIONS_DIR", _DEFAULT_SESSIONS_DIR)


def _ensure_dir() -> None:
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def _session_path(session_id: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{session_id}.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_data(session_id: str) -> dict:
    path = _session_path(session_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _save_data(session_id: str, data: dict) -> None:
    _ensure_dir()
    with open(_session_path(session_id), "w") as f:
        json.dump(data, f, indent=2)


def delete_session(session_id: str) -> None:
    path = _session_path(session_id)
    if os.path.exists(path):
        os.remove(path)


def archive_session(session_id: str) -> None:
    data = _load_data(session_id)
    if data:
        data["archived"] = True
        _save_data(session_id, data)


def unarchive_session(session_id: str) -> None:
    data = _load_data(session_id)
    if data:
        data["archived"] = False
        _save_data(session_id, data)


def _parse_session_row(data: dict) -> dict:
    return {
        "id":         data["id"],
        "title":      data.get("title", ""),
        "summary":    data.get("summary", ""),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
        "turn_count": len(data.get("turns", [])),
        "archived":   data.get("archived", False),
    }


def list_sessions() -> list[dict]:
    _ensure_dir()
    sessions = []
    for fname in os.listdir(SESSIONS_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(SESSIONS_DIR, fname)) as f:
                    data = json.load(f)
                if not data.get("archived", False):
                    sessions.append(_parse_session_row(data))
            except Exception:
                continue
    return sorted(sessions, key=lambda s: s.get("updated_at", ""), reverse=True)


def list_archived_sessions() -> list[dict]:
    _ensure_dir()
    sessions = []
    for fname in os.listdir(SESSIONS_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(SESSIONS_DIR, fname)) as f:
                    data = json.load(f)
                if data.get("archived", False):
                    sessions.append(_parse_session_row(data))
            except Exception:
                continue
    return sorted(sessions, key=lambda s: s.get("updated_at", ""), reverse=True)


class Session:
    def __init__(
        self,
        session_id: Optional[str] = None,
        title: str = "",
    ):
        _ensure_dir()
        if session_id and os.path.exists(_session_path(session_id)):
            self.session_id = session_id
        else:
            self.session_id = session_id or str(uuid.uuid4())
            now = _now()
            _save_data(self.session_id, {
                "id":         self.session_id,
                "title":      title or "New Chat",
                "summary":    "",
                "created_at": now,
                "updated_at": now,
                "messages":   [],
                "turns":      [],
            })

    def _read(self) -> dict:
        return _load_data(self.session_id)

    def _write(self, data: dict) -> None:
        data["updated_at"] = _now()
        _save_data(self.session_id, data)

    # ── Messages ──────────────────────────────────────────────

    def add_message(self, role: str, content: str) -> None:
        data = self._read()
        data.setdefault("messages", []).append({
            "role": role, "content": content, "created_at": _now()
        })
        self._write(data)

    def get_history(self, limit: int = 20) -> list[dict]:
        data = self._read()
        messages = data.get("messages", [])
        return [{"role": m["role"], "content": m["content"]} for m in messages[-limit:]]

    # ── Turns ─────────────────────────────────────────────────

    def add_turn(
        self,
        question: str,
        answer: str,
        sources: list[dict] | None = None,
        search_queries: list[str] | None = None,
        context_snippets: list[dict] | None = None,
    ) -> None:
        data = self._read()
        now = _now()
        # Store a compact version of context snippets (url + title + first 300 chars)
        compact_snippets = []
        for c in (context_snippets or []):
            compact_snippets.append({
                "url":    c.get("url", ""),
                "title":  c.get("title", ""),
                "domain": c.get("domain", ""),
                "score":  c.get("score", 0),
                "text":   c.get("text", "")[:300],
            })
        data.setdefault("turns", []).append({
            "question":         question,
            "answer":           answer,
            "sources":          sources or [],
            "search_queries":   search_queries or [],
            "context_snippets": compact_snippets,
            "created_at":       now,
        })
        # Sync to messages with timestamps
        data.setdefault("messages", []).append({"role": "user",      "content": question, "created_at": now})
        data.setdefault("messages", []).append({"role": "assistant", "content": answer,   "created_at": now})
        self._write(data)

    def get_turns(self) -> list[dict]:
        return self._read().get("turns", [])

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> str:
        return self._read().get("summary", "")

    def update_summary(self, summary: str) -> None:
        data = self._read()
        data["summary"] = summary
        self._write(data)

    # ── Title ─────────────────────────────────────────────────

    def get_title(self) -> str:
        return self._read().get("title", "")

    def set_title(self, title: str) -> None:
        data = self._read()
        data["title"] = title
        self._write(data)
