"""
CMDB Agent — Neo4j storage layer.

Turns the pipeline's GraphBatch (node/edge ops) into idempotent Cypher MERGEs,
and exposes read queries for the API and the /ask agent. The graph is the single
source of truth for all Configuration Items and their relationships.

Design notes:
- Labels / key fields / relationship types are validated against allow-lists
  before being interpolated into Cypher (they cannot be query parameters).
- Property values ARE parameters (injection-safe). `n += $props` only sets keys
  present in props; the pipeline already strips nulls, so a sparse source never
  clobbers a richer one with null. Latest non-null value wins on conflict, and
  provenance (`_sources`) is appended, never overwritten.
"""
from __future__ import annotations

from typing import Any, Optional

from neo4j import GraphDatabase
from neo4j.time import DateTime, Date

from config import settings
from relations import LIST_MERGE_PROPS, SINGLE_VALUED_RELS

_LABELS = {"Device", "User", "App", "Location", "Department", "Team",
           "OperatingSystem", "Ticket"}
_KEYS = {"device_id", "uid", "name_norm", "name", "id"}
_RELS = {"ASSIGNED_TO", "USES", "INTEGRATES_WITH", "DEPENDS_ON",
         "LOCATED_AT", "BELONGS_TO", "MEMBER_OF", "OWNED_BY", "RUNS", "ABOUT"}

_CONSTRAINTS = [
    "CREATE CONSTRAINT device_id IF NOT EXISTS FOR (d:Device) REQUIRE d.device_id IS UNIQUE",
    "CREATE CONSTRAINT user_uid IF NOT EXISTS FOR (u:User) REQUIRE u.uid IS UNIQUE",
    "CREATE CONSTRAINT app_name IF NOT EXISTS FOR (a:App) REQUIRE a.name_norm IS UNIQUE",
    "CREATE CONSTRAINT loc_name IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE",
    "CREATE CONSTRAINT dept_name IF NOT EXISTS FOR (d:Department) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT team_name IF NOT EXISTS FOR (t:Team) REQUIRE t.name IS UNIQUE",
    "CREATE INDEX user_email IF NOT EXISTS FOR (u:User) ON (u.email)",
    "CREATE INDEX user_empid IF NOT EXISTS FOR (u:User) ON (u.employee_id)",
    "CREATE INDEX device_host IF NOT EXISTS FOR (d:Device) ON (d.hostname)",
    "CREATE INDEX app_appid IF NOT EXISTS FOR (a:App) ON (a.app_id)",
]


def _jsonsafe(value: Any) -> Any:
    if isinstance(value, (DateTime, Date)):
        return value.iso_format()
    if isinstance(value, dict):
        return {k: _jsonsafe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonsafe(v) for v in value]
    return value


def _node_to_dict(node) -> dict:
    return {k: _jsonsafe(v) for k, v in dict(node).items()}


class GraphStore:
    def __init__(self, uri=None, user=None, password=None, database=None):
        self._driver = GraphDatabase.driver(
            uri or settings.NEO4J_URI,
            auth=(user or settings.NEO4J_USER, password or settings.NEO4J_PASSWORD),
        )
        self._db = database or settings.NEO4J_DATABASE

    def close(self):
        self._driver.close()

    def verify(self) -> bool:
        self._driver.verify_connectivity()
        return True

    # --- schema -----------------------------------------------------------
    def apply_schema(self) -> None:
        with self._driver.session(database=self._db) as s:
            for stmt in _CONSTRAINTS:
                s.run(stmt)

    # --- writes -----------------------------------------------------------
    def write_batch(self, batch) -> tuple[int, int]:
        """Apply node + edge ops. Returns (unique_nodes, edges_written)."""
        with self._driver.session(database=self._db) as s:
            for n in batch.nodes:
                self._merge_node(s, n)
            for e in batch.edges:
                self._merge_edge(s, e)
        return len(batch.node_keys), len(batch.edges)

    @staticmethod
    def _merge_node(session, op: dict) -> None:
        label, key = op["label"], op["key_field"]
        if label not in _LABELS or key not in _KEYS:
            raise ValueError(f"Illegal node label/key: {label}/{key}")
        props = dict(op["props"])
        # last_checkin is handled separately so we keep the MAX, not latest-write
        last_checkin = props.pop("last_checkin", None)
        # List-merge props (floors, suites, …) UNION rather than overwrite, so a
        # Location node aggregates every variant seen across sources.
        list_props = {k: props.pop(k) for k in list(props) if k in LIST_MERGE_PROPS}
        list_clauses = ""
        list_params: dict = {}
        for idx, (lk, lv) in enumerate(list_props.items()):
            pname = f"lp{idx}"
            list_clauses += f" SET n.{lk} = apoc.coll.toSet(coalesce(n.{lk}, []) + ${pname})"
            list_params[pname] = lv if isinstance(lv, list) else [lv]
        cypher = (
            f"MERGE (n:{label} {{{key}: $key}}) "
            "ON CREATE SET n._first_seen = datetime(), n._sources = [$source] "
            "ON MATCH SET n._sources = CASE WHEN $source IN coalesce(n._sources, []) "
            "  THEN n._sources ELSE coalesce(n._sources, []) + $source END "
            "SET n._last_updated = datetime(), n += $props "
            + list_clauses +
            " FOREACH (_ IN CASE WHEN $lc IS NOT NULL AND "
            "  (n.last_checkin IS NULL OR n.last_checkin < $lc) THEN [1] ELSE [] END | "
            "  SET n.last_checkin = $lc)"
        )
        session.run(cypher, key=op["key_value"], source=op["source"],
                    props=props, lc=last_checkin, **list_params)

    @staticmethod
    def _merge_edge(session, op: dict) -> None:
        fl, fk, fv = op["from"]
        tl, tk, tv = op["to"]
        etype = op["type"]
        if fl not in _LABELS or tl not in _LABELS or fk not in _KEYS or tk not in _KEYS:
            raise ValueError("Illegal edge endpoint label/key")
        if etype not in _RELS:
            raise ValueError(f"Illegal relationship type: {etype}")
        if etype in SINGLE_VALUED_RELS:
            # single-valued: drop any prior edge of this type from the source node
            # so the highest-priority source (written last) wins
            session.run(
                f"MATCH (a:{fl} {{{fk}: $fk}})-[r:{etype}]->() DELETE r", fk=fv,
            )
        cypher = (
            f"MATCH (a:{fl} {{{fk}: $fk}}), (b:{tl} {{{tk}: $tk}}) "
            f"MERGE (a)-[r:{etype}]->(b) "
            "ON CREATE SET r._first_seen = datetime(), r._sources = [$source] "
            "ON MATCH SET r._sources = CASE WHEN $source IN coalesce(r._sources, []) "
            "  THEN r._sources ELSE coalesce(r._sources, []) + $source END"
        )
        session.run(cypher, fk=fv, tk=tv, source=op["source"])

    # --- reads ------------------------------------------------------------
    def _read(self, cypher: str, **params) -> list[dict]:
        with self._driver.session(database=self._db) as s:
            return [dict(r) for r in s.run(cypher, **params)]

    def list_label(self, label: str) -> list[dict]:
        if label not in _LABELS:
            raise ValueError(label)
        with self._driver.session(database=self._db) as s:
            return [_node_to_dict(r["n"]) for r in s.run(f"MATCH (n:{label}) RETURN n")]

    def get_ci(self, identifier: str) -> Optional[dict]:
        """Fetch a CI by any identifier plus its 1-hop neighborhood."""
        cypher = (
            "MATCH (n) WHERE n.device_id = $id OR n.uid = $id OR n.app_id = $id "
            "  OR n.hostname = $id OR n.name_norm = toLower($id) OR n.email = toLower($id) "
            "WITH n LIMIT 1 "
            "OPTIONAL MATCH (n)-[r]-(m) "
            "RETURN n AS node, collect(DISTINCT {rel: type(r), "
            "  direction: CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END, "
            "  node: m}) AS neighbors"
        )
        with self._driver.session(database=self._db) as s:
            rec = s.run(cypher, id=identifier).single()
            if not rec or rec["node"] is None:
                return None
            neighbors = []
            for nb in rec["neighbors"]:
                if nb.get("node") is None:
                    continue
                neighbors.append({
                    "rel": nb["rel"], "direction": nb["direction"],
                    "node": _node_to_dict(nb["node"]),
                })
            return {"ci": _node_to_dict(rec["node"]), "relationships": neighbors}

    def all_users_min(self) -> list[dict]:
        """Minimal user records to seed the identity resolver across ingests."""
        return self._read(
            "MATCH (u:User) RETURN u.uid AS uid, u.name AS name, "
            "u.email AS email, u.employee_id AS employee_id"
        )

    # --- tickets (topology only; file store owns the records) -------------
    def link_ticket(self, ticket: dict) -> None:
        props = {k: ticket.get(k) for k in
                 ("title", "status", "priority", "category", "email", "created_at")}
        props["tags"] = ticket.get("tags") or []
        props = {k: v for k, v in props.items() if v is not None}
        with self._driver.session(database=self._db) as s:
            s.run("MERGE (t:Ticket {id: $id}) SET t += $props",
                  id=ticket["id"], props=props)
            for ref in ticket.get("related_cis", []):
                ident = ref.get("id") or ref.get("identifier")
                if not ident:
                    continue
                s.run(
                    "MATCH (t:Ticket {id: $id}) "
                    "MATCH (n) WHERE n.device_id = $ref OR n.uid = $ref OR n.app_id = $ref "
                    "  OR n.hostname = $ref OR n.name_norm = toLower($ref) OR n.email = toLower($ref) "
                    "MERGE (t)-[:ABOUT]->(n)",
                    id=ticket["id"], ref=str(ident),
                )

    def update_ticket_status(self, ticket_id: str, status: str) -> None:
        with self._driver.session(database=self._db) as s:
            s.run("MATCH (t:Ticket {id: $id}) SET t.status = $s", id=ticket_id, s=status)

    def tickets_about(self, identifier: str) -> list[dict]:
        return self._read(
            "MATCH (n)<-[:ABOUT]-(t:Ticket) "
            "WHERE n.device_id = $id OR n.uid = $id OR n.app_id = $id "
            "  OR n.name_norm = toLower($id) OR n.email = toLower($id) "
            "RETURN t.id AS id, t.title AS title, t.status AS status",
            id=identifier,
        )

    def graph_summary(self) -> dict:
        """Return all CI nodes + edges as {nodes, edges} for visualization.

        Each node gets a stable string id derived from its label + merge key, so
        edge endpoints reference the same node ids without needing Neo4j's
        internal ids. Tickets are excluded — the graph view is a CMDB topology.
        """
        node_q = (
            "MATCH (n) WHERE NOT n:Ticket "
            "RETURN labels(n)[0] AS label, "
            "  coalesce(n.device_id, n.uid, n.app_id, n.name_norm, n.name) AS key, "
            "  coalesce(n.name, n.hostname, n.email, n.device_id, n.app_id, n.uid) AS display, "
            "  properties(n) AS props"
        )
        edge_q = (
            "MATCH (a)-[r]->(b) WHERE NOT a:Ticket AND NOT b:Ticket "
            "RETURN labels(a)[0] AS al, "
            "  coalesce(a.device_id, a.uid, a.app_id, a.name_norm, a.name) AS ak, "
            "  labels(b)[0] AS bl, "
            "  coalesce(b.device_id, b.uid, b.app_id, b.name_norm, b.name) AS bk, "
            "  type(r) AS rel"
        )
        with self._driver.session(database=self._db) as s:
            nodes = []
            for rec in s.run(node_q):
                if rec["key"] is None:
                    continue
                nodes.append({
                    "id": f"{rec['label']}:{rec['key']}",
                    "label": rec["label"],
                    "display": rec["display"] or rec["key"],
                    "props": {k: _jsonsafe(v) for k, v in dict(rec["props"]).items()},
                })
            edges = []
            for rec in s.run(edge_q):
                if rec["ak"] is None or rec["bk"] is None:
                    continue
                edges.append({
                    "source": f"{rec['al']}:{rec['ak']}",
                    "target": f"{rec['bl']}:{rec['bk']}",
                    "type": rec["rel"],
                })
            return {"nodes": nodes, "edges": edges}

    def run_read_cypher(self, cypher: str) -> list[dict]:
        """Execute a read-only Cypher query (used by the /ask agent)."""
        lowered = cypher.lower()
        forbidden = ("create", "merge", "delete", "set ", "remove", "drop",
                     "detach", "call db.", "load csv")
        if any(tok in lowered for tok in forbidden):
            raise ValueError("Only read-only queries are permitted.")
        with self._driver.session(database=self._db) as s:
            out = []
            for rec in s.run(cypher):
                out.append({k: _jsonsafe(v) for k, v in rec.data().items()})
            return out

    def run_write_cypher(self, cypher: str) -> list[dict]:
        """Execute a write Cypher (MERGE/CREATE/SET/DELETE/APOC).

        Used by the /ask agent when the user explicitly asks to mutate the graph
        (e.g. "merge HR and HR Team"). Hard-blocks destructive admin ops; all
        normal data mutations are permitted.
        """
        lowered = cypher.lower()
        forbidden_admin = (
            "drop constraint", "drop index", "drop database",
            "load csv", "call dbms.", "call db.drop",
        )
        for tok in forbidden_admin:
            if tok in lowered:
                raise ValueError(f"Forbidden admin op: {tok}")
        with self._driver.session(database=self._db) as s:
            out = []
            for rec in s.run(cypher):
                out.append({k: _jsonsafe(v) for k, v in rec.data().items()})
            return out
