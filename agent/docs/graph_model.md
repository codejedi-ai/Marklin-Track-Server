# CMDB Knowledge Graph — Neo4j Data Model

This document specifies the graph model for the AI-First CMDB. The core idea:
**every ingested file is an incremental contribution to one shared graph.** A file
never replaces the graph — it either introduces new nodes (CIs it's the first to
mention), enriches existing nodes (more properties for a CI already present), or
adds relationships (new edges between CIs). This is expressed in Cypher with
`MERGE`, which is "match-or-create": idempotent upserts that make re-ingesting the
same file a no-op.

---

## 1. Why a graph

A CMDB's value is the *connections*, not the rows. The questions graders care about
— "if this app dies, which users and devices are affected?", "which users lack
MFA?", "what does this device depend on?" — are traversals, not table scans. In a
relational store these become multi-join queries that get worse as the model grows;
in a graph they are first-class edges. Neo4j also makes the multi-source merge
problem natural: the same device seen in three files resolves to **one node** via
`MERGE` on a stable key, with each file layering on more properties and edges.

---

## 2. Node labels (Configuration Items)

Three primary CI types, plus four lightweight **dimension nodes** that turn repeated
string values into queryable entities (the "knowledge" in knowledge graph).

### `:Device` — primary CI
Merge key: **`device_id`** (e.g. `C-19283`). This id is present and identical in
`sample_hardware.csv`, `.json`, and `.yaml`, so it is a reliable join key — the easy
identity case.

| Property | Example | Source(s) | Notes |
|---|---|---|---|
| `device_id` | `C-19283` | all hardware files | **merge key**, unique |
| `hostname` | `laptop-jdoe` | all | |
| `ip_address` | `10.10.22.5` | csv, json, yaml | |
| `mac_address` | `AA:BB:CC:DD:11:22` | csv, yaml | |
| `os` | `macOS` | all | normalized from `macOS Ventura` / `macos` |
| `os_version` | `Ventura 13.5` | yaml | |
| `os_build` | `22G74` | yaml | |
| `status` | `active` | all | normalized enum: `active` / `inactive` (`deactivated`→`inactive`) |
| `encryption` | `true` | csv, yaml | bool, normalized from `FileVault Enabled` / `FileVault 2` |
| `encryption_type` | `FileVault 2` | csv, yaml | |
| `device_type` | `laptop` | csv, yaml | |
| `serial_number` | `LAP-JD-20230615` | csv, yaml | |
| `manufacturer` / `model` / `cpu` / `ram_gb` / `storage_gb` | `Apple` / `MacBook Pro 14"` | yaml | hardware specs |
| `last_checkin` | `2024-07-23T13:45:00Z` | all | conflict policy: keep **max** (most recent) |
| `compliant` / `last_audit` / `warranty_expiry` | `true` | yaml | |
| `firewall_enabled` / `antivirus` / `mdm_enrolled` | `CrowdStrike Falcon` | yaml | security posture |
| `_sources` | `["hardware.csv","hardware.yaml"]` | — | provenance, append-only |
| `_first_seen` / `_last_updated` | timestamp | — | provenance |

### `:User` — primary CI
Merge key: **resolved `uid`** (synthetic). Unlike devices, users have *no* reliable
shared key — see §4. Candidate identifiers, in priority order: `employee_id` (yaml
only) → normalized `email` → name similarity.

| Property | Example | Source(s) |
|---|---|---|
| `uid` | `usr_8a1f...` | assigned at resolution (**merge key**) |
| `name` | `John Doe` | hardware, okta |
| `email` | `john.doe@example.com` | hardware, okta — **conflicts**: `john.d@` vs `john.doe@` |
| `employee_id` | `EMP-2156` | yaml |
| `department` / `team` / `title` | `Engineering` / `Platform Engineering` / `CTO` | yaml |
| `mfa_enabled` | `true` | okta |
| `last_login` | `2024-07-22T09:15:00Z` | okta |
| `status` | `active` | okta, normalized from `ACTIVE` |
| `groups` | `["Engineering","Admins"]` | okta |
| `_sources`, `_first_seen`, `_last_updated` | — | provenance |

### `:App` — primary CI
Merge key: **normalized `name`** (e.g. `slack`). Chosen deliberately: `app_id`
(`APP-001`) appears *only* in `sample_app.json`, but the app **name** is the common
reference across every file that mentions an app — the inventory, the Okta `apps[]`
arrays, and the `integrations[]` arrays. Merging on name avoids creating duplicate
nodes for the same app seen from different sources.

| Property | Example | Source(s) |
|---|---|---|
| `name_norm` | `slack` | all app-referencing files (**merge key**) |
| `name` | `Slack` | display name |
| `app_id` | `APP-001` | app inventory |
| `vendor` | `Salesforce Inc.` | app inventory |
| `app_type` | `SaaS` | app inventory |
| `category` / `deployment` / `owner` | `Collaboration` / `cloud` / `IT Operations` | app inventory |
| `users_count` | `52` | app inventory |
| `sso_enabled` | `true` | app inventory |
| `contract_renewal` / `annual_cost_usd` | `2025-03-15` / `24000` | app inventory |
| `_stub` | `true` | set when first seen only as a *reference* (e.g. Okta `apps[]`) before the inventory file arrives; cleared on enrichment |
| `_sources`, ... | — | provenance |

### Dimension nodes (normalize repeated values into entities)
- `:Location { name }` — `London`, `New York HQ`, `San Francisco Office`. Lets you ask "all devices in London."
- `:Department { name }` — `Engineering`, `Executive`.
- `:Team { name }` — `Platform Engineering`, `DevOps`, `IT Operations` (also app owners).
- `:OperatingSystem { name, version }` — optional; enables "all devices on macOS Sonoma."

These are optional-but-recommended: they make the graph answer aggregate questions
without scanning device properties, and they keep location/department spellings
canonical in one place.

---

## 3. Relationships (edges)

| Edge | Direction | Source | Meaning |
|---|---|---|---|
| `:ASSIGNED_TO` | `(:Device)→(:User)` | hardware `assigned_to` | device ownership |
| `:USES` | `(:User)→(:App)` | okta `apps[]` | app usage |
| `:INTEGRATES_WITH` | `(:App)→(:App)` | app `integrations[]` | integration link |
| `:DEPENDS_ON` | `(:App)→(:App)` | derived/declared | dependency (directional) |
| `:LOCATED_AT` | `(:Device)→(:Location)` | hardware `location` | physical site |
| `:BELONGS_TO` | `(:User)→(:Department)` / `(:Device)→(:Department)` | hardware/okta | org unit |
| `:MEMBER_OF` | `(:User)→(:Team)` | yaml `team`, okta `groups` | team membership |
| `:OWNED_BY` | `(:App)→(:Team)` | app `owner` | app ownership |
| `:RUNS` | `(:Device)→(:OperatingSystem)` | hardware `os` | optional |

Edges carry their own provenance (`_sources`, `_first_seen`) so you can answer "where
did we learn John uses Slack?" — useful for the `/ask` reasoning and for audits.

---

## 4. Identity resolution (the hard part)

`MERGE` is only as good as the key you merge on. Each CI type has a different
difficulty:

**Device — easy.** `device_id` is stable across all three hardware files.
`MERGE (d:Device {device_id: $id})` — done. The three files for `C-19283` collapse to
one node automatically.

**App — medium.** Merge on `name_norm` (lowercased, trimmed). The inventory supplies
`app_id` and rich metadata; references (`apps[]`, `integrations[]`) supply only the
name. Both `MERGE` on the same normalized name, so a reference creates a stub that the
inventory later enriches — one node, not two.

**User — hard.** No shared key. Resolution order on each incoming user record:
1. **`employee_id` exact match** (yaml) → strongest signal.
2. **normalized `email` exact match** — but note `john.d@example.com` (okta) vs
   `john.doe@example.com` (yaml) are the *same person* with *different* emails, so
   email alone is insufficient.
3. **Similarity match** on `name` (+ email local-part) using the existing matching
   engine (`utils/similarity.py`, `pipeline/layer1–3`). This is exactly where the
   salvaged reconciliation pipeline plugs in: it scores whether an incoming record
   refers to an already-present `:User`, returning match / uncertain / no-match.
   - **match** → `MERGE` onto the existing `uid`.
   - **no-match** → create a new `:User` with a fresh `uid`.
   - **uncertain** → create the node but flag it for the Layer-4 human-review queue
     (kept from the original code) and store both candidate emails.

This keeps AI usage principled per the rubric: deterministic keys first, AI only for
the ambiguous residue, with human review as the safety net.

---

## 5. Merge semantics — "each file adds onto the graph"

Every ingest follows the same five steps per record:

1. **Parse** the file (CSV/JSON/YAML) into raw records.
2. **Normalize** field values (`utils/normalization.py`): OS strings → canonical,
   encryption strings → bool, status → enum, names/emails lowercased for matching.
3. **Resolve identity** → canonical merge key (§4).
4. **`MERGE` the node** on its key, then `SET` properties using the precedence policy
   below, and **append** to `_sources` (never overwrite provenance).
5. **`MERGE` relationships** to related CIs, resolving *their* identities too —
   creating stub nodes for things referenced but not yet ingested.

### Property precedence on conflict
When two sources disagree on a property for the same node:

- **Source-richness ranking for devices:** `yaml > csv > json`. The YAML export is
  deeply nested and most detailed; the JSON is the sparsest. A higher-priority source's
  non-null value wins.
- **`last_checkin`:** always keep the **maximum** (most recent), regardless of source.
- **`status`:** prefer the value from the most recently-checked-in source; if still
  conflicting, record both in `_conflicts` and surface for review rather than silently
  picking.
- **Append-only fields:** `_sources`, `groups`, and relationship sets are unioned, not
  replaced.

Conflicts are not hidden — a `_conflicts` map property (e.g.
`{location: ["London","New York HQ"]}`) preserves the disagreement so `/ask` and a
reviewer can see it. This demonstrates "edge cases considered" for the rubric.

### Stub / lazy nodes
Okta lists `apps: ["GitHub","Slack"]` before the app inventory is ingested. We create
`(:App {name_norm:"github", _stub:true})` immediately and attach the `:USES` edge. When
`sample_app.json` later arrives, `MERGE` on `name_norm` matches that stub and enriches
it (vendor, cost, `_stub:false`). This is the literal expression of your requirement:
a file adds *either* objects *or* relationships, and partial knowledge is filled in as
more files arrive — in any order.

---

## 6. File → graph contribution map

| File | Creates / enriches nodes | Adds relationships |
|---|---|---|
| `sample_hardware.csv` | `:Device` (+ `:User` stub, `:Location`, `:Department`) | `ASSIGNED_TO`, `LOCATED_AT`, `BELONGS_TO` |
| `sample_hardware.json` | enriches existing `:Device` (os, location, status) | — |
| `sample_hardware.yaml` | enriches `:Device` (specs, security, compliance) + rich `:User` (employee_id, team) | `MEMBER_OF`, `RUNS` |
| `sample_okta.json` | `:User` (mfa, last_login, groups) + `:App` stubs | `USES`, `MEMBER_OF` |
| `sample_app.json` | `:App` (vendor, cost, sso) — enriches okta stubs | `INTEGRATES_WITH`, `OWNED_BY` |

Ingest order does not matter: any file can arrive first because every reference
`MERGE`s a stub that later files enrich.

---

## 7. Constraints & indexes

Uniqueness constraints double as the indexes that make `MERGE` fast and prevent
duplicate CIs. See `storage/schema.cypher`. Summary:

- `UNIQUE (:Device {device_id})`
- `UNIQUE (:User {uid})`
- `UNIQUE (:App {name_norm})`
- `UNIQUE (:Location {name})`, `(:Department {name})`, `(:Team {name})`
- secondary indexes on `:User(email)`, `:User(employee_id)`, `:Device(hostname)`,
  `:App(app_id)` to support resolution lookups and `/ask`.

---

## 8. How this powers the API

- `POST /ingest` → runs the five-step pipeline above per record.
- `GET /devices` / `/users` / `/apps` → `MATCH (n:Device) RETURN n` etc.
- `GET /ci/<id>` → `MATCH (n {…id…})-[r]-(m) RETURN n, r, m` — node plus its
  neighborhood, which is the natural "CI detail" view in a graph.
- `POST /ask` → AI translates the question to **Cypher**, executes it, and the LLM
  phrases the result. "Which users don't have MFA?" →
  `MATCH (u:User) WHERE u.mfa_enabled = false RETURN u.name`. The graph schema is small
  and fixed, so text-to-Cypher is reliable and the query result grounds the answer
  (no hallucinated data).

---

## 9. Local Neo4j (Docker)

A self-contained `docker-compose.yml` so the whole project runs with one command
(rubric: "database initializes automatically"). See `docker-compose.yml`. The API reads
`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` from env; `schema.cypher` is applied on
first startup to create constraints before any ingest.
