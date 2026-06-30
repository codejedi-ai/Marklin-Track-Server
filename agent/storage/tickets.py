"""
Ticket store — file-backed JSON persistence (durable source of truth for ticket
CRUD). Kept separate from the graph: the graph holds the *topology* (Ticket->CI
relationships) while this store owns the ticket records themselves. Simple, no DB
setup, survives restarts.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone

from config import settings

VALID_STATUS = {"New", "In Progress", "Resolved"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TicketStore:
    def __init__(self, path: str | None = None):
        self.path = path or settings.TICKETS_FILE
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

    def _write(self, tickets: list[dict]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(tickets, f, indent=2, default=str)
        os.replace(tmp, self.path)  # atomic

    # --- CRUD -------------------------------------------------------------
    def create(self, data: dict) -> dict:
        ticket = {
            "id": f"TKT-{uuid.uuid4().hex[:8]}",
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "email": data.get("email"),
            "department": data.get("department"),
            "priority": data.get("priority") or "Medium",
            "status": "New",
            "category": data.get("category"),
            "tags": data.get("tags") or [],
            "suggested_response": data.get("suggested_response"),
            "related_cis": data.get("related_cis") or [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        with self._lock:
            tickets = self._read()
            tickets.append(ticket)
            self._write(tickets)
        return ticket

    def list(self) -> list[dict]:
        # newest first
        return sorted(self._read(), key=lambda t: t.get("created_at", ""), reverse=True)

    def get(self, ticket_id: str) -> dict | None:
        return next((t for t in self._read() if t["id"] == ticket_id), None)

    def update_status(self, ticket_id: str, status: str) -> dict | None:
        if status not in VALID_STATUS:
            raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUS}.")
        with self._lock:
            tickets = self._read()
            for t in tickets:
                if t["id"] == ticket_id:
                    t["status"] = status
                    t["updated_at"] = _now()
                    self._write(tickets)
                    return t
        return None
