"""
End-to-end test of the full ingest -> graph -> query flow against the in-memory
backend (no Neo4j needed). This exercises the real parsers, normalization, identity
resolution, source-precedence ordering, and graph writes, then asserts that the
stored graph returns the CORRECT answers to real CMDB questions.

The only thing NOT covered here is the Neo4j Cypher engine and the LLM in /ask —
those are exercised by test_e2e_live.py against real services.
"""
import os

import pytest

from service import ingest_texts
from storage.memory import InMemoryGraphStore
from ingest.normalize import norm_key

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "input_data", "backend")
FILES = ["sample_hardware.csv", "sample_hardware.json", "sample_hardware.yaml",
         "sample_okta.json", "sample_app.json"]


@pytest.fixture(scope="module")
def store():
    s = InMemoryGraphStore()
    items = []
    for fn in FILES:
        with open(os.path.join(DATA, fn), encoding="utf-8") as f:
            items.append((fn, f.read()))
    results = ingest_texts(s, items)
    assert all(r.detected != "unknown" for r in results)
    return s


def test_ci_counts(store):
    assert len(store.list_label("Device")) == 3      # deduped across 3 files
    assert len(store.list_label("User")) == 9        # John D./John Doe merged
    apps = {a["name_norm"] for a in store.list_label("App")}
    assert "slack" in apps and "github" in apps


def test_device_merge_precedence_and_edges(store):
    ci = store.get_ci("C-19283")
    assert ci is not None
    dev = ci["ci"]
    assert dev["os"] == "macOS"            # normalized from 3 spellings
    assert dev["status"] == "inactive"     # yaml precedence over active
    assert dev["location"] == "London"     # yaml precedence
    assert any(r["rel"] == "ASSIGNED_TO" for r in ci["relationships"])


def test_single_location_edge_after_conflict(store):
    # csv/yaml say London, json says New York HQ -> exactly ONE LOCATED_AT, London
    locs = store.neighbors("Device", "C-19283", rel="LOCATED_AT", direction="out")
    assert [l["name"] for l in locs] == ["London"]


def test_last_checkin_is_the_max(store):
    # csv 07-22, json 06-12, yaml 07-23 -> keep the most recent
    dev = store.get_ci("C-19283")["ci"]
    assert dev["last_checkin"] == "2024-07-23T13:45:00Z"


def test_ci_lookup_by_hostname(store):
    ci = store.get_ci("laptop-jdoe")       # not the device_id, a secondary field
    assert ci is not None and ci["ci"]["device_id"] == "C-19283"


def test_users_without_mfa_is_correct(store):
    no_mfa = sorted(
        u.get("name") for u in store.list_label("User")
        if not u.get("mfa_enabled")
    )
    assert no_mfa == ["Alex Johnson", "Carlos S.", "Michael Brown"]


def test_slack_users_is_correct(store):
    slack_users = 0
    for u in store.list_label("User"):
        apps = store.neighbors("User", u["uid"], rel="USES", direction="out")
        if any(a.get("name_norm") == "slack" for a in apps):
            slack_users += 1
    assert slack_users == 6   # matches the Okta source of truth


def test_john_doe_resolution_and_apps(store):
    johns = [u for u in store.list_label("User")
             if (u.get("name") or "").lower().startswith("john d")]
    assert len(johns) == 1                 # "John D." and "John Doe" are one node
    john = johns[0]
    app_keys = {a.get("name_norm") for a in
                store.neighbors("User", john["uid"], rel="USES", direction="out")}
    assert {"slack", "github"} <= app_keys
