"""
AI-First CMDB — FastAPI application.

Endpoints (per assignment):
  POST /ingest          upload raw infra/SaaS files -> normalized CIs in the graph
  POST /ingest/samples  convenience: ingest the bundled input_data/backend/* files
  GET  /devices         list Device CIs
  GET  /users           list User CIs
  GET  /apps            list App CIs
  GET  /ci/{identifier} fetch one CI + its relationships (by any identifier)
  POST /ask             natural-language question answered via the LlamaIndex agent

Storage backend is chosen by STORE_BACKEND ("neo4j" default, or "memory" for a
dependency-free run/demo). /ask requires the neo4j backend.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

import json
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import settings
from models.schemas import (
    IngestResult, AskRequest, AskResponse,
    SuggestRequest, SuggestResponse, TicketCreate, Ticket, StatusUpdate,
    Chat, ChatSummary, ChatCreate, ChatRename, ChatSendMessage,
)
from storage.factory import make_store
from storage.tickets import TicketStore
from storage.chats import ChatStore
from service import ingest_texts

SAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "input_data", "backend",
)

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = make_store()
    store.verify()
    store.apply_schema()
    state["store"] = store
    state["tickets"] = TicketStore()
    state["chats"] = ChatStore()
    yield
    store.close()


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def store():
    return state["store"]


def tickets() -> TicketStore:
    return state["tickets"]


def chats() -> ChatStore:
    return state["chats"]


# --- meta -------------------------------------------------------------------
@app.get("/")
def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION,
            "backend": settings.STORE_BACKEND}


@app.get("/health")
def health():
    try:
        store().verify()
        return {"status": "healthy", "backend": settings.STORE_BACKEND}
    except Exception as exc:
        raise HTTPException(503, f"Store unavailable: {exc}")


# --- ingest -----------------------------------------------------------------
@app.post("/ingest", response_model=list[IngestResult])
async def ingest(files: list[UploadFile] = File(...)):
    items = []
    for f in files:
        raw = await f.read()
        items.append((f.filename, raw.decode("utf-8", errors="replace")))
    return ingest_texts(store(), items)


@app.post("/ingest/samples", response_model=list[IngestResult])
def ingest_samples():
    if not os.path.isdir(SAMPLES_DIR):
        raise HTTPException(404, f"Sample directory not found: {SAMPLES_DIR}")
    items = []
    for name in sorted(os.listdir(SAMPLES_DIR)):
        path = os.path.join(SAMPLES_DIR, name)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                items.append((name, fh.read()))
    if not items:
        raise HTTPException(404, "No sample files found.")
    return ingest_texts(store(), items)


# --- list / detail ----------------------------------------------------------
@app.get("/devices")
def list_devices():
    return store().list_label("Device")


@app.get("/users")
def list_users():
    return store().list_label("User")


@app.get("/apps")
def list_apps():
    return store().list_label("App")


@app.get("/api/graph")
def graph():
    """Full CMDB topology as {nodes, edges} for visualization."""
    return store().graph_summary()


@app.get("/ci/{identifier}")
def get_ci(identifier: str):
    ci = store().get_ci(identifier)
    if ci is None:
        raise HTTPException(404, f"No CI found for identifier '{identifier}'")
    return ci


# --- ask --------------------------------------------------------------------
@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    from ai.agent import answer_question  # lazy: only needs llama_index when used
    try:
        result = answer_question(req.question, store())
    except Exception as exc:
        raise HTTPException(500, f"Agent error: {exc}")
    return AskResponse(question=req.question, **result)


# --- tickets (frontend ticket system, grounded in the CMDB) -----------------
@app.post("/api/ai/suggest", response_model=SuggestResponse)
def ai_suggest(req: SuggestRequest):
    from ai.ticket_suggest import suggest
    result = suggest(store(), req.title, req.description, req.email)
    return SuggestResponse(**result)


@app.get("/api/tickets", response_model=list[Ticket])
def list_tickets():
    return tickets().list()


@app.post("/api/tickets", response_model=Ticket)
def create_ticket(payload: TicketCreate):
    data = payload.model_dump()
    ticket = tickets().create(data)
    # mirror into the graph as a Ticket node linked to its CIs (best-effort)
    try:
        store().link_ticket(ticket)
    except Exception:
        pass
    return ticket


@app.patch("/api/tickets/{ticket_id}", response_model=Ticket)
def update_ticket(ticket_id: str, payload: StatusUpdate):
    try:
        updated = tickets().update_status(ticket_id, payload.status)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if updated is None:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    try:
        store().update_ticket_status(ticket_id, payload.status)
    except Exception:
        pass
    return updated


@app.get("/api/tickets/about/{identifier}")
def tickets_about(identifier: str):
    """Showcase: all tickets that reference a given CI (e.g. /api/tickets/about/slack)."""
    try:
        return store().tickets_about(identifier)
    except Exception as exc:
        raise HTTPException(500, str(exc))


# --- chats (multi-conversation history for /ask) ----------------------------
@app.get("/api/chats", response_model=list[ChatSummary])
def list_chats():
    return chats().list_summaries()


@app.post("/api/chats", response_model=Chat)
def create_chat(payload: ChatCreate):
    return chats().create(payload.title)


@app.get("/api/chats/{chat_id}", response_model=Chat)
def get_chat(chat_id: str):
    chat = chats().get(chat_id)
    if chat is None:
        raise HTTPException(404, f"Chat {chat_id} not found")
    return chat


@app.patch("/api/chats/{chat_id}", response_model=Chat)
def rename_chat(chat_id: str, payload: ChatRename):
    chat = chats().rename(chat_id, payload.title)
    if chat is None:
        raise HTTPException(404, f"Chat {chat_id} not found")
    return chat


@app.delete("/api/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str):
    if not chats().delete(chat_id):
        raise HTTPException(404, f"Chat {chat_id} not found")


@app.post("/api/chats/{chat_id}/messages", response_model=Chat)
def chat_send_message(chat_id: str, payload: ChatSendMessage):
    """Append the user message, run /ask, append the assistant reply, return chat."""
    from ai.agent import answer_question
    if chats().get(chat_id) is None:
        raise HTTPException(404, f"Chat {chat_id} not found")
    chats().append_message(chat_id, {"role": "user", "content": payload.question})
    try:
        result = answer_question(payload.question, store())
    except Exception as exc:
        chats().append_message(chat_id, {
            "role": "assistant",
            "content": f"Agent error: {exc}",
        })
        raise HTTPException(500, f"Agent error: {exc}")
    chat = chats().append_message(chat_id, {
        "role": "assistant",
        "content": result.get("answer") or "",
        "cypher": result.get("cypher"),
        "rows": result.get("rows"),
        "thoughts": result.get("thoughts"),
    })
    return chat


# --- ontology (normalization rules; live-editable) --------------------------
@app.get("/api/ontology")
def get_ontology_route():
    from ingest.ontology import get_ontology
    return get_ontology()


@app.put("/api/ontology")
def put_ontology_route(payload: dict):
    from ingest.ontology import update_ontology
    try:
        return update_ontology(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.post("/api/chats/{chat_id}/messages/stream")
def chat_send_message_stream(chat_id: str, payload: ChatSendMessage):
    """Stream the agent's thoughts as NDJSON as they're produced.

    Each line is a JSON object:
      {"type":"thought","content":"Thought: ..."}
      {"type":"thought","content":"Action: run_cypher"}
      ...
      {"type":"done","answer":"...","cypher":"...","rows":[...]}
      OR  {"type":"error","message":"..."}

    The user message is persisted at start; the assistant message is persisted
    once the agent finishes (so it includes the final answer + thoughts).
    """
    from ai.agent import stream_answer
    if chats().get(chat_id) is None:
        raise HTTPException(404, f"Chat {chat_id} not found")
    chats().append_message(chat_id, {"role": "user", "content": payload.question})

    def gen():
        try:
            for kind, data in stream_answer(payload.question, store()):
                if kind == "thought":
                    yield json.dumps({"type": "thought", "content": data}) + "\n"
                elif kind == "done":
                    chats().append_message(chat_id, {
                        "role": "assistant",
                        "content": data.get("answer") or "",
                        "cypher": data.get("cypher"),
                        "rows": data.get("rows"),
                        "thoughts": data.get("thoughts"),
                    })
                    yield json.dumps({"type": "done", **data}) + "\n"
                elif kind == "error":
                    chats().append_message(chat_id, {
                        "role": "assistant",
                        "content": f"Agent error: {data}",
                    })
                    yield json.dumps({"type": "error", "message": data}) + "\n"
        except Exception as exc:  # pragma: no cover — top-level safety net
            yield json.dumps({"type": "error", "message": str(exc)}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
