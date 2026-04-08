import contextlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import tidalapi

from models import Playlist, Track

# Token cache written next to this file; gitignored
_CACHE_PATH = Path(__file__).parent / ".tidal_cache.json"


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def _save_session(session: tidalapi.Session) -> None:
    data = {
        "token_type": session.token_type,
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expiry_time": session.expiry_time.isoformat() if session.expiry_time else None,
    }
    _CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_session(session: tidalapi.Session) -> bool:
    """Try to restore a cached session. Returns True if successful."""
    if not _CACHE_PATH.exists():
        return False
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        expiry = datetime.fromisoformat(data["expiry_time"]) if data.get("expiry_time") else None
        session.load_oauth_session(
            token_type=data["token_type"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expiry_time=expiry,
        )
        return session.check_login()
    except Exception:
        return False


_REQUEST_TIMEOUT = 10  # seconds per Tidal API call


def _patch_request_timeout(session: tidalapi.Session, timeout: int = _REQUEST_TIMEOUT) -> None:
    """Patch tidalapi's underlying requests.Session to enforce a per-call timeout.

    tidalapi calls self.session.request_session.request(...) for every HTTP
    request but never passes a timeout, so a single slow call blocks forever.
    """
    original = session.request_session.request

    def _with_timeout(*args, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return original(*args, **kwargs)

    session.request_session.request = _with_timeout


def create_client() -> tidalapi.Session:
    """Return an authenticated Tidal session using tidalapi's built-in credentials.

    Restores a cached token if available.  Otherwise starts the OAuth device
    code flow: prints a URL for the user to open in their browser, then blocks
    until they complete login.  The resulting token is cached to disk so
    subsequent runs skip the browser step.
    """
    session = tidalapi.Session()

    if _load_session(session):
        _patch_request_timeout(session)
        return session

    # First login (or expired/missing cache) — device code flow
    login, future = session.login_oauth()
    print(f"\nOpen this URL in your browser to log in to Tidal:\n\n  {login.verification_uri_complete}\n")
    print("Waiting for login…")
    future.result()  # blocks until the user completes auth

    _save_session(session)
    _patch_request_timeout(session)
    return session


# ---------------------------------------------------------------------------
# Track matching
# ---------------------------------------------------------------------------

# Default number of concurrent Tidal API calls.
# tidalapi uses requests.Session internally; concurrent GETs are safe in
# practice but if you hit rate-limit errors, lower this value.
DEFAULT_MATCH_WORKERS = 8

# Module-level match cache — persists across match_playlists() calls within
# the same process so the same track is only looked up once even if it appears
# in many playlists.
_match_cache: dict[str, tuple[str | None, str | None, bool | None]] = {}
_cache_lock = threading.Lock()

MatchResult = tuple[str | None, str | None, bool | None, str | None]  # (tidal_id, method, available, tidal_isrc)


def _cache_key(track: Track) -> str:
    """Stable dedup/cache key for a track.

    ISRC is used when available (exact). Falls back to casefold name + first
    artist so tracks without ISRC are still deduplicated across playlists.
    """
    if track.isrc:
        return f"isrc:{track.isrc}"
    artist = track.artists[0].casefold().strip() if track.artists else ""
    return f"search:{track.name.casefold().strip()}|{artist}"


@contextlib.contextmanager
def _silence_tidalapi():
    """Suppress tidalapi's log.warning('Track X is unavailable') noise."""
    logger = logging.getLogger("tidalapi")
    original = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(original)


def _do_match(session: tidalapi.Session, track: Track) -> MatchResult:
    """Run the Tidal lookup for one track. No caching — call via match_playlists."""
    # 1. ISRC — dedicated API call, exact match.
    #    Prefer available tracks; keep unavailable as fallback so the ID is recorded.
    if track.isrc:
        try:
            hits = session.get_tracks_by_isrc(track.isrc.upper())
            if hits:
                available = [t for t in hits if getattr(t, "available", True)]
                best = available[0] if available else hits[0]
                return str(best.id), "isrc", bool(getattr(best, "available", True)), getattr(best, "isrc", None)
        except Exception:
            pass

    # 2. Title + artist text search (skip local files — no catalog entry)
    if track.name and not track.is_local:
        try:
            artist = track.artists[0] if track.artists else ""
            query = f"{track.name} {artist}".strip()
            results = session.search(query, models=[tidalapi.Track], limit=1)
            hits = results.get("tracks", [])
            if hits:
                return str(hits[0].id), "search", bool(getattr(hits[0], "available", True)), getattr(hits[0], "isrc", None)
        except Exception:
            pass

    return None, "not_found", None, None


def match_playlists(
    session: tidalapi.Session,
    playlists: list[Playlist],
    *,
    workers: int = DEFAULT_MATCH_WORKERS,
    on_progress: callable = None,
) -> None:
    """Populate tidal_id, tidal_match_method, tidal_is_available on every Track in-place.

    Deduplicates tracks across all playlists — the same song (by ISRC, or by
    name+artist when ISRC is absent) is fetched only once regardless of how
    many playlists it appears in.  Results are cached in memory so re-running
    on an overlapping set of playlists in the same process is also instant.

    Uses a thread pool for concurrent API calls.
    on_progress(done: int, total: int) is called after each unique track resolves.
    """
    # --- Build dedup map ---
    # key_to_tracks: cache_key -> all Track objects with that key (across all playlists)
    key_to_tracks: dict[str, list[Track]] = {}
    for playlist in playlists:
        for track in playlist.tracks:
            if track.tidal_id:
                continue  # already matched in a previous run — leave it alone
            key = _cache_key(track)
            key_to_tracks.setdefault(key, []).append(track)

    if not key_to_tracks:
        return

    # --- Separate already-cached keys from work still to do ---
    to_fetch: dict[str, Track] = {}  # key -> one representative track for the API call
    for key, tracks in key_to_tracks.items():
        with _cache_lock:
            cached = _match_cache.get(key)
        if cached is not None:
            _apply_result(tracks, cached)
        else:
            to_fetch[key] = tracks[0]

    total = len(to_fetch)
    done = 0

    if on_progress:
        on_progress(done, total)

    if not to_fetch:
        return

    # --- Fetch concurrently ---
    def fetch(key: str, track: Track) -> tuple[str, MatchResult]:
        result = _do_match(session, track)
        with _cache_lock:
            _match_cache[key] = result
        return key, result

    with _silence_tidalapi(), ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch, key, track): key for key, track in to_fetch.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                _, result = future.result()
            except Exception:
                result = (None, "not_found", None, None)
                with _cache_lock:
                    _match_cache[key] = result
            _apply_result(key_to_tracks[key], result)
            done += 1
            if on_progress:
                on_progress(done, total)


def _apply_result(tracks: list[Track], result: MatchResult) -> None:
    tidal_id, method, available, tidal_isrc = result
    for track in tracks:
        track.tidal_id = tidal_id
        track.tidal_match_method = method
        track.tidal_is_available = available
        track.tidal_isrc = tidal_isrc
