# AI-First CMDB — Knowledge Graph Agent

A runnable prototype of an AI-powered Configuration Management Database. It ingests
messy IT-infrastructure and SaaS exports (hardware CSV/JSON/YAML, Okta, app
inventory), normalizes them into typed Configuration Items (CIs), resolves the same
real-world entity seen across multiple sources into a single node, stores everything
as a **Neo4j knowledge graph**, and answers natural-language questions through a
**LlamaIndex agent running on OpenRouter**.

## Why a graph

A CMDB's value is the connections between CIs, not flat rows. Questions like "if
Slack goes down, who's affected?" or "which devices are unencrypted?" are graph
traversals. Neo4j makes relationships first-class and makes the multi-source merge
natural: the same device seen in three files becomes **one node** via `MERGE` on a
stable key, with each file layering on more properties and edges. Every ingested
file is an incremental contribution — it adds new nodes, enriches existing ones, or
adds relationships. Re-ingesting a file is idempotent.

See `docs/graph_model.md` for the full data-model rationale and `storage/schema.cypher`
for constraints + the MERGE/`/ask` templates.

## Quick start

```bash
# 1. Bring up Neo4j + the API together (DB schema initializes automatically)
export OPENROUTER_API_KEY=sk-or-...      # only needed for /ask
docker compose up --build

# 2. Load the provided sample data into the graph
curl -X POST http://localhost:8000/ingest/samples

# 3. Explore
curl http://localhost:8000/devices
curl http://localhost:8000/ci/C-19283
curl -X POST http://localhost:8000/ask \
     -H 'Content-Type: application/json' \
     -d '{"question": "Which users do not have MFA?"}'
```

Interactive API docs: http://localhost:8000/docs · Neo4j Browser: http://localhost:7474

### Running without Docker

```bash
pip install -r requirements.txt
# point at any Neo4j 5.x; defaults match docker-compose
export NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=cmdb-dev-password
uvicorn main:app --reload
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest` | upload raw files (multipart) → CIs in the graph |
| POST | `/ingest/samples` | ingest the bundled `input_data/backend/*` |
| GET | `/devices` `/users` `/apps` | list CIs |
| GET | `/ci/{identifier}` | one CI + its relationships (by device_id, uid, hostname, email, app name…) |
| POST | `/ask` | natural-language question → Cypher → grounded answer |
| POST | `/api/ai/suggest` | ticket triage grounded in the CMDB (category, tags, priority, response, related CIs) |
| GET/POST | `/api/tickets` | list / create tickets (file-backed; mirrored as `:Ticket` graph nodes) |
| PATCH | `/api/tickets/{id}` | update ticket status |
| GET | `/api/tickets/about/{identifier}` | all tickets referencing a CI (e.g. `…/about/slack`) |

The ticket endpoints power the React frontend (`../frontend`). Tickets are persisted
to a JSON file store (`data_store/tickets.json`, the CRUD source of truth) and also
written into Neo4j as `(:Ticket)-[:ABOUT]->(:User|:Device|:App)` so the graph can
answer "which tickets affect Slack?". `/api/ai/suggest` looks the submitter up in the
graph and grounds its triage in their real device/apps/MFA status — see
`ai/ticket_suggest.py`.

## Architecture

```
ingest/   parsers.py    structural parse of each source -> uniform records
          normalize.py  value canonicalization (OS, status, encryption, …)
          resolve.py    user identity resolution (employee_id > email > name similarity)
          pipeline.py   parse -> normalize -> resolve -> emit graph node/edge ops
storage/  graph.py      Neo4j driver: idempotent MERGE writes + read queries
          schema.cypher constraints, indexes, MERGE & /ask templates
ai/       agent.py      LlamaIndex ReAct agent (OpenRouter LLM) with a run_cypher tool
models/   schemas.py    CI + API pydantic models
main.py                 FastAPI wiring
```

### Data model (CIs)

- **Device** — merge key `device_id` (stable across all three hardware files).
- **User** — merge key is a resolved synthetic `uid`; no reliable shared key exists.
- **App** — merge key is the normalized `name` (the only identifier shared by the
  inventory, Okta `apps[]`, and `integrations[]`); `app_id` is stored as a property.
- Dimension nodes **Location / Department / Team** turn repeated strings into
  queryable entities.

Relationships: `ASSIGNED_TO`, `USES`, `INTEGRATES_WITH`, `LOCATED_AT`, `BELONGS_TO`,
`MEMBER_OF`, `OWNED_BY`.

### Identity resolution (the hard part)

The sample data is deliberately messy: device `C-19283` appears in three files with
conflicting OS (`macOS Ventura` / `macos`), location, and status; the same person is
`John D.` (hardware) and `John Doe` (Okta/YAML) with two different emails
(`john.d@` vs `john.doe@`). Resolution order per incoming user record:

1. `employee_id` exact match
2. normalized `email` exact match
3. name similarity (Jaro-Winkler + token + phonetic) above a configurable threshold

Devices/apps merge on their stable keys directly. This keeps AI usage principled:
deterministic keys first, fuzzy matching only for the ambiguous residue.

### AI usage

- **`/ask`** is a LlamaIndex `ReActAgent` over an OpenRouter model. The graph schema
  is in its system prompt; it has one tool, `run_cypher`, which executes **read-only**
  Cypher. The model writes a query, runs it, and phrases the rows. Answers are grounded
  in real query results, so the model can't invent CMDB facts. The store rejects any
  non-read Cypher as a guardrail.
- AI is intentionally *not* used for parsing or normalization — those are
  deterministic and cheaper/safer in code. AI is reserved for the genuinely fuzzy
  task (translating English to a graph query). Model is configurable via `ASK_MODEL`.

## Conflict handling & provenance

On conflicting scalar fields, latest non-null value wins (sparse sources never
overwrite a richer one with null), and every node/edge keeps an append-only
`_sources` list plus `_first_seen` / `_last_updated`, so you can trace where each
fact came from.

## Testing

Three tiers, from no-dependency to full-stack:

```bash
pip install -r requirements.txt pytest && pytest      # from agent/

# unit + in-memory e2e only (no Neo4j, no network):
pytest tests/test_normalize.py tests/test_parsers.py \
       tests/test_pipeline.py tests/test_e2e_inmemory.py
```

- **Unit** (`test_normalize`, `test_parsers`, `test_pipeline`) — source detection,
  nested-YAML extraction, value normalization, cross-file device dedup, OS
  canonicalization, the John D./John Doe identity merge, and source precedence.
- **In-memory end-to-end** (`test_e2e_inmemory`) — runs the real ingest pipeline
  into the in-memory graph and asserts the stored graph returns the *correct
  answers*: users without MFA = {Carlos S., Michael Brown, Alex Johnson}, Slack's
  6 users, the merged `C-19283` (macOS / inactive / London), CI lookup by hostname.
- **API end-to-end** (`test_e2e_api`) — same flow through the real FastAPI app via
  `TestClient` (in-memory backend; skipped if FastAPI absent).
- **Live** (`test_e2e_live`) — real Neo4j + real OpenRouter, gated behind
  `RUN_LIVE_TESTS=1`. This is the test that proves `/ask` returns the right answer
  end-to-end (English → Cypher → grounded result).

### Run the structured API with no Neo4j

```bash
STORE_BACKEND=memory uvicorn main:app      # /ingest, /devices, /ci all work; /ask needs neo4j
```

## Assumptions & limitations

- Conflict precedence (`yaml > csv > json`, SaaS sources authoritative for their own
  entity) is enforced by writing sources in ascending priority order so a richer
  source overwrites scalars while a sparse one only fills gaps (see
  `pipeline.SOURCE_PRIORITY`). `last_checkin` is special-cased to keep the strict
  max regardless of source order.
- Team/location strings from different systems (`DevOps` vs `DevOps Team`,
  `New York HQ` vs `New York HQ - Floor 15`) are kept distinct — a good future use of
  AI enrichment to reconcile.
- Multi-valued team/location *strings* from different systems (`DevOps` vs
  `DevOps Team`) are still kept as distinct dimension nodes — a good future use of AI
  enrichment to reconcile. (Single-valued *edges* like `LOCATED_AT`/`BELONGS_TO` are
  now deduped: a conflicting source replaces rather than accumulates, so a device has
  exactly one location — the highest-priority one.)
- Single-instance, no pagination on list endpoints (fine at sample scale).

## Notes for graders

- The graph DB initializes its schema automatically on API startup
  (`GraphStore.apply_schema`).
- `_old_datawise/` contains the pre-pivot reconciliation code and can be deleted.
- Put the OpenRouter key in `OPENROUTER_API_KEY`; as a fallback the app reads
  `../token.txt`. Keep the key out of git (see `.gitignore`).
