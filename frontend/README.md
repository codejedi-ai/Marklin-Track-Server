# CMDB Support Desk — Frontend

An AI-first ticket management UI (React + TypeScript + Tailwind) for an internal
support team. The differentiator: the AI triage isn't mocked — it's **grounded in
the CMDB knowledge graph** from the backend. When a user submits a ticket, the
backend looks them up in the graph (their device, department, apps, MFA status) and
returns category, tags, priority, and a suggested response based on real
Configuration Items.

This is the "wrapper" around the backend nugget — but built to the frontend bar:
clean layout, async UX with loading/error states, editable AI suggestions with
explicit user control, and optimistic dashboard updates.

## Run

The backend (the `agent/` service) must be running first — see `../agent/README.md`
(`docker compose up`). Then:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

In dev, Vite proxies `/api/*` to `http://localhost:8000` (the FastAPI backend), so
no CORS setup is needed. For a non-default backend URL, set `VITE_API_BASE` in `.env`.

Seed some data so suggestions have something to ground against:

```bash
curl -X POST http://localhost:8000/ingest/samples
```

Then submit a ticket titled "Can't access Slack" with email
`c.santos@example.com` and click **Generate AI Suggestions** — it returns High
priority + an MFA tag because the graph shows that user has MFA disabled.

## Features (to spec)

- **Ticket submission form** — Title, Description, Email, optional Priority,
  Department. "Generate AI Suggestions" calls `POST /api/ai/suggest`.
- **Editable AI suggestions** — category, tags, priority, and response are all
  editable before you click **Use Suggestion**; related CIs are shown as chips,
  with a "Grounded in CMDB" badge when graph facts were used.
- **Dashboard** — ticket cards showing title, description, status, category, tags,
  priority, and the AI suggested response. Change status (New / In Progress /
  Resolved) with **optimistic updates** (revert + toast on failure). Filter by
  category, status, and tag.
- **Async UX** — spinners on every async action, inline + toast error feedback,
  empty/error/loading states on the dashboard.

## Structure

```
src/
  api.ts                typed fetch client + error handling
  types.ts              shared types (mirror the backend models)
  App.tsx               shell: tabs, toasts, optimistic status logic, data load
  components/
    TicketForm.tsx      submission + AI suggestion flow
    AiSuggestions.tsx   editable suggestion panel ("Use Suggestion")
    Dashboard.tsx       list + filters + states
    TicketCard.tsx      one ticket + status control
    Filters.tsx         category / status / tag filters
    ui.tsx              spinner, badges, chips, field
```

## Design decisions & limitations

- State is plain React hooks lifted into `App` (no Redux) — the app is small enough
  that this stays readable. Optimistic updates keep the dashboard snappy.
- The API client normalizes errors (network vs HTTP) into a single `ApiError` so the
  UI can show one friendly message everywhere.
- Suggestions are editable on purpose: the AI proposes, the human disposes.
- Not implemented (scope): auth, pagination, real-time push. The dashboard refreshes
  on demand and on ticket creation.

## How AI is used

The frontend treats `/api/ai/suggest` as an async AI call. The backend grounds the
suggestion in the CMDB graph (deterministic grounding always; OpenRouter LLM refines
the wording when a key is configured). See `../agent/ai/ticket_suggest.py`.
