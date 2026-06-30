"""
CMDB Agent — Natural-language /ask agent (LlamaIndex + OpenRouter).

A ReAct agent runs over an OpenRouter-hosted LLM. It has two tools:
  - run_cypher       — read-only Cypher; used to answer questions
  - run_write_cypher — write Cypher (MERGE/SET/DELETE/APOC); used only when the
                       user explicitly asks the agent to mutate the graph
                       (e.g. "combine HR and HR Team into one node").

For each call we capture the agent's verbose ReAct trace so the chat UI can
display the thought process verbatim. Heavy imports (llama_index) are done
lazily so the rest of the service runs even if the AI extras aren't installed.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
from typing import Any, Optional

from config import settings


GRAPH_SCHEMA = """
You query a CMDB knowledge graph in Neo4j. Schema:

NODES
  (:Device)  device_id, hostname, ip_address, mac_address, os, os_version,
             status ('active'|'inactive'), encryption (bool), encryption_type,
             device_type, serial_number, manufacturer, model, location,
             department, assigned_user, last_checkin
  (:User)    uid, name, email, employee_id, department, team, title,
             mfa_enabled (bool), last_login, status, groups (list), apps (list)
  (:App)     name_norm (lowercase key), name, app_id, vendor, app_type,
             category, owner, users_count, sso_enabled (bool), annual_cost_usd,
             is_stub (bool — true if only referenced, not yet in inventory)
  (:Location){name}   (:Department){name}   (:Team){name}

RELATIONSHIPS
  (:Device)-[:ASSIGNED_TO]->(:User)
  (:Device)-[:LOCATED_AT]->(:Location)
  (:Device)-[:BELONGS_TO]->(:Department)
  (:User)-[:USES]->(:App)
  (:User)-[:MEMBER_OF]->(:Team)
  (:App)-[:INTEGRATES_WITH]->(:App)
  (:App)-[:OWNED_BY]->(:Team)

RULES
- Default to READ-ONLY Cypher (MATCH/RETURN/WHERE/WITH/ORDER/LIMIT) via run_cypher.
- Only use run_write_cypher when the user explicitly asks you to MUTATE the graph
  (e.g. "merge HR and HR Team", "delete this device", "add a tag").
- The ontology (normalization.json) governs deterministic ingest rules: OS
  families, status synonyms, location type qualifiers, etc. To add/edit a rule
  (e.g. "recognize FreeBSD as an OS"), call get_ontology first, make the
  smallest change, then call update_ontology with the FULL updated JSON.
- For node merges, prefer APOC: CALL apoc.refactor.mergeNodes([survivor, dup],
  {properties:'discard', mergeRels:true}) so edges and props are transferred.
- App names are matched on name_norm (lowercase), e.g. {name_norm:'slack'}.
- For Location / Team / Department / User / Device names typed by the user,
  prefer flexible matching with toLower(...) CONTAINS toLower($q) instead of
  exact equality. Names often vary: "New York" should still find
  "New York HQ"; "HR" should still find "HR Team" if both exist.
- When the user asks for "all information" about a thing, also return its
  1-hop relationships, e.g. MATCH (n)-[r]-(m) RETURN n, type(r), m.
- "no MFA" / "without MFA" => u.mfa_enabled = false OR u.mfa_enabled IS NULL.
- Always RETURN concrete fields (names/hostnames), not whole nodes when
  possible (whole-node returns are allowed but verbose).
- After running a query, answer the user in one or two plain sentences.
""".strip()

SYSTEM_PROMPT = (
    "You are the CMDB assistant. Use run_cypher to read from the CMDB Neo4j graph "
    "and run_write_cypher to mutate it when (and only when) the user asks you to.\n\n"
    + GRAPH_SCHEMA
)


class CypherToolbox:
    """Holds the last query/rows so the API can return them alongside the answer."""

    def __init__(self, store):
        self.store = store
        self.last_cypher: Optional[str] = None
        self.last_rows: Optional[list[dict[str, Any]]] = None

    def run_cypher(self, cypher: str) -> str:
        """Execute a read-only Cypher query against the CMDB graph; returns JSON rows."""
        self.last_cypher = cypher
        try:
            rows = self.store.run_read_cypher(cypher)
        except Exception as exc:  # surfaced back to the agent to self-correct
            return f"ERROR: {exc}"
        self.last_rows = rows
        return json.dumps(rows[:50], default=str)

    def run_write_cypher(self, cypher: str) -> str:
        """Execute a WRITE Cypher query (MERGE/SET/DELETE/APOC). Use only when the
        user has explicitly asked to mutate the graph."""
        self.last_cypher = cypher
        try:
            rows = self.store.run_write_cypher(cypher)
        except Exception as exc:
            return f"ERROR: {exc}"
        self.last_rows = rows
        return json.dumps({"ok": True, "rows": rows[:20]}, default=str)

    def get_ontology(self) -> str:
        """Return the current normalization ontology (rules JSON) as a string."""
        from ingest.ontology import get_ontology
        return json.dumps(get_ontology(), indent=2)

    def update_ontology(self, rules_json: str) -> str:
        """Replace the ontology with the provided JSON. Validates regex + shape;
        rejects on any error so a bad edit can't break the pipeline.

        Use when the user asks to add/edit an OS family, status synonym, team
        suffix, location type, etc. ALWAYS call get_ontology first, make the
        smallest change, then pass the full updated object here.
        """
        from ingest.ontology import update_ontology
        try:
            new = json.loads(rules_json)
        except json.JSONDecodeError as exc:
            return f"ERROR: invalid JSON: {exc}"
        try:
            update_ontology(new)
        except ValueError as exc:
            return f"ERROR: {exc}"
        return "ok — ontology updated and hot-reloaded for the next ingest."


# Strip ANSI color codes that LlamaIndex prints in verbose mode.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _parse_react_trace(verbose_text: str) -> list[str]:
    """Turn LlamaIndex's verbose ReAct stdout into a list of one-line steps.

    Verbose format prints lines prefixed with markers like:
        > Running step ...
        Thought: ...
        Action: run_cypher
        Action Input: {"cypher": "MATCH ..."}
        Observation: [...rows...]
        Answer: ...
    We preserve each of those lines verbatim so the UI can show the agent's
    reasoning as it happened.
    """
    text = _ANSI_RE.sub("", verbose_text)
    steps: list[str] = []
    keep_prefixes = ("Thought:", "Action:", "Action Input:", "Observation:", "Answer:")
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(keep_prefixes):
            steps.append(s)
    return steps


def build_agent(store):
    from llama_index.llms.openrouter import OpenRouter
    from llama_index.core.tools import FunctionTool
    from llama_index.core.agent import ReActAgent

    key = settings.resolve_openrouter_key()
    if not key:
        raise RuntimeError(
            "No OpenRouter API key. Set OPENROUTER_API_KEY or place token.txt at repo root."
        )

    llm = OpenRouter(
        api_key=key,
        model=settings.ASK_MODEL,
        max_tokens=1024,
        context_window=8192,
        temperature=0.0,
    )
    toolbox = CypherToolbox(store)
    read_tool = FunctionTool.from_defaults(
        fn=toolbox.run_cypher,
        name="run_cypher",
        description="Execute a READ-ONLY Cypher query against the CMDB Neo4j graph "
                    "and return matching rows as JSON.",
    )
    write_tool = FunctionTool.from_defaults(
        fn=toolbox.run_write_cypher,
        name="run_write_cypher",
        description="Execute a WRITE Cypher query (MERGE / SET / DELETE / "
                    "apoc.refactor.mergeNodes) against the CMDB graph. "
                    "Use ONLY when the user has explicitly asked to mutate the graph.",
    )
    get_ont_tool = FunctionTool.from_defaults(
        fn=toolbox.get_ontology,
        name="get_ontology",
        description="Return the current normalization ontology (rules JSON) "
                    "that controls how raw strings are turned into structured "
                    "fields during ingest. Read this BEFORE you propose changes.",
    )
    update_ont_tool = FunctionTool.from_defaults(
        fn=toolbox.update_ontology,
        name="update_ontology",
        description="Replace the normalization ontology with the provided JSON "
                    "string. Use ONLY when the user explicitly asks to add or "
                    "edit a rule (e.g. 'add FreeBSD to the OS family list'). "
                    "Must contain the FULL ontology object — fetch with "
                    "get_ontology first, apply the smallest change, send it back.",
    )
    agent = ReActAgent.from_tools(
        [read_tool, write_tool, get_ont_tool, update_ont_tool], llm=llm,
        verbose=True, max_iterations=8, context=SYSTEM_PROMPT,
    )
    return agent, toolbox


def answer_question(question: str, store) -> dict:
    agent, toolbox = build_agent(store)
    # Capture the verbose ReAct trace so the chat UI can display the reasoning.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        response = agent.chat(question)
    return {
        "answer": str(response),
        "cypher": toolbox.last_cypher,
        "rows": toolbox.last_rows,
        "thoughts": _parse_react_trace(buf.getvalue()),
    }


# Serialize agent.chat() invocations: contextlib.redirect_stdout is process-wide
# so two concurrent streams would race for stdout. Take-home single-user is fine.
import threading
_AGENT_LOCK = threading.Lock()
_KEEP_PREFIXES = ("Thought:", "Action:", "Action Input:", "Observation:", "Answer:")


def stream_answer(question: str, store):
    """Generator yielding ('thought', line) events as the agent produces them,
    then a final ('done', {answer, cypher, rows, thoughts}) or ('error', msg).

    Implementation: agent.chat() runs in a worker thread with stdout redirected
    into a thread-safe Queue. The main thread (the FastAPI streaming response)
    consumes lines as they arrive — that's what makes the trace stream live.
    """
    import queue

    q: "queue.Queue[tuple[str, str]]" = queue.Queue()

    class TeeIO:
        def write(self, s):
            if s:
                q.put(("chunk", s))
            return len(s)

        def flush(self):
            pass

    result: dict = {}

    def worker():
        try:
            agent, toolbox = build_agent(store)
            with contextlib.redirect_stdout(TeeIO()):
                response = agent.chat(question)
            result["payload"] = {
                "answer": str(response),
                "cypher": toolbox.last_cypher,
                "rows": toolbox.last_rows,
            }
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            q.put(("__end__", ""))

    with _AGENT_LOCK:
        threading.Thread(target=worker, daemon=True).start()

        buffer = ""
        thoughts: list[str] = []
        while True:
            kind, data = q.get()
            if kind == "chunk":
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    clean = _ANSI_RE.sub("", line).strip()
                    if clean.startswith(_KEEP_PREFIXES):
                        thoughts.append(clean)
                        yield ("thought", clean)
            elif kind == "__end__":
                # Flush any remaining buffered line.
                if buffer.strip():
                    clean = _ANSI_RE.sub("", buffer).strip()
                    if clean.startswith(_KEEP_PREFIXES):
                        thoughts.append(clean)
                        yield ("thought", clean)
                if "error" in result:
                    yield ("error", result["error"])
                else:
                    payload = dict(result["payload"])
                    payload["thoughts"] = thoughts
                    yield ("done", payload)
                return
