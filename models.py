from dataclasses import dataclass, field


@dataclass
class Track:
    name: str
    artists: list[str]
    album: str
    duration_ms: int
    added_at: str | None = None
    isrc: str | None = None
    spotify_id: str | None = None
    # False when the track is geographically unavailable or has been removed.
    # Requires --market to be set for accurate results; defaults to True when
    # the Spotify API omits the field (i.e. no market was provided).
    is_available: bool = True
    is_local: bool = False
    # Populated by --match-tidal; None means no match was found on Tidal.
    tidal_id: str | None = None
    # "isrc"      — matched via ISRC (high confidence)
    # "search"    — matched via title+artist text search (lower confidence)
    # "not_found" — matching was attempted but nothing came back
    # None        — matching was never run
    tidal_match_method: str | None = None
    # True/False = available or not in your Tidal region; None = not yet matched
    tidal_is_available: bool | None = None
    # ISRC returned by Tidal for the matched track — compare to `isrc` to verify search matches
    tidal_isrc: str | None = None
    # Name-comparison verdict for search-matched tracks (None for isrc/not_found):
    # "exact"            — track names match exactly (case-insensitive)
    # "version_mismatch" — same base name, differs only by parenthetical/remaster suffix
    # "mix_mismatch"     — one or both names contain a mix indicator
    tidal_name_match: str | None = None


@dataclass
class Playlist:
    id: str
    name: str
    description: str
    owner_id: str
    owner_name: str
    # True  → authenticated user owns this playlist
    # False → user follows/saved it but someone else owns it
    is_owned: bool
    total_tracks: int = 0
    tracks: list[Track] = field(default_factory=list)
