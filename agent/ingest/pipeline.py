"""
CMDB Agent — Ingest pipeline.

Ties the stages together:  parse -> normalize -> resolve identity -> emit graph ops.

The output is a GraphBatch (lists of node and edge upserts) expressed as plain
dicts. This keeps the pipeline pure and unit-testable without a live database;
storage/graph.py turns the ops into Cypher MERGEs. Re-ingesting a file is
idempotent because every op is a MERGE on a stable key.
"""
from __future__ import annotations

from typing import Any, Optional

from ingest import parsers, normalize as N
from ingest.resolve import UserResolver


# Source precedence: when sources disagree on a scalar field, the higher-priority
# source wins. Enforced by writing sources in ascending priority order — because
# node props are null-stripped, a later (higher) source overwrites set fields while
# a sparse source only fills gaps. yaml (richest) > csv > json (sparsest); the SaaS
# sources are authoritative for their own entity type.
SOURCE_PRIORITY = {
    "hardware_json": 1,
    "hardware_csv": 2,
    "hardware_yaml": 3,
    "okta": 3,
    "app_inventory": 3,
    "unknown": 0,
}


def ordering_key(filename: str, text: str) -> int:
    """Priority for a file, so callers can sort ingest order (ascending)."""
    return SOURCE_PRIORITY.get(parsers.detect_source(filename, text), 2)


# Map an intermediate rel target_type to a (label, key_field, key_value) tuple.
# Team/Location names are canonicalized so "HR" + "HR Team" collapse to one
# node, and "New York HQ" + "New York HQ - Floor 15" collapse to one location.
def _dim_target(target_type: str, target: dict) -> Optional[tuple[str, str, str]]:
    if target_type == "location":
        canon = N.normalize_location(target["name"])
        return ("Location", "name", canon) if canon else None
    if target_type == "department":
        canon = N.normalize_team(target["name"])  # same suffix rules apply
        return ("Department", "name", canon) if canon else None
    if target_type == "team":
        canon = N.normalize_team(target["name"])
        return ("Team", "name", canon) if canon else None
    if target_type == "app":
        return ("App", "name_norm", N.norm_key(target["name"]))
    return None


class GraphBatch:
    def __init__(self):
        self.nodes: list[dict] = []
        self.edges: list[dict] = []

    def add_node(self, label, key_field, key_value, props, source):
        if not key_value:
            return
        clean = {k: v for k, v in props.items() if v is not None and v != ""}
        self.nodes.append({
            "label": label, "key_field": key_field, "key_value": key_value,
            "props": clean, "source": source,
        })

    def add_edge(self, etype, frm, to, source):
        if not frm or not to or not frm[2] or not to[2]:
            return
        self.edges.append({"type": etype, "from": frm, "to": to, "source": source})

    @property
    def node_keys(self) -> set:
        return {(n["label"], n["key_value"]) for n in self.nodes}


def build_batch(records: list[dict], resolver: UserResolver) -> GraphBatch:
    batch = GraphBatch()
    for rec in records:
        rtype = rec["type"]
        f = rec["fields"]
        src = rec["source"]

        if rtype == "device":
            _emit_device(batch, f, rec.get("rels", []), src, resolver)
        elif rtype == "user":
            _emit_user(batch, f, rec.get("rels", []), src, resolver)
        elif rtype == "app":
            _emit_app(batch, f, rec.get("rels", []), src)
    return batch


def _emit_device(batch, f, rels, src, resolver: UserResolver):
    os_name, os_ver = N.normalize_os(f.get("os"))
    if not os_ver and f.get("os_version"):
        os_ver = f.get("os_version")
    raw_loc = f.get("location")
    loc_details = N.parse_location_detail(raw_loc)
    props = {
        "device_id": f.get("device_id"),
        "hostname": f.get("hostname"),
        "ip_address": f.get("ip_address"),
        "mac_address": f.get("mac_address"),
        "os": os_name,
        "os_version": os_ver,
        "status": N.normalize_status(f.get("status")),
        "encryption": N.normalize_encryption(f.get("encryption")),
        "encryption_type": f.get("encryption_type"),
        "device_type": f.get("device_type"),
        "serial_number": f.get("serial_number"),
        "manufacturer": f.get("manufacturer"),
        "model": f.get("model"),
        "location": N.normalize_location(raw_loc),    # canonical (merge key)
        "location_raw": raw_loc,                       # original string for audit
        "floor": loc_details.get("floor"),
        "suite": loc_details.get("suite"),
        "wing": loc_details.get("wing"),
        "building": loc_details.get("building"),
        "department": N.normalize_team(f.get("department")),
        "assigned_user": N.normalize_name(f.get("assigned_user")),
        "last_checkin": f.get("last_checkin"),
    }
    did = f.get("device_id")
    batch.add_node("Device", "device_id", did, props, src)
    device_ref = ("Device", "device_id", did)

    for rel in rels:
        if rel["type"] == "ASSIGNED_TO":
            t = rel["target"]
            uid, _ = resolver.resolve(t.get("name"), t.get("email"), t.get("employee_id"))
            batch.add_node("User", "uid", uid, {
                "uid": uid, "name": N.normalize_name(t.get("name")),
                "email": N.normalize_email(t.get("email")),
                "employee_id": t.get("employee_id"),
            }, src)
            batch.add_edge("ASSIGNED_TO", device_ref, ("User", "uid", uid), src)
        else:
            tgt = _dim_target(rel["target_type"], rel["target"])
            if tgt:
                node_props = {tgt[1]: tgt[2]}
                # Enrich Location with type + parsed sub-details so each node
                # has structured city/type and aggregates every floor/suite seen.
                if rel["target_type"] == "location":
                    raw = rel["target"].get("name")
                    loc_type = N.parse_location_type(raw)
                    if loc_type:
                        # UNION-merged list — same city legitimately has multiple
                        # types (e.g. San Francisco has an Office AND a DC).
                        node_props["types"] = [loc_type]
                    for k, v in N.parse_location_detail(raw).items():
                        # singular -> plural list (floor -> floors)
                        node_props[f"{k}s"] = [v]
                batch.add_node(tgt[0], tgt[1], tgt[2], node_props, src)
                batch.add_edge(rel["type"], device_ref, tgt, src)


def _emit_user(batch, f, rels, src, resolver: UserResolver):
    uid, _ = resolver.resolve(f.get("name"), f.get("email"), f.get("employee_id"))
    props = {
        "uid": uid,
        "name": N.normalize_name(f.get("name")),
        "email": N.normalize_email(f.get("email")),
        "employee_id": f.get("employee_id"),
        "department": N.normalize_team(f.get("department")),
        "team": N.normalize_team(f.get("team")),
        "title": f.get("title"),
        "mfa_enabled": N.normalize_bool(f.get("mfa_enabled")),
        "last_login": f.get("last_login"),
        "status": N.normalize_status(f.get("status")),
        "groups": f.get("groups") or None,
        "apps": f.get("apps") or None,
    }
    batch.add_node("User", "uid", uid, props, src)
    user_ref = ("User", "uid", uid)

    for rel in rels:
        if rel["target_type"] == "app":
            name = rel["target"]["name"]
            nk = N.norm_key(name)
            stub_props = {"name_norm": nk, "name": name, "is_stub": True}
            cats = N.parse_app_categories(name)
            if cats:
                stub_props["categories"] = cats
            batch.add_node("App", "name_norm", nk, stub_props, src)
            batch.add_edge(rel["type"], user_ref, ("App", "name_norm", nk), src)
        else:
            tgt = _dim_target(rel["target_type"], rel["target"])
            if tgt:
                batch.add_node(tgt[0], tgt[1], tgt[2], {tgt[1]: tgt[2]}, src)
                batch.add_edge(rel["type"], user_ref, tgt, src)


def _emit_app(batch, f, rels, src):
    name = f.get("name")
    nk = N.norm_key(name)
    cats = N.parse_app_categories(name)
    props = {
        "name_norm": nk,
        "name": name,
        "app_id": f.get("app_id"),
        "vendor": f.get("vendor"),
        "app_type": f.get("app_type"),
        "category": f.get("category"),
        "categories": cats or None,
        "deployment": f.get("deployment"),
        "owner": f.get("owner"),
        "users_count": N.to_int(f.get("users_count")),
        "sso_enabled": N.normalize_bool(f.get("sso_enabled")),
        "annual_cost_usd": N.to_float(f.get("annual_cost_usd")),
        "integrations": f.get("integrations") or None,
        "is_stub": False,
    }
    batch.add_node("App", "name_norm", nk, props, src)
    app_ref = ("App", "name_norm", nk)

    for rel in rels:
        if rel["target_type"] == "app":
            other = rel["target"]["name"]
            onk = N.norm_key(other)
            batch.add_node("App", "name_norm", onk,
                           {"name_norm": onk, "name": other, "is_stub": True}, src)
            batch.add_edge(rel["type"], app_ref, ("App", "name_norm", onk), src)
        else:
            tgt = _dim_target(rel["target_type"], rel["target"])
            if tgt:
                batch.add_node(tgt[0], tgt[1], tgt[2], {tgt[1]: tgt[2]}, src)
                batch.add_edge(rel["type"], app_ref, tgt, src)


def parse_and_build(filename: str, text: str, resolver: UserResolver) -> tuple[str, GraphBatch]:
    source_type, records = parsers.parse(filename, text)
    return source_type, build_batch(records, resolver)
