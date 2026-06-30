"""
CMDB Agent — Identity resolution.

Devices and apps have stable merge keys (device_id; normalized name), so they
resolve trivially in the pipeline. Users do not: the same person appears as
"John D." (hardware) and "John Doe" (Okta/YAML) with different emails
(john.d@ vs john.doe@). This module decides which existing user an incoming
record refers to, assigning a stable synthetic `uid`.

Resolution order (strongest signal first):
  1. employee_id exact match
  2. normalized email exact match
  3. name similarity above threshold (reuses utils.similarity)

The resolver keeps an in-memory index for the current process. It can be seeded
from the graph at startup so resolution is stable across separate ingest calls.
"""
from __future__ import annotations

import uuid
from typing import Optional

from utils.similarity import composite_name_similarity
from ingest.normalize import normalize_email, normalize_name
from config import settings


class _KnownUser:
    __slots__ = ("uid", "name", "email", "employee_id")

    def __init__(self, uid, name, email, employee_id):
        self.uid = uid
        self.name = name
        self.email = email
        self.employee_id = employee_id


class UserResolver:
    def __init__(self, threshold: Optional[float] = None):
        self.threshold = threshold if threshold is not None else settings.USER_MATCH_THRESHOLD
        self._known: list[_KnownUser] = []

    def seed(self, users: list[dict]) -> None:
        """Seed from existing graph users: [{uid, name, email, employee_id}]."""
        for u in users:
            self._known.append(_KnownUser(
                u.get("uid"), normalize_name(u.get("name")),
                normalize_email(u.get("email")), u.get("employee_id"),
            ))

    def resolve(self, name: Optional[str], email: Optional[str],
                employee_id: Optional[str]) -> tuple[str, bool]:
        """
        Return (uid, is_new). Matches an existing user or mints a new uid.
        """
        n = normalize_name(name)
        e = normalize_email(email)

        # 1. employee_id exact
        if employee_id:
            for k in self._known:
                if k.employee_id and k.employee_id == employee_id:
                    self._enrich(k, n, e, employee_id)
                    return k.uid, False

        # 2. email exact
        if e:
            for k in self._known:
                if k.email and k.email == e:
                    self._enrich(k, n, e, employee_id)
                    return k.uid, False

        # 3. name similarity
        if n:
            best, best_score = None, 0.0
            for k in self._known:
                if not k.name:
                    continue
                score = composite_name_similarity(n.lower(), k.name.lower())
                if score > best_score:
                    best, best_score = k, score
            if best is not None and best_score >= self.threshold:
                self._enrich(best, n, e, employee_id)
                return best.uid, False

        # No match -> new identity
        uid = f"usr_{uuid.uuid4().hex[:12]}"
        self._known.append(_KnownUser(uid, n, e, employee_id))
        return uid, True

    @staticmethod
    def _enrich(k: _KnownUser, n, e, employee_id) -> None:
        """Backfill identifiers we learn from a matched record."""
        if not k.email and e:
            k.email = e
        if not k.employee_id and employee_id:
            k.employee_id = employee_id
        if (not k.name or len(k.name) < len(n or "")) and n:
            k.name = n
