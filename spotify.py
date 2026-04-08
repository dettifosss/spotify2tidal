import re

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from models import Playlist, Track

SCOPES = [
    "playlist-read-private",
    "playlist-read-collaborative",
]


def create_client(client_id: str, client_secret: str, redirect_uri: str) -> spotipy.Spotify:
    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(SCOPES),
    )
    return spotipy.Spotify(auth_manager=auth)


def _normalize_isrc(raw: str | None) -> str | None:
    """Normalize a raw ISRC string to the compact 12-character uppercase form.

    Handles:
    - Leading punctuation/colons (e.g. ':NL-L56-08-01386')
    - Hyphenated form (e.g. 'NL-L56-08-01386' → 'NLL560801386')
    - Lowercase (e.g. 'uscgj1291908' → 'USCGJ1291908')

    Returns None if the result isn't exactly 12 alphanumeric characters.
    """
    if not raw:
        return None
    normalized = re.sub(r'[^A-Za-z0-9]', '', raw).upper()
    return normalized if len(normalized) == 12 else None


def _parse_track(item: dict, market: str | None) -> Track:
    """
    Parse a single playlist item dict into a Track.

    Handles three cases:
      1. track is None           → removed/unavailable, no metadata
      2. track type is 'episode' → podcast episode, skipped as unavailable
      3. normal track            → full metadata
    """
    added_at: str | None = item.get("added_at")
    is_local: bool = item.get("is_local", False)
    track = item.get("track")

    if track is None:
        return Track(
            name="[Removed Track]",
            artists=[],
            album="",
            duration_ms=0,
            added_at=added_at,
            is_available=False,
            is_local=is_local,
        )

    if track.get("type") == "episode":
        return Track(
            name=track.get("name", "[Episode]"),
            artists=[track.get("show", {}).get("name", "")] if track.get("show") else [],
            album="",
            duration_ms=track.get("duration_ms", 0),
            added_at=added_at,
            spotify_id=track.get("id"),
            is_available=track.get("is_playable", True) if market else True,
            is_local=False,
        )

    artists = [a["name"] for a in track.get("artists") or []]
    album = (track.get("album") or {}).get("name", "")
    isrc: str | None = _normalize_isrc((track.get("external_ids") or {}).get("isrc"))

    # is_playable is only present when a market was requested
    if market is not None:
        is_available = track.get("is_playable", True)
    else:
        is_available = True

    return Track(
        name=track.get("name", "[Unknown]"),
        artists=artists,
        album=album,
        duration_ms=track.get("duration_ms", 0),
        added_at=added_at,
        isrc=isrc,
        spotify_id=track.get("id"),
        is_available=is_available,
        is_local=is_local,
    )


def fetch_playlist_tracks(
    sp: spotipy.Spotify,
    playlist_id: str,
    market: str | None = None,
) -> list[Track]:
    tracks: list[Track] = []
    kwargs: dict = {"additional_types": ("track", "episode")}
    if market:
        kwargs["market"] = market

    results = sp.playlist_items(playlist_id, **kwargs)
    while results:
        for item in results.get("items") or []:
            if item is None:
                continue
            tracks.append(_parse_track(item, market))
        results = sp.next(results) if results.get("next") else None

    return tracks


def fetch_user_playlists(
    sp: spotipy.Spotify,
    target_user_id: str | None = None,
) -> list[Playlist]:
    """Fetch playlists for a Spotify user.

    If target_user_id is None, fetches the authenticated user's playlists
    (private + public).  If a user ID is provided, fetches that user's
    publicly visible playlists only.
    """
    if target_user_id is None:
        me = sp.me()
        owner_key: str = me["id"]
        results = sp.current_user_playlists()
    else:
        owner_key = target_user_id
        results = sp.user_playlists(target_user_id)

    playlists: list[Playlist] = []
    while results:
        for item in results.get("items") or []:
            if item is None:
                continue
            owner_id: str = item["owner"]["id"]
            playlists.append(Playlist(
                id=item["id"],
                name=item["name"],
                description=item.get("description") or "",
                owner_id=owner_id,
                owner_name=item["owner"].get("display_name") or owner_id,
                is_owned=(owner_id == owner_key),
                total_tracks=item["tracks"]["total"],
            ))
        results = sp.next(results) if results.get("next") else None

    return playlists


def fetch_single_playlist(
    sp: spotipy.Spotify,
    playlist_id: str,
    market: str | None = None,
) -> Playlist:
    """Fetch a single playlist by ID, including all its tracks."""
    me = sp.me()
    my_id: str = me["id"]

    kwargs: dict = {}
    if market:
        kwargs["market"] = market
    item = sp.playlist(playlist_id, **kwargs)

    owner_id: str = item["owner"]["id"]
    playlist = Playlist(
        id=item["id"],
        name=item["name"],
        description=item.get("description") or "",
        owner_id=owner_id,
        owner_name=item["owner"].get("display_name") or owner_id,
        is_owned=(owner_id == my_id),
        total_tracks=item["tracks"]["total"],
    )
    playlist.tracks = fetch_playlist_tracks(sp, playlist_id, market=market)
    return playlist
