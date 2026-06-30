"""
CMDB Agent - Similarity Metrics

String similarity functions used for identity resolution (matching the same
user/device/app across heterogeneous sources). Uses jellyfish for phonetic and
edit-distance algorithms. No custom training required.
"""
from __future__ import annotations

import re
import jellyfish
from thefuzz import fuzz


def jaro_winkler(s1: str, s2: str) -> float:
    """Jaro-Winkler similarity (0.0 to 1.0). Best for short strings like names."""
    if not s1 or not s2:
        return 0.0
    return jellyfish.jaro_winkler_similarity(s1, s2)


def levenshtein_ratio(s1: str, s2: str) -> float:
    """Normalized Levenshtein distance as similarity ratio (0.0 to 1.0)."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    dist = jellyfish.levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    return 1.0 - (dist / max_len)


def soundex_match(s1: str, s2: str) -> bool:
    """Check if two strings have the same Soundex code (phonetic match)."""
    if not s1 or not s2:
        return False
    try:
        return jellyfish.soundex(s1) == jellyfish.soundex(s2)
    except Exception:
        return False


def metaphone_match(s1: str, s2: str) -> bool:
    """Check if two strings have the same Metaphone code."""
    if not s1 or not s2:
        return False
    try:
        return jellyfish.metaphone(s1) == jellyfish.metaphone(s2)
    except Exception:
        return False


def token_sort_ratio(s1: str, s2: str) -> float:
    """
    TheFuzz token sort ratio — sorts tokens alphabetically before comparing.
    Great for "John Smith" vs "Smith John" → 100.
    Returns 0.0 to 1.0.
    """
    if not s1 or not s2:
        return 0.0
    return fuzz.token_sort_ratio(s1, s2) / 100.0


def token_set_ratio(s1: str, s2: str) -> float:
    """
    TheFuzz token set ratio — handles partial overlap.
    "Acme Corporation Inc" vs "Acme Corp" → high score.
    Returns 0.0 to 1.0.
    """
    if not s1 or not s2:
        return 0.0
    return fuzz.token_set_ratio(s1, s2) / 100.0


def partial_ratio(s1: str, s2: str) -> float:
    """
    TheFuzz partial ratio — best substring match.
    Returns 0.0 to 1.0.
    """
    if not s1 or not s2:
        return 0.0
    return fuzz.partial_ratio(s1, s2) / 100.0


def exact_match(s1: str, s2: str) -> bool:
    """Case-insensitive exact match after stripping whitespace."""
    return s1.strip().lower() == s2.strip().lower()


def numeric_match(s1: str, s2: str) -> float:
    """
    Compare two numeric strings. Returns 1.0 if equal, 0.0 if very different.
    Handles currency, percentages, etc.
    """
    def extract_number(s: str) -> float | None:
        s = re.sub(r"[^\d.\-]", "", s)
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    n1 = extract_number(s1)
    n2 = extract_number(s2)

    if n1 is None or n2 is None:
        return 0.0
    if n1 == n2:
        return 1.0
    if n1 == 0 and n2 == 0:
        return 1.0

    # Relative difference
    max_val = max(abs(n1), abs(n2))
    if max_val == 0:
        return 1.0
    diff_ratio = abs(n1 - n2) / max_val
    return max(0.0, 1.0 - diff_ratio)


def composite_name_similarity(name1: str, name2: str) -> float:
    """
    Composite similarity for names using multiple metrics.
    Weighted average of Jaro-Winkler, token sort, and phonetic.
    """
    jw = jaro_winkler(name1, name2)
    ts = token_sort_ratio(name1, name2)
    phonetic_bonus = 0.1 if soundex_match(name1, name2) else 0.0

    # Weighted: Jaro-Winkler 40%, Token Sort 50%, Phonetic bonus 10%
    return min(1.0, (jw * 0.4) + (ts * 0.5) + phonetic_bonus)


def composite_org_similarity(org1: str, org2: str) -> float:
    """
    Composite similarity for organization names.
    Uses token set ratio heavily since org names have variable suffixes.
    """
    tset = token_set_ratio(org1, org2)
    jw = jaro_winkler(org1, org2)
    partial = partial_ratio(org1, org2)

    # Token set 50%, Jaro-Winkler 25%, Partial 25%
    return (tset * 0.5) + (jw * 0.25) + (partial * 0.25)


def best_field_similarity(value1: str, value2: str, field_type: str = "unknown") -> float:
    """
    Select the best similarity metric based on field type.
    Returns a similarity score from 0.0 to 1.0.
    """
    if exact_match(value1, value2):
        return 1.0

    v1 = value1.lower().strip()
    v2 = value2.lower().strip()

    if field_type == "person_name":
        return composite_name_similarity(v1, v2)
    elif field_type == "org_name":
        return composite_org_similarity(v1, v2)
    elif field_type in ("email", "phone", "id_code"):
        return 1.0 if v1 == v2 else levenshtein_ratio(v1, v2)
    elif field_type == "currency":
        return numeric_match(v1, v2)
    elif field_type == "date":
        return 1.0 if v1 == v2 else 0.0  # Dates should be exact after normalization
    elif field_type in ("medical_term", "medication"):
        return token_set_ratio(v1, v2)
    else:
        return token_sort_ratio(v1, v2)
