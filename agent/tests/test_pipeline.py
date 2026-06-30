import os

from ingest.pipeline import parse_and_build, ordering_key
from ingest.resolve import UserResolver

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "input_data", "backend")
FILES = ["sample_hardware.csv", "sample_hardware.json", "sample_hardware.yaml",
         "sample_okta.json", "sample_app.json"]


def _ingest_all():
    resolver = UserResolver()
    nodes, edges = [], []
    for fn in FILES:
        with open(os.path.join(DATA, fn), encoding="utf-8") as f:
            _, batch = parse_and_build(fn, f.read(), resolver)
        nodes += batch.nodes
        edges += batch.edges
    return nodes, edges


def test_device_dedup_across_three_files():
    nodes, _ = _ingest_all()
    devices = {n["key_value"] for n in nodes if n["label"] == "Device"}
    # 3 unique devices despite appearing in csv + json + yaml
    assert devices == {"C-19283", "D-10005", "HW-2024-003"}


def test_os_normalized_consistently():
    nodes, _ = _ingest_all()
    os_vals = {n["props"].get("os") for n in nodes
               if n["label"] == "Device" and n["key_value"] == "C-19283"}
    assert os_vals == {"macOS"}  # macOS Ventura / macos / macOS all collapse


def test_john_identity_resolution():
    nodes, _ = _ingest_all()
    # "John D." (csv/json) and "John Doe" (yaml/okta) -> one uid
    john_uids = {n["key_value"] for n in nodes if n["label"] == "User"
                 and (n["props"].get("name") or "").lower().startswith("john d")}
    assert len(john_uids) == 1


def test_relationships_present():
    _, edges = _ingest_all()
    types = {e["type"] for e in edges}
    assert {"ASSIGNED_TO", "USES", "INTEGRATES_WITH", "LOCATED_AT"} <= types


def _effective_device_props(device_id):
    """Replay node ops in source-priority order, folding null-stripped props
    (mimics Neo4j `n += $props`), to compute the final stored device."""
    texts = []
    for fn in FILES:
        with open(os.path.join(DATA, fn), encoding="utf-8") as f:
            texts.append((fn, f.read()))
    texts.sort(key=lambda it: ordering_key(it[0], it[1]))
    resolver = UserResolver()
    merged = {}
    for fn, text in texts:
        _, batch = parse_and_build(fn, text, resolver)
        for n in batch.nodes:
            if n["label"] == "Device" and n["key_value"] == device_id:
                merged.update(n["props"])  # later (higher-priority) overwrites
    return merged


def test_precedence_yaml_wins_on_conflict():
    # C-19283: status active(csv/json) vs deactivated->inactive(yaml);
    # location New York HQ(json) vs London(csv/yaml). YAML has highest priority.
    dev = _effective_device_props("C-19283")
    assert dev["status"] == "inactive"      # yaml wins
    assert dev["location"] == "London"      # yaml wins
    assert dev["manufacturer"] == "Apple"   # gap filled only by yaml
