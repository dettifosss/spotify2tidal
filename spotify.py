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
    isrc: str | None = (track.get("external_ids") or {}).get("isrc")

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


def fetch_user_playlists(sp: spotipy.Spotify) -> list[Playlist]:
    me = sp.me()
    user_id: str = me["id"]

    playlists: list[Playlist] = []
    results = sp.current_user_playlists()
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
                is_owned=(owner_id == user_id),
                total_tracks=item["tracks"]["total"],
            ))
        results = sp.next(results) if results.get("next") else None

    return playlists
