"""
End-to-end test through the real FastAPI app (HTTP layer included), using the
in-memory backend so no Neo4j is required. Skipped if FastAPI isn't installed.

Run:  pip install fastapi httpx pytest && pytest tests/test_e2e_api.py
"""
import os

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    os.environ["STORE_BACKEND"] = "memory"
    # import after env is set so settings pick up the memory backend
    import importlib
    import config
    importlib.reload(config)
    import main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def test_ingest_samples_then_query(client):
    r = client.post("/ingest/samples")
    assert r.status_code == 200
    types = {item["detected"] for item in r.json()}
    assert "hardware_yaml" in types and "okta" in types and "app_inventory" in types

    devices = client.get("/devices").json()
    assert len(devices) == 3

    users = client.get("/users").json()
    assert len(users) == 9


def test_ci_endpoint_reflects_precedence(client):
    client.post("/ingest/samples")
    ci = client.get("/ci/C-19283").json()
    assert ci["ci"]["status"] == "inactive"     # yaml precedence, end-to-end
    assert ci["ci"]["os"] == "macOS"
    assert any(r["rel"] == "ASSIGNED_TO" for r in ci["relationships"])


def test_ci_not_found(client):
    assert client.get("/ci/does-not-exist").status_code == 404
