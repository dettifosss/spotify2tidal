import re
from dataclasses import dataclass


@dataclass(frozen=True)
class NameMatchRule:
    key: str            # value stored in tidal_name_match
    label: str          # verbose group label (appended to "Search: ")
    summary: str        # short form used in the playlist summary line
    pattern: re.Pattern
    mode: str           # "any": fires if either name matches
                        # "asymmetric": fires if exactly one name matches


# Rules are checked in order; first match wins.
# To add a new classification: append a NameMatchRule here — nothing else needs changing.
NAME_MATCH_RULES: list[NameMatchRule] = [
    NameMatchRule(
        key="mix_mismatch",
        label="mix mismatch (likely wrong track)",
        summary="mix",
        pattern=re.compile(r'\b(?:re)?mix\b', re.IGNORECASE),
        mode="any",
    ),
    NameMatchRule(
        key="radio_edit",
        label="radio edit mismatch",
        summary="radio edit",
        # Phrase form avoids false positives on titles like "Radio Gaga"
        pattern=re.compile(r'\bradio\s+(?:edit|version)\b', re.IGNORECASE),
        mode="asymmetric",
    ),
    NameMatchRule(
        key="version_mismatch",
        label="version mismatch (different edition)",
        summary="version",
        pattern=re.compile(
            r'\b(?:live|demo|acoustic|outtake|concert|session|instrumental|reprise|bonus|extended|rehearsal)\b',
            re.IGNORECASE,
        ),
        mode="asymmetric",
    ),
    NameMatchRule(
        key="remaster",
        label="remaster mismatch",
        summary="remaster",
        pattern=re.compile(r'\b\d{4}\s+remaster(?:ed)?\b', re.IGNORECASE),
        mode="any",
    ),
]


def _strip_suffixes(s: str) -> str:
    """Strip trailing parenthetical/bracket groups and ' - <suffix>' iteratively."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r'\s*-\s+\S.*$', '', s)                # " - 2018 Remaster"
        s = re.sub(r'\s*[\(\[][^\)\]]+[\)\]]\s*$', '', s)  # trailing (...) or [...]
        s = s.strip()
    return s


def classify_name_match(name_a: str, name_b: str) -> str:
    """Classify the similarity between two track names.

    Source-agnostic — works for any two name strings (Spotify vs Tidal,
    Spotify vs Spotify, etc.).

    Returns one of: "exact", a rule key from NAME_MATCH_RULES, or "search"
    (unclassified — base names differ with no recognised pattern).
    """
    a = name_a.strip().lower()
    b = name_b.strip().lower()

    if a == b:
        return "exact"

    for rule in NAME_MATCH_RULES:
        a_hit = bool(rule.pattern.search(a))
        b_hit = bool(rule.pattern.search(b))
        match rule.mode:
            case "any" if a_hit or b_hit:
                return rule.key
            case "asymmetric" if a_hit != b_hit:
                return rule.key

    # Structural fallback: strip remaster/year/other suffixes and compare bases
    if _strip_suffixes(a) == _strip_suffixes(b):
        return "version_mismatch"

    return "search"  # base names differ — unclassified
