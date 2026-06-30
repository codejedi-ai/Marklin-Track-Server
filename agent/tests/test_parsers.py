import os

from ingest import parsers

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "input_data", "backend")


def _read(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return f.read()


def test_source_detection():
    assert parsers.detect_source("sample_hardware.csv", _read("sample_hardware.csv")) == "hardware_csv"
    assert parsers.detect_source("sample_hardware.json", _read("sample_hardware.json")) == "hardware_json"
    assert parsers.detect_source("sample_hardware.yaml", _read("sample_hardware.yaml")) == "hardware_yaml"
    assert parsers.detect_source("sample_okta.json", _read("sample_okta.json")) == "okta"
    assert parsers.detect_source("sample_app.json", _read("sample_app.json")) == "app_inventory"


def test_yaml_nested_extraction():
    _, recs = parsers.parse("sample_hardware.yaml", _read("sample_hardware.yaml"))
    devices = [r for r in recs if r["type"] == "device"]
    c19283 = next(d for d in devices if d["fields"]["device_id"] == "C-19283")
    # deeply nested fields are flattened correctly
    assert c19283["fields"]["mac_address"] == "AA:BB:CC:DD:11:22"
    assert c19283["fields"]["manufacturer"] == "Apple"
    assert any(r["type"] == "user" for r in recs)  # rich user emitted from YAML


def test_okta_user_app_edges():
    _, recs = parsers.parse("sample_okta.json", _read("sample_okta.json"))
    assert all(r["type"] == "user" for r in recs)
    uses = [rel for r in recs for rel in r["rels"] if rel["type"] == "USES"]
    assert len(uses) > 0
