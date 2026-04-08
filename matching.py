import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

_RULES_PATH = Path(__file__).parent / "name_match_rules.toml"


@dataclass(frozen=True)
class NameMatchRule:
    order: int          # evaluation priority; lower numbers run first
    key: str            # value stored in tidal_name_match
    label: str          # verbose group label (appended to "Search: ")
    summary: str        # short form used in the playlist summary line
    pattern: re.Pattern
    mode: str           # "any":        fires if either name matches the pattern
                        # "asymmetric": fires if exactly one name matches the pattern
                        # "feat":       strips feat. refs from both names, fires if
                        #               the stripped bases then match


def _load_rules() -> list[NameMatchRule]:
    with open(_RULES_PATH, "rb") as f:
        data = tomllib.load(f)
    rules = [
        NameMatchRule(
            order=r["order"],
            key=r["key"],
            label=r["label"],
            summary=r["summary"],
            pattern=re.compile(r["pattern"], re.IGNORECASE),
            mode=r["mode"],
        )
        for r in data["rules"]
    ]
    return sorted(rules, key=lambda r: r.order)


NAME_MATCH_RULES: list[NameMatchRule] = _load_rules()


def _strip_suffixes(s: str) -> str:
    """Strip trailing parenthetical/bracket groups and ' - <suffix>' iteratively."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r'\s*-\s+\S.*$', '', s)                # " - 2018 Remaster"
        s = re.sub(r'\s*[\(\[][^\)\]]+[\)\]]\s*$', '', s)  # trailing (...) or [...]
        s = s.strip()
    return s


def _strip_feat(s: str) -> str:
    """Remove featured artist references from a name string."""
    # Parenthetical form: "(feat. X)" / "[featuring X]" etc.
    s = re.sub(r'\s*[\(\[]\s*(?:feat(?:uring)?\.?|ft\.)\s+[^\)\]]+[\)\]]', '', s, flags=re.IGNORECASE)
    # Inline form at end: "Song feat. X" / "Song, feat. X"
    s = re.sub(r'\s*,?\s*\b(?:feat(?:uring)?\.?|ft\.)\s+.+$', '', s, flags=re.IGNORECASE)
    return s.strip()


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
                # Guard: base names must match after stripping suffixes —
                # prevents "Unbreakable - Remix" matching "Other Song (Remix)"
                if _strip_suffixes(a) == _strip_suffixes(b):
                    return rule.key
            case "asymmetric" if a_hit != b_hit:
                if _strip_suffixes(a) == _strip_suffixes(b):
                    return rule.key
            case "feat":
                a_norm = _strip_feat(a)
                b_norm = _strip_feat(b)
                # Only fire if something was stripped AND the bases now match
                if (a_norm != a or b_norm != b) and _strip_suffixes(a_norm) == _strip_suffixes(b_norm):
                    return rule.key

    # Structural fallback: strip remaster/year/other suffixes and compare bases
    if _strip_suffixes(a) == _strip_suffixes(b):
        return "version_mismatch"

    return "search"  # base names differ — unclassified
