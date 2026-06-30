# Input data — provenance

This directory is split by **origin**, not by file type. Nothing here is moved
or renamed, and `/ingest/samples` continues to load **only** `backend/`.

| Subdirectory       | Origin            | Auto-loaded by `/ingest/samples`? | Purpose |
|--------------------|-------------------|-----------------------------------|---------|
| `backend/`         | Interview-given   | **Yes**                           | The canonical "stock" dataset shipped with the take-home. **Do not edit.** |
| `manual_upload/`   | Synthetic (mine)  | No                                | One Okta-shaped fixture for testing the drag-drop Upload UI. Exercises the team normalizer (`"Platform Engineering Team"` → `Platform Engineering`) and the location normalizer (`"HR Department"` → `HR`). |
| `synthetic_batch2/`| Synthetic (added in-session) | No                     | A second batch of synthetic infra/SaaS exports for ingest experiments. |

**Rules of thumb**

- Keep `backend/` pristine — that's the dataset the grader will diff against.
- All synthetic / experimental fixtures belong in a sibling directory whose
  name makes the provenance obvious (`synthetic_*`, `manual_upload/`, etc.).
- Anything dragged into the **Upload Data** view in the UI hits `POST /ingest`
  directly and never touches this folder; the graph stores `_sources: [<filename>]`
  on every node and edge so you can always trace what was loaded from where.
