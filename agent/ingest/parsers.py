"""
CMDB Agent — Source parsers.

Each source has a different shape. Parsers do the *structural* work: detect the
source type and map its idiosyncratic layout (flat CSV, sparse JSON, deeply
nested YAML, Okta arrays, app inventory) into a uniform list of IntermediateRecord
dicts. Value normalization and identity resolution happen later in pipeline.py.

IntermediateRecord shape:
{
  "type":   "device" | "user" | "app",
  "fields": { canonical_field_name: raw_value, ... },
  "rels":   [ {"type": "ASSIGNED_TO", "target_type": "user", "target": {...}}, ... ],
  "source": "<filename>",
}
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Source detection
# ---------------------------------------------------------------------------

def detect_source(filename: str, text: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return "hardware_csv"
    if name.endswith((".yaml", ".yml")):
        return "hardware_yaml"
    if name.endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return "unknown"
        if isinstance(data, dict) and "applications" in data:
            return "app_inventory"
        if isinstance(data, list) and data:
            first = data[0]
            if "user_id" in first or "mfa_enabled" in first:
                return "okta"
            if "device_id" in first:
                return "hardware_json"
    # content sniff fallback
    stripped = text.lstrip()
    if stripped.startswith("device_id,"):
        return "hardware_csv"
    return "unknown"


def parse(filename: str, text: str) -> tuple[str, list[dict[str, Any]]]:
    """Detect the source type and return (source_type, [IntermediateRecord])."""
    source_type = detect_source(filename, text)
    fn = {
        "hardware_csv": _parse_hardware_csv,
        "hardware_json": _parse_hardware_json,
        "hardware_yaml": _parse_hardware_yaml,
        "okta": _parse_okta,
        "app_inventory": _parse_app_inventory,
    }.get(source_type)
    if fn is None:
        return source_type, []
    return source_type, fn(filename, text)


# ---------------------------------------------------------------------------
# Device sources
# ---------------------------------------------------------------------------

def _device_rels(name, email, employee_id, location, department) -> list[dict]:
    rels = []
    if name:
        rels.append({
            "type": "ASSIGNED_TO", "target_type": "user",
            "target": {"name": name, "email": email, "employee_id": employee_id},
        })
    if location:
        rels.append({"type": "LOCATED_AT", "target_type": "location",
                     "target": {"name": location}})
    if department:
        rels.append({"type": "BELONGS_TO", "target_type": "department",
                     "target": {"name": department}})
    return rels


def _parse_hardware_csv(filename: str, text: str) -> list[dict]:
    records = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        fields = {
            "device_id": row.get("device_id"),
            "hostname": row.get("hostname"),
            "ip_address": row.get("ip_address"),
            "mac_address": row.get("mac_address"),
            "os": row.get("os"),
            "status": row.get("status"),
            "encryption": row.get("encryption_status"),
            "encryption_type": row.get("encryption_status"),
            "device_type": row.get("device_type"),
            "serial_number": row.get("serial_number"),
            "location": row.get("location"),
            "department": row.get("department"),
            "assigned_user": row.get("assigned_to"),
            "last_checkin": row.get("last_checkin"),
        }
        records.append({
            "type": "device", "fields": fields, "source": filename,
            "rels": _device_rels(row.get("assigned_to"), None, None,
                                  row.get("location"), row.get("department")),
        })
    return records


def _parse_hardware_json(filename: str, text: str) -> list[dict]:
    records = []
    for row in json.loads(text):
        fields = {
            "device_id": row.get("device_id"),
            "hostname": row.get("hostname"),
            "ip_address": row.get("ip_address"),
            "os": row.get("os"),
            "status": row.get("status"),
            "location": row.get("location"),
            "assigned_user": row.get("assigned_to"),
            "last_checkin": row.get("last_checkin"),
        }
        records.append({
            "type": "device", "fields": fields, "source": filename,
            "rels": _device_rels(row.get("assigned_to"), None, None,
                                  row.get("location"), None),
        })
    return records


def _parse_hardware_yaml(filename: str, text: str) -> list[dict]:
    doc = yaml.safe_load(text) or {}
    devices = (doc.get("inventory", {}) or {}).get("devices", []) or []
    records = []
    for dev in devices:
        assigned = dev.get("assigned_to", {}) or {}
        hw = dev.get("hardware", {}) or {}
        net = dev.get("network", {}) or {}
        os_info = dev.get("operating_system", {}) or {}
        sec = dev.get("security", {}) or {}
        loc = (dev.get("location", {}) or {}).get("site")
        status = (dev.get("status", {}) or {}).get("operational_status")
        last_checkin = (dev.get("status", {}) or {}).get("last_checkin")
        department = assigned.get("department")

        os_name = os_info.get("name")
        os_version = os_info.get("version")
        os_combined = f"{os_name} {os_version}".strip() if os_name else None

        fields = {
            "device_id": dev.get("device_id"),
            "hostname": dev.get("hostname"),
            "ip_address": net.get("primary_ip"),
            "mac_address": net.get("mac_address"),
            "os": os_combined,
            "os_version": os_version,
            "status": status,
            "encryption": sec.get("encryption_enabled"),
            "encryption_type": sec.get("encryption_type"),
            "device_type": dev.get("type"),
            "serial_number": hw.get("serial_number"),
            "manufacturer": hw.get("manufacturer"),
            "model": hw.get("model"),
            "location": loc,
            "department": department,
            "assigned_user": assigned.get("name"),
            "last_checkin": last_checkin,
        }
        rels = _device_rels(assigned.get("name"), assigned.get("email"),
                            assigned.get("employee_id"), loc, department)
        if assigned.get("team"):
            rels.append({"type": "MEMBER_OF", "target_type": "team",
                         "target": {"name": assigned.get("team")}})
        records.append({"type": "device", "fields": fields,
                        "source": filename, "rels": rels})

        # YAML carries a rich user — emit a User record too so we capture
        # employee_id / team / title that no other source has.
        if assigned.get("name"):
            records.append({
                "type": "user", "source": filename,
                "fields": {
                    "name": assigned.get("name"),
                    "email": assigned.get("email"),
                    "employee_id": assigned.get("employee_id"),
                    "department": assigned.get("department"),
                    "team": assigned.get("team"),
                    "title": assigned.get("title"),
                },
                "rels": [],
            })
    return records


# ---------------------------------------------------------------------------
# SaaS sources
# ---------------------------------------------------------------------------

def _parse_okta(filename: str, text: str) -> list[dict]:
    records = []
    for u in json.loads(text):
        fields = {
            "name": u.get("name"),
            "email": u.get("email"),
            "mfa_enabled": u.get("mfa_enabled"),
            "last_login": u.get("last_login"),
            "status": u.get("status"),
            "groups": u.get("groups", []),
            "apps": u.get("apps", []),
        }
        rels = []
        for app_name in u.get("apps", []) or []:
            rels.append({"type": "USES", "target_type": "app",
                         "target": {"name": app_name}})
        for grp in u.get("groups", []) or []:
            rels.append({"type": "MEMBER_OF", "target_type": "team",
                         "target": {"name": grp}})
        records.append({"type": "user", "fields": fields,
                        "source": filename, "rels": rels})
    return records


def _parse_app_inventory(filename: str, text: str) -> list[dict]:
    data = json.loads(text)
    records = []
    for app in data.get("applications", []) or []:
        fields = {
            "name": app.get("name"),
            "app_id": app.get("app_id"),
            "vendor": app.get("vendor"),
            "app_type": app.get("app_type"),
            "category": app.get("category"),
            "deployment": app.get("deployment"),
            "owner": app.get("owner"),
            "users_count": app.get("users_count"),
            "sso_enabled": app.get("sso_enabled"),
            "annual_cost_usd": app.get("annual_cost_usd"),
            "integrations": app.get("integrations", []),
        }
        rels = []
        for other in app.get("integrations", []) or []:
            rels.append({"type": "INTEGRATES_WITH", "target_type": "app",
                         "target": {"name": other}})
        if app.get("owner"):
            rels.append({"type": "OWNED_BY", "target_type": "team",
                         "target": {"name": app.get("owner")}})
        records.append({"type": "app", "fields": fields,
                        "source": filename, "rels": rels})
    return records
