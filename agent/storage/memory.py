"""
CMDB Agent — In-memory graph store.

A dependency-free implementation of the same interface as storage.graph.GraphStore,
backed by plain dicts/sets. It reproduces the MERGE semantics (dedup by key,
null-stripped property merge, idempotent edges) so the structured endpoints and the
full ingest pipeline can run and be tested without a live Neo4j.

Used when STORE_BACKEND=memory. It has no Cypher engine, so /ask (text->Cypher)
requires the real Neo4j backend.
"""
from __future__ import annotations

from typing import Optional

from relations import LIST_MERGE_PROPS, SINGLE_VALUED_RELS

_ID_FIELDS = ("device_id", "uid", "app_id", "hostname", "name_norm", "email")


class InMemoryGraphStore:
    def __init__(self):
        # (label, key_value) -> props dict
        self.nodes: dict[tuple[str, str], dict] = {}
        # set of (rel_type, (fl,fk,fv), (tl,tk,tv))
        self.edges: set[tuple] = set()

    # --- lifecycle (no-ops) ----------------------------------------------
    def verify(self) -> bool:
        return True

    def apply_schema(self) -> None:
        pass

    def close(self) -> None:
        pass

    # --- writes -----------------------------------------------------------
    def write_batch(self, batch) -> tuple[int, int]:
        for n in batch.nodes:
            key = (n["label"], n["key_value"])
            node = self.nodes.setdefault(key, {"_sources": []})
            if n["source"] not in node["_sources"]:
                node["_sources"].append(n["source"])
            props = dict(n["props"])  # already null-stripped
            last_checkin = props.pop("last_checkin", None)
            # List-merge props (floors, suites, …) UNION instead of overwrite,
            # so a Location aggregates every sub-detail seen across sources.
            for lk in list(props):
                if lk not in LIST_MERGE_PROPS:
                    continue
                new_vals = props.pop(lk)
                if not isinstance(new_vals, list):
                    new_vals = [new_vals]
                existing = node.get(lk) or []
                seen = set(existing)
                for v in new_vals:
                    if v not in seen:
                        existing.append(v)
                        seen.add(v)
                node[lk] = existing
            node.update(props)        # later (higher-priority) source wins
            # last_checkin: keep the most recent, regardless of source priority
            if last_checkin is not None and (
                node.get("last_checkin") is None or node["last_checkin"] < last_checkin
            ):
                node["last_checkin"] = last_checkin
        for e in batch.edges:
            etype, frm, to = e["type"], tuple(e["from"]), tuple(e["to"])
            if etype in SINGLE_VALUED_RELS:
                # replace any existing edge of this type from the same source node
                self.edges = {ed for ed in self.edges
                              if not (ed[0] == etype and ed[1] == frm)}
            self.edges.add((etype, frm, to))
        return len(batch.node_keys), len(batch.edges)

    # --- reads ------------------------------------------------------------
    def list_label(self, label: str) -> list[dict]:
        return [dict(p) for (l, _), p in self.nodes.items() if l == label]

    def _locate(self, identifier: str) -> Optional[tuple[str, str]]:
        ident = identifier
        low = identifier.lower()
        for (label, key), props in self.nodes.items():
            if key == ident:
                return (label, key)
            for f in _ID_FIELDS:
                v = props.get(f)
                if v is None:
                    continue
                if f in ("name_norm", "email"):
                    if str(v).lower() == low:
                        return (label, key)
                elif str(v) == ident:
                    return (label, key)
        return None

    def get_ci(self, identifier: str) -> Optional[dict]:
        loc = self._locate(identifier)
        if loc is None:
            return None
        label, key = loc
        neighbors = []
        for rel, frm, to in self.edges:
            if (frm[0], frm[2]) == (label, key):
                tnode = self.nodes.get((to[0], to[2]))
                if tnode is not None:
                    neighbors.append({"rel": rel, "direction": "out", "node": dict(tnode)})
            elif (to[0], to[2]) == (label, key):
                fnode = self.nodes.get((frm[0], frm[2]))
                if fnode is not None:
                    neighbors.append({"rel": rel, "direction": "in", "node": dict(fnode)})
        return {"ci": dict(self.nodes[loc]), "relationships": neighbors}

    def all_users_min(self) -> list[dict]:
        out = []
        for (label, _), p in self.nodes.items():
            if label == "User":
                out.append({"uid": p.get("uid"), "name": p.get("name"),
                            "email": p.get("email"), "employee_id": p.get("employee_id")})
        return out

    def graph_summary(self) -> dict:
        """CMDB topology as {nodes, edges} for visualization (Tickets excluded)."""
        nodes = []
        for (label, key), props in self.nodes.items():
            if label == "Ticket":
                continue
            display = (props.get("name") or props.get("hostname") or props.get("email")
                       or props.get("device_id") or props.get("app_id") or key)
            nodes.append({
                "id": f"{label}:{key}", "label": label,
                "display": display, "props": dict(props),
            })
        edges = []
        for rel, frm, to in self.edges:
            if frm[0] == "Ticket" or to[0] == "Ticket":
                continue
            edges.append({
                "source": f"{frm[0]}:{frm[2]}",
                "target": f"{to[0]}:{to[2]}",
                "type": rel,
            })
        return {"nodes": nodes, "edges": edges}

    def run_read_cypher(self, cypher: str):
        raise NotImplementedError(
            "In-memory backend has no Cypher engine. Use STORE_BACKEND=neo4j for /ask."
        )

    # --- tickets (topology only; file store owns the records) -------------
    def link_ticket(self, ticket: dict) -> None:
        key = ("Ticket", ticket["id"])
        self.nodes[key] = {
            "id": ticket["id"], "title": ticket.get("title"),
            "status": ticket.get("status"), "priority": ticket.get("priority"),
            "category": ticket.get("category"), "tags": ticket.get("tags") or [],
            "email": ticket.get("email"), "_sources": ["tickets"],
        }
        for ref in ticket.get("related_cis", []):
            ident = ref.get("id") or ref.get("identifier")
            loc = self._locate(str(ident)) if ident else None
            if loc:
                self.edges.add(("ABOUT", ("Ticket", "id", ticket["id"]),
                                (loc[0], "_", loc[1])))

    def update_ticket_status(self, ticket_id: str, status: str) -> None:
        node = self.nodes.get(("Ticket", ticket_id))
        if node:
            node["status"] = status

    def tickets_about(self, identifier: str) -> list[dict]:
        loc = self._locate(identifier)
        if loc is None:
            return []
        out = []
        for rel, frm, to in self.edges:
            if rel == "ABOUT" and (to[0], to[2]) == (loc[0], loc[1]):
                t = self.nodes.get(("Ticket", frm[2]))
                if t:
                    out.append({"id": t["id"], "title": t.get("title"),
                                "status": t.get("status")})
        return out

    # --- convenience for tests / traversal -------------------------------
    def neighbors(self, label: str, key: str, rel: str = None, direction: str = "out"):
        out = []
        for r, frm, to in self.edges:
            if rel and r != rel:
                continue
            if direction == "out" and (frm[0], frm[2]) == (label, key):
                out.append(self.nodes.get((to[0], to[2])))
            elif direction == "in" and (to[0], to[2]) == (label, key):
                out.append(self.nodes.get((frm[0], frm[2])))
        return [n for n in out if n is not None]
