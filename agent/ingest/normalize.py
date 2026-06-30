"""
CMDB Agent — Value normalization.

Turns the inconsistent raw strings across sources into canonical values so the
same real-world fact resolves to one value in the graph. This is the
deterministic cleaning layer; ambiguous identity decisions happen in resolve.py.

ALL rules live in `normalization.json` (next to this file) so they can be edited
without changing code. After editing the JSON, restart the api container.

Examples handled (all present in the sample data):
  os:         "macOS Ventura" / "macos" / "macOS Sonoma 14.5" -> ("macOS", "Sonoma 14.5")
  status:     "active" / "ACTIVE" / "deactivated"             -> "active" / "inactive"
  encryption: "FileVault Enabled" / "FileVault 2" / "LUKS..." -> True
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional


# --- Rules loaded from JSON -------------------------------------------------
_RULES_PATH = os.path.join(os.path.dirname(__file__), "normalization.json")


def _load_rules() -> dict:
    with open(_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_RULES = _load_rules()

# Materialized lookups (cheap to do once at import).
_OS_FAMILIES: dict[str, str] = _RULES["os_families"]
_ACTIVE: set[str] = set(_RULES["status"]["active"])
_INACTIVE: set[str] = set(_RULES["status"]["inactive"])
_ENCRYPTION_FALSE: set[str] = set(_RULES["encryption_false_tokens"])
_BOOL_TRUE: set[str] = set(_RULES["bool_true_tokens"])
_BOOL_FALSE: set[str] = set(_RULES["bool_false_tokens"])
_DETAIL_ALIASES: dict[str, str] = _RULES["location_detail_aliases"]
_APP_ALIASES: dict[str, str] = _RULES.get("app_aliases", {})
_APP_CATEGORIES_RAW: dict[str, list[str]] = _RULES.get("app_categories", {})
# Inverted for O(1) lookup: keyword -> list of categories that include it.
_APP_CATEGORY_INDEX: dict[str, list[str]] = {}
for _cat, _keywords in _APP_CATEGORIES_RAW.items():
    for _kw in _keywords:
        _APP_CATEGORY_INDEX.setdefault(_kw, []).append(_cat)

_TEAM_SUFFIX_RE = re.compile(_RULES["team_suffix_pattern"], re.IGNORECASE)
_LOC_SUBLOC_RE = re.compile(_RULES["location_subloc_pattern"], re.IGNORECASE)
_LOC_DETAIL_FINDER = re.compile(_RULES["location_detail_finder_pattern"], re.IGNORECASE)
_LOC_DETAIL_FINDER_REVERSE = re.compile(
    _RULES.get("location_detail_finder_reverse_pattern",
               r"\b(\d+(?:st|nd|rd|th)?|[A-Z]\d*)\s*(floor|fl|level|lvl|suite|wing|room|bldg|building)\b"),
    re.IGNORECASE,
)
_LOC_TYPE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(item["pattern"], re.IGNORECASE), item["canonical"])
    for item in _RULES["location_types"]
]


def reload_rules() -> None:
    """Re-read normalization.json and rebuild every cached lookup/regex.

    Lets you edit rules without restarting the process. Existing references to
    the module-level constants still see the new values because we mutate them
    in place rather than rebinding.
    """
    global _RULES, _OS_FAMILIES, _ACTIVE, _INACTIVE
    global _ENCRYPTION_FALSE, _BOOL_TRUE, _BOOL_FALSE, _DETAIL_ALIASES
    global _TEAM_SUFFIX_RE, _LOC_SUBLOC_RE, _LOC_DETAIL_FINDER, _LOC_TYPE_PATTERNS
    global _LOC_DETAIL_FINDER_REVERSE
    global _APP_ALIASES, _APP_CATEGORIES_RAW, _APP_CATEGORY_INDEX
    _RULES = _load_rules()
    _OS_FAMILIES = _RULES["os_families"]
    _ACTIVE = set(_RULES["status"]["active"])
    _INACTIVE = set(_RULES["status"]["inactive"])
    _ENCRYPTION_FALSE = set(_RULES["encryption_false_tokens"])
    _BOOL_TRUE = set(_RULES["bool_true_tokens"])
    _BOOL_FALSE = set(_RULES["bool_false_tokens"])
    _DETAIL_ALIASES = _RULES["location_detail_aliases"]
    _APP_ALIASES = _RULES.get("app_aliases", {})
    _APP_CATEGORIES_RAW = _RULES.get("app_categories", {})
    _APP_CATEGORY_INDEX = {}
    for cat, keywords in _APP_CATEGORIES_RAW.items():
        for kw in keywords:
            _APP_CATEGORY_INDEX.setdefault(kw, []).append(cat)
    _TEAM_SUFFIX_RE = re.compile(_RULES["team_suffix_pattern"], re.IGNORECASE)
    _LOC_SUBLOC_RE = re.compile(_RULES["location_subloc_pattern"], re.IGNORECASE)
    _LOC_DETAIL_FINDER = re.compile(_RULES["location_detail_finder_pattern"], re.IGNORECASE)
    _LOC_DETAIL_FINDER_REVERSE = re.compile(
        _RULES.get("location_detail_finder_reverse_pattern",
                   r"\b(\d+(?:st|nd|rd|th)?|[A-Z]\d*)\s*(floor|fl|level|lvl|suite|wing|room|bldg|building)\b"),
        re.IGNORECASE,
    )
    _LOC_TYPE_PATTERNS = [
        (re.compile(item["pattern"], re.IGNORECASE), item["canonical"])
        for item in _RULES["location_types"]
    ]


def normalize_os(raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Return (canonical_os_name, version_string_or_None)."""
    if not raw:
        return None, None
    text = str(raw).strip()
    low = text.lower()

    family = None
    for key, canon in _OS_FAMILIES.items():
        if low.startswith(key) or key in low:
            family = canon
            break

    # Strip the family token to leave the version remainder.
    version = None
    if family:
        remainder = re.sub(re.escape(family), "", text, flags=re.IGNORECASE).strip()
        remainder = remainder.strip(" -")
        version = remainder or None
    else:
        family = text  # unknown family: keep as-is

    return family, version


# --- Status -----------------------------------------------------------------
def normalize_status(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    low = str(raw).strip().lower()
    if low in _INACTIVE:
        return "inactive"
    if low in _ACTIVE:
        return "active"
    return low


# --- Encryption -------------------------------------------------------------
def normalize_encryption(raw) -> Optional[bool]:
    """
    Map heterogeneous encryption fields to a bool.
    Accepts bools, or strings like 'FileVault Enabled', 'FileVault 2',
    'LUKS Full Disk Encryption', 'none', 'disabled'.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    low = str(raw).strip().lower()
    if low in _ENCRYPTION_FALSE:
        return False
    return True


# --- Generic booleans -------------------------------------------------------
def normalize_bool(raw) -> Optional[bool]:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    low = str(raw).strip().lower()
    if low in _BOOL_TRUE:
        return True
    if low in _BOOL_FALSE:
        return False
    return None


# --- Identity helpers -------------------------------------------------------
def normalize_email(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return str(raw).strip().lower() or None


def normalize_name(raw: Optional[str]) -> Optional[str]:
    """Collapse whitespace; strip trailing punctuation like 'John D.' -> 'John D'."""
    if not raw:
        return None
    text = re.sub(r"\s+", " ", str(raw)).strip()
    return text or None


def norm_key(raw: Optional[str]) -> Optional[str]:
    """Stable lowercased key for app names / dimension nodes.

    Also applies app_aliases (from normalization.json) so equivalent product
    names collapse to one App node, e.g. "Salesforce CRM" -> "salesforce".
    The alias step is a no-op for keys not in the alias table.
    """
    if not raw:
        return None
    key = re.sub(r"\s+", " ", str(raw)).strip().lower()
    if not key:
        return None
    return _APP_ALIASES.get(key, key)


# --- Team / Location canonicalization ---------------------------------------
# Two sources often describe the same dimension with different strings:
#   "HR" vs "HR Team",  "DevOps" vs "DevOps Team",  "Engineering" vs "Engineering Org"
#   "New York HQ" vs "New York HQ - Floor 15"
# We collapse these so the graph has one node per real-world team/location.
# (Patterns are loaded from normalization.json at the top of this file.)


def normalize_team(raw: Optional[str]) -> Optional[str]:
    """Drop trailing 'Team'/'Org'/'Department'-style suffixes; collapse whitespace."""
    if not raw:
        return None
    text = re.sub(r"\s+", " ", str(raw)).strip()
    # Strip until idempotent (handles e.g. "HR Team Org" → "HR")
    while True:
        stripped = _TEAM_SUFFIX_RE.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    return text or None


def _strip_loc_type(text: str) -> str:
    for pat, _ in _LOC_TYPE_PATTERNS:
        text = pat.sub("", text)
    return re.sub(r"\s+", " ", text).strip(" -,")


def normalize_location(raw: Optional[str]) -> Optional[str]:
    """Reduce a raw location to its city/site name.

    Drops sub-location qualifiers ('- Floor 15'), type qualifiers ('Office',
    'HQ'), and collapses whitespace. So "San Francisco Office" -> "San Francisco",
    "New York HQ - Floor 15" -> "New York".
    """
    if not raw:
        return None
    text = re.sub(r"\s+", " ", str(raw)).strip()
    text = _LOC_SUBLOC_RE.sub("", text).strip()
    text = _strip_loc_type(text)
    return text or None


def parse_location_type(raw: Optional[str]) -> Optional[str]:
    """Return the canonical Location type if a qualifier is present.

    >>> parse_location_type("San Francisco Office")  # -> 'Office'
    >>> parse_location_type("New York HQ - Floor 15")  # -> 'Headquarters'
    >>> parse_location_type("London")  # -> None
    """
    if not raw:
        return None
    text = _LOC_SUBLOC_RE.sub("", str(raw))
    for pat, canon in _LOC_TYPE_PATTERNS:
        if pat.search(text):
            return canon
    return None


# Extract sub-location details so canonicalizing "New York HQ - Floor 15"
# into "New York HQ" doesn't lose the floor info — it lives on the Device.
# (Pattern + aliases are loaded from normalization.json at the top of this file.)


def parse_location_detail(raw: Optional[str]) -> dict:
    """Pull floor/suite/wing/etc. out of a location string — bidirectional.

    Matches "Floor 15" (keyword first) AND "15 Floor" / "15th Floor"
    (value first), so the order of writing doesn't lose the detail.

    >>> parse_location_detail("New York HQ - Floor 15")
    {'floor': '15'}
    >>> parse_location_detail("New York HQ, 15 Floor")
    {'floor': '15'}
    >>> parse_location_detail("Tokyo, 22nd Floor")
    {'floor': '22'}
    >>> parse_location_detail("London - Suite 200")
    {'suite': '200'}
    >>> parse_location_detail("Tokyo Bldg 5, Floor 3")
    {'building': '5', 'floor': '3'}
    """
    if not raw:
        return {}
    text = str(raw)
    out: dict = {}
    # Reverse FIRST: value-then-keyword usually carries the numeric value
    # ("15 Floor", "22nd Fl") and is more likely to be the intended assignment
    # than the trailing word in something like "15 Floor only".
    for m in _LOC_DETAIL_FINDER_REVERSE.finditer(text):
        raw_val = m.group(1).strip()
        # Strip ordinal suffixes so "22nd" -> "22"
        val = re.sub(r"(?i)(\d+)(st|nd|rd|th)$", r"\1", raw_val)
        key = _DETAIL_ALIASES.get(m.group(2).lower(), m.group(2).lower())
        if val and key not in out:
            out[key] = val
    # Forward: keyword then value ("Floor 15", "Suite 200"). Only fills keys
    # the reverse pass didn't already claim.
    for m in _LOC_DETAIL_FINDER.finditer(text):
        key = _DETAIL_ALIASES.get(m.group(1).lower(), m.group(1).lower())
        val = m.group(2).strip()
        if val and key not in out:
            out[key] = val
    return out


def parse_app_categories(name_or_norm: Optional[str]) -> list[str]:
    """Look up the list of semantic categories an app belongs to.

    Driven entirely by app_categories in normalization.json — the more keyword
    lists are filled in there, the more apps are auto-classified at ingest
    without an LLM in the loop.

    >>> parse_app_categories("Salesforce")
    ['crm']
    >>> parse_app_categories("aws console")
    ['cloud']
    >>> parse_app_categories("Some Brand New App")
    []
    """
    if not name_or_norm:
        return []
    key = re.sub(r"\s+", " ", str(name_or_norm)).strip().lower()
    # An alias may map to the canonical, look up both forms.
    aliased = _APP_ALIASES.get(key, key)
    return sorted(set(_APP_CATEGORY_INDEX.get(key, []) + _APP_CATEGORY_INDEX.get(aliased, [])))


def to_int(raw) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        return int(float(str(raw).replace(",", "")))
    except (ValueError, TypeError):
        return None


def to_float(raw) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(re.sub(r"[^\d.\-]", "", str(raw)))
    except (ValueError, TypeError):
        return None
