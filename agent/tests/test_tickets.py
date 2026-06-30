"""
Tests for the ticket store and the CMDB-grounded suggestion engine (LLM disabled,
so this is deterministic and needs no network). Proves /api/ai/suggest returns the
RIGHT grounded triage for a known submitter.
"""
import os

import pytest

from storage.tickets import TicketStore
from storage.memory import InMemoryGraphStore
from service import ingest_texts
from ai.ticket_suggest import suggest

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "input_data", "backend")
FILES = ["sample_hardware.csv", "sample_hardware.json", "sample_hardware.yaml",
         "sample_okta.json", "sample_app.json"]


# --- ticket store CRUD ------------------------------------------------------
def test_ticket_store_crud(tmp_path):
    store = TicketStore(path=str(tmp_path / "tickets.json"))
    t = store.create({"title": "Test", "description": "d", "email": "a@b.com"})
    assert t["id"].startswith("TKT-") and t["status"] == "New"
    assert len(store.list()) == 1
    assert store.get(t["id"])["title"] == "Test"
    upd = store.update_status(t["id"], "In Progress")
    assert upd["status"] == "In Progress"
    with pytest.raises(ValueError):
        store.update_status(t["id"], "Bogus")
    assert store.update_status("nope", "Resolved") is None


# --- grounded suggestion ----------------------------------------------------
@pytest.fixture(scope="module")
def graph():
    s = InMemoryGraphStore()
    items = [(fn, open(os.path.join(DATA, fn), encoding="utf-8").read()) for fn in FILES]
    ingest_texts(s, items)
    return s


def test_suggest_is_cmdb_grounded(graph):
    # Carlos has MFA disabled (per Okta); a Slack access issue -> High + MFA tag
    out = suggest(graph, "Can't access Slack",
                  "I keep getting logged out of Slack and can't sign in.",
                  email="c.santos@example.com", use_llm=False)
    assert out["category"] == "Access"
    assert out["priority"] == "High"          # access issue + MFA disabled
    assert "MFA" in out["tags"]
    assert any(c["type"] == "user" for c in out["related_cis"])
    assert any(c.get("name") == "Slack" for c in out["related_cis"])
    assert out["grounded"] is True


def test_suggest_network_category(graph):
    out = suggest(graph, "VPN keeps timing out",
                  "The VPN connection times out every few minutes.",
                  email=None, use_llm=False)
    assert out["category"] == "Network"
    assert out["suggested_response"]          # always returns a response


def test_suggest_works_without_known_user(graph):
    out = suggest(graph, "Need software installed", "Please install Figma.",
                  email="unknown@nowhere.com", use_llm=False)
    assert out["category"] in {"Access", "Software"}  # Figma is a known app
    assert isinstance(out["tags"], list)
