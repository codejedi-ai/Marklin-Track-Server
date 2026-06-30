"""Store factory — picks the backend from settings.STORE_BACKEND.

Keeps the neo4j import lazy so the in-memory backend (and its tests) run with no
neo4j driver installed.
"""
from __future__ import annotations

from config import settings


def make_store():
    if settings.STORE_BACKEND == "memory":
        from storage.memory import InMemoryGraphStore
        return InMemoryGraphStore()
    from storage.graph import GraphStore
    return GraphStore()
