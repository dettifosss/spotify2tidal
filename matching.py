import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

_RULES_PATH = Path(__file__).parent / "name_match_rules.toml"


@dataclass(frozen=True)
class NameMatchRule:
    key: str            # value stored in tidal_name_match
    label: str          # verbose group label (appended to "Search: ")
    summary: str        # short form used in the playlist summary line
    pattern: re.Pattern
    mode: str           # "any": fires if either name matches
                        # "asymmetric": fires if exactly one name matches


def _load_rules() -> list[NameMatchRule]:
    with open(_RULES_PATH, "rb") as f:
        data = tomllib.load(f)
    return [
        NameMatchRule(
            key=r["key"],
            label=r["label"],
            summary=r["summary"],
            pattern=re.compile(r["pattern"], re.IGNORECASE),
            mode=r["mode"],
        )
        for r in data["rules"]
    ]


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
