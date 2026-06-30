"""
CMDB Agent — Ingest service (framework-free).

Orchestrates ingesting a set of (filename, text) items into any store that
implements the storage interface. Kept independent of FastAPI so it can be
unit/end-to-end tested directly against the in-memory backend.
"""
from __future__ import annotations

from ingest.pipeline import parse_and_build, ordering_key
from ingest.resolve import UserResolver
from models.schemas import IngestResult


def ingest_texts(store, items: list[tuple[str, str]]) -> list[IngestResult]:
    """Ingest [(filename, text), ...] into the store. One resolver, seeded from the
    graph, keeps user identity stable. Files are written in ascending source
    priority so richer sources win on conflicting scalar fields."""
    resolver = UserResolver()
    resolver.seed(store.all_users_min())
    ordered = sorted(items, key=lambda it: ordering_key(it[0], it[1]))

    results: list[IngestResult] = []
    for filename, text in ordered:
        errors: list[str] = []
        try:
            source_type, batch = parse_and_build(filename, text, resolver)
            if source_type == "unknown":
                errors.append("Unrecognized source format; nothing ingested.")
                nodes, edges = 0, 0
            else:
                nodes, edges = store.write_batch(batch)
        except Exception as exc:  # one bad file shouldn't fail the whole upload
            source_type, nodes, edges = "error", 0, 0
            errors.append(str(exc))
        results.append(IngestResult(
            source=filename, detected=source_type,
            nodes_written=nodes, edges_written=edges, errors=errors,
        ))
    return results
