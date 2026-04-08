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
