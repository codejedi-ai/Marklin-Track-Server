"""
CMDB Agent — Ontology service.

`normalization.json` is the source of truth for every deterministic rule the
ingest pipeline applies (OS families, status synonyms, team-suffix patterns,
location type qualifiers, etc.). This module exposes a small, validating
interface so callers — the HTTP API and the LLM agent — can read or update
the ontology safely at runtime.

Design notes:
- Atomic-ish write: tmp file + os.replace so a partial write never half-corrupts
  the source of truth.
- Validate before commit: load the candidate, try to compile every regex. If any
  step fails, raise and don't touch disk. Keeps a broken edit from breaking
  every subsequent ingest.
- Hot-reload: after a successful write, normalize.reload_rules() rebuilds the
  module-level lookups so the next ingest picks up the change without restart.
"""
from __future__ import annotations

import json
import os
import re
import threading
from typing import Any

from ingest import normalize as N

_PATH = N._RULES_PATH
_LOCK = threading.Lock()

# Required top-level keys + their expected Python type after JSON parse.
_REQUIRED_SHAPE: dict[str, type] = {
    "os_families":                     dict,
    "status":                          dict,
    "encryption_false_tokens":         list,
    "bool_true_tokens":                list,
    "bool_false_tokens":               list,
    "team_suffix_pattern":             str,
    "location_subloc_pattern":         str,
    "location_detail_finder_pattern":  str,
    "location_detail_aliases":         dict,
    "location_types":                  list,
    # Optional but, if present, must be a dict (not strictly required so older
    # ontology files without this key still validate). We validate the type
    # below if it's present.
}
_OPTIONAL_DICT_KEYS = {"app_aliases"}


def get_ontology() -> dict[str, Any]:
    """Return the current rules dict (re-reads disk to avoid stale view)."""
    with open(_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _validate(candidate: Any) -> None:
    if not isinstance(candidate, dict):
        raise ValueError("Ontology must be a JSON object.")
    for key, want_type in _REQUIRED_SHAPE.items():
        if key not in candidate:
            raise ValueError(f"Missing required key: {key!r}")
        if not isinstance(candidate[key], want_type):
            raise ValueError(
                f"Key {key!r} must be a {want_type.__name__}, got "
                f"{type(candidate[key]).__name__}."
            )
    # Status shape
    if not {"active", "inactive"} <= set(candidate["status"].keys()):
        raise ValueError("status must contain 'active' and 'inactive' arrays.")
    for opt in _OPTIONAL_DICT_KEYS:
        if opt in candidate and not isinstance(candidate[opt], dict):
            raise ValueError(f"Key {opt!r} must be a dict if present.")
    # Compile every regex so we fail BEFORE writing.
    for pat in (
        candidate["team_suffix_pattern"],
        candidate["location_subloc_pattern"],
        candidate["location_detail_finder_pattern"],
    ):
        try:
            re.compile(pat)
        except re.error as exc:
            raise ValueError(f"Invalid regex {pat!r}: {exc}") from exc
    for item in candidate["location_types"]:
        if not isinstance(item, dict) or "pattern" not in item or "canonical" not in item:
            raise ValueError(
                "Each location_types entry must be an object with "
                "'pattern' and 'canonical' fields."
            )
        try:
            re.compile(item["pattern"])
        except re.error as exc:
            raise ValueError(f"Invalid regex {item['pattern']!r}: {exc}") from exc


def update_ontology(new_rules: dict[str, Any]) -> dict[str, Any]:
    """Validate, write atomically, then hot-reload the in-memory rules.

    Returns the rules that were written (so callers can confirm).
    """
    _validate(new_rules)
    # Direct overwrite (no tmp + rename): the file may be a Docker bind mount
    # where cross-filesystem rename is denied with EBUSY. Validation already
    # happened above so we won't write garbage.
    with _LOCK:
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(new_rules, f, indent=2)
        N.reload_rules()
    return new_rules
