"""Shared relationship semantics (dependency-free so both store backends import it).

Single-valued relationships describe a property a CI can only have one of (a device
is at one location, in one department). For these, a new edge REPLACES the prior one
rather than accumulating — combined with ascending source-priority writes, the
highest-priority source's value wins. Multi-valued relationships (USES, MEMBER_OF,
INTEGRATES_WITH, ASSIGNED_TO) accumulate normally.
"""
SINGLE_VALUED_RELS = {"LOCATED_AT", "BELONGS_TO", "RUNS"}

# Properties that are UNION-merged on write (instead of overwritten).
# A Location node aggregates every floor/suite/wing/etc. it has been seen with,
# across all source files, so the node carries the full set of sub-locations.
LIST_MERGE_PROPS = {
    "floors", "suites", "wings", "rooms", "buildings",   # Location sub-details
    "types",                                              # Location types
    "categories",                                         # App taxonomy
}
