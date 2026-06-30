"""
Chat store — file-backed JSON persistence for multi-conversation /ask history.

Same shape and threading pattern as TicketStore. Each chat owns its own message
list (alternating user / assistant). Title defaults to the first user message,
trimmed.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone

from config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(s: str, n: int = 60) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


class ChatStore:
    def __init__(self, path: str | None = None):
        self.path = path or settings.CHATS_FILE
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write([])

    # --- persistence ------------------------------------------------------
    def _read(self) -> list[dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write(self, chats: list[dict]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(chats, f, indent=2, default=str)
        os.replace(tmp, self.path)

    # --- CRUD -------------------------------------------------------------
    def create(self, title: str | None = None) -> dict:
        chat = {
            "id": uuid.uuid4().hex,
            "title": title or "New chat",
            "messages": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        with self._lock:
            chats = self._read()
            chats.append(chat)
            self._write(chats)
        return chat

    def list_summaries(self) -> list[dict]:
        chats = self._read()
        chats.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
        return [
            {
                "id": c["id"], "title": c.get("title") or "New chat",
                "message_count": len(c.get("messages") or []),
                "created_at": c.get("created_at"), "updated_at": c.get("updated_at"),
            }
            for c in chats
        ]

    def get(self, chat_id: str) -> dict | None:
        return next((c for c in self._read() if c["id"] == chat_id), None)

    def delete(self, chat_id: str) -> bool:
        with self._lock:
            chats = self._read()
            kept = [c for c in chats if c["id"] != chat_id]
            if len(kept) == len(chats):
                return False
            self._write(kept)
            return True

    def rename(self, chat_id: str, title: str) -> dict | None:
        with self._lock:
            chats = self._read()
            for c in chats:
                if c["id"] == chat_id:
                    c["title"] = title or "Untitled"
                    c["updated_at"] = _now()
                    self._write(chats)
                    return c
        return None

    def append_message(self, chat_id: str, message: dict) -> dict | None:
        """Append one message. If it's the first user message, derive a title."""
        message = dict(message)
        message.setdefault("ts", _now())
        with self._lock:
            chats = self._read()
            for c in chats:
                if c["id"] != chat_id:
                    continue
                msgs = c.setdefault("messages", [])
                msgs.append(message)
                if (c.get("title") in (None, "", "New chat")
                        and message.get("role") == "user"):
                    c["title"] = _truncate(message.get("content", "") or "New chat")
                c["updated_at"] = _now()
                self._write(chats)
                return c
        return None
