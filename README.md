# AI-First CMDB + Grounded Ticket System

Two connected pieces from the Standard Template Labs take-homes, built as one
integrated product:

- **`agent/`** — the backend nugget: an **AI-First Configuration Management Database**
  as a **Neo4j knowledge graph**. Ingests messy IT/SaaS exports, normalizes them into
  typed Configuration Items (Device / User / App), resolves the same entity across
  sources, stores them as a graph, and answers natural-language questions via a
  **LlamaIndex agent on OpenRouter** (`/ask`).
- **`frontend/`** — the wrapper: an **AI-first ticket system** (React + TS + Tailwind)
  whose triage is **grounded in the CMDB**. The "Generate AI Suggestions" button is
  powered by the graph, not a mock.

## How they connect

Support tickets are *about* configuration items. When someone submits "Can't access
Slack," the backend looks them up in the CMDB graph (device, department, apps, MFA
status) and grounds the suggested category / priority / tags / response in those real
facts — then links the ticket into the graph as `(:Ticket)-[:ABOUT]->(:User|:App)`.
The same backend serves both the CMDB endpoints and the ticket endpoints.

```
 React frontend ──HTTP──> FastAPI (agent/) ──> Neo4j knowledge graph
   tickets UI            /api/ai/suggest  ──┐    (CIs + Ticket nodes)
                         /api/tickets       └──> CMDB lookups ground the AI
                         /ingest /ask
```

## Run the whole thing

```bash
# 1. Backend + Neo4j
cd agent
export OPENROUTER_API_KEY=$(cat ../token.txt)
docker compose up --build           # API on :8000, Neo4j on :7474

# 2. Seed the CMDB
curl -X POST http://localhost:8000/ingest/samples

# 3. Frontend
cd ../frontend
npm install && npm run dev          # http://localhost:5173
```

Then submit a ticket "Can't access Slack" with email `c.santos@example.com` →
the AI returns **High** priority + an **MFA** tag, grounded in that user's graph
profile.

See `agent/README.md` and `frontend/README.md` for details, architecture, and tests.
`agent/_old_datawise/` is pre-pivot code and can be deleted.
