import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

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


def _norm(s: str) -> str:
    """Strip suffixes then remove punctuation for loose base-name comparison."""
    base = _strip_suffixes(s)
    base = re.sub(r'[^\w\s]', '', base)
    return re.sub(r'\s+', ' ', base).strip()


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
                # Guard: base names must match after stripping suffixes and punctuation —
                # prevents "Unbreakable - Remix" matching "Other Song (Remix)"
                if _norm(a) == _norm(b):
                    return rule.key
            case "asymmetric" if a_hit != b_hit:
                if _norm(a) == _norm(b):
                    return rule.key
            case "feat":
                a_nofeat = _strip_feat(a)
                b_nofeat = _strip_feat(b)
                # Only fire if something was stripped AND the bases now match
                if (a_nofeat != a or b_nofeat != b) and _norm(a_nofeat) == _norm(b_nofeat):
                    return rule.key

    # Structural fallback: strip remaster/year/other suffixes and compare bases.
    # Uses exact equality (not _norm) so that punctuation-only differences like
    # "Love Rocket!" vs "Love Rocket" fall through to "search" rather than
    # being mislabelled as a version mismatch.
    if _strip_suffixes(a) == _strip_suffixes(b):
        return "version_mismatch"

    return "search"  # base names differ — unclassified


def _norm_artist(s: str) -> str:
    """Casefold and remove all non-alphanumeric characters for artist comparison.

    Handles hyphens ("Jay-Z" → "jayz"), slashes ("AC/DC" → "acdc"),
    apostrophes, and casing differences.
    """
    return re.sub(r'[^a-z0-9]', '', s.lower())


def artist_matches(spotify_artists: list[str], tidal_artist: str) -> bool:
    """Return True if any Spotify artist matches the Tidal primary artist.

    Uses normalized comparison (casefold + strip punctuation/spaces) so minor
    formatting differences don't produce false mismatches.
    """
    td = _norm_artist(tidal_artist)
    return any(_norm_artist(a) == td for a in spotify_artists)


def score_name_similarity(name_a: str, name_b: str) -> float:
    """Return a 0–100 similarity score between two track names.

    Strips suffixes and featured-artist references before scoring so that
    "Song (feat. X) [2018 Remaster]" vs "Song" scores near 100 rather than
    being penalised for the extra tokens.
    """
    a = _strip_suffixes(_strip_feat(name_a.strip().lower()))
    b = _strip_suffixes(_strip_feat(name_b.strip().lower()))
    return fuzz.token_sort_ratio(a, b)
