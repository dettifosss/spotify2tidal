import click

import config as cfg_module
from exporters import EXPORTERS
from models import Playlist
from spotify import create_client, fetch_playlist_tracks, fetch_single_playlist, fetch_user_playlists
from tidal import create_client as create_tidal_client, match_playlists


def _playlist_summary(p: Playlist) -> str:
    tracks = p.tracks
    total = len(tracks)
    spotify_avail = sum(1 for t in tracks if t.is_available)
    isrc          = sum(1 for t in tracks if t.tidal_match_method == "isrc")
    search_exact  = sum(1 for t in tracks if t.tidal_name_match == "exact")
    search_ver    = sum(1 for t in tracks if t.tidal_name_match == "version_mismatch")
    search_mix    = sum(1 for t in tracks if t.tidal_name_match == "mix_mismatch")
    search_other  = sum(1 for t in tracks if t.tidal_match_method == "search" and t.tidal_name_match not in ("exact", "version_mismatch", "mix_mismatch"))
    unavail       = sum(1 for t in tracks if t.tidal_id and not t.tidal_is_available)
    not_found     = sum(1 for t in tracks if t.tidal_match_method == "not_found")
    tidal_avail   = isrc + search_exact + search_ver + search_mix + search_other - unavail

    search_parts = (
        ([f"{search_exact} exact"]       if search_exact  else [])
        + ([f"{search_ver} version"]     if search_ver    else [])
        + ([f"{search_mix} mix"]         if search_mix    else [])
        + ([f"{search_other} unverified"] if search_other else [])
    )
    search_str = f", search: {', '.join(search_parts)}" if search_parts else ""

    return (
        f"  {p.name}: {total} tracks | "
        f"Spotify: {spotify_avail} avail | "
        f"Tidal: {tidal_avail} avail ({isrc} ISRC{search_str})"
        + (f", {unavail} unavail" if unavail else "")
        + (f", {not_found} not found" if not_found else "")
    )


def _verbose_attention(p: Playlist) -> None:
    """Print tracks needing attention for a playlist, grouped by issue."""
    def _fmt(t) -> str:
        artists = ", ".join(t.artists) if t.artists else "Unknown artist"
        sp_isrc = (t.isrc or "").ljust(12)
        td_isrc = (t.tidal_isrc or "").ljust(12)
        sp_line = f"      SP  {sp_isrc}  {t.name} — {artists}"
        td_line = f"      TD  {td_isrc}  {t.tidal_name or '—'}"
        return f"{sp_line}\n{td_line}"

    groups = {
        "Not found on Tidal": [
            t for t in p.tracks if t.tidal_match_method == "not_found"
        ],
        "On Tidal but unavailable in your region": [
            t for t in p.tracks if t.tidal_id and not t.tidal_is_available
        ],
        "Search: mix mismatch (likely wrong track)": [
            t for t in p.tracks if t.tidal_name_match == "mix_mismatch"
        ],
        "Search: version mismatch (different edition)": [
            t for t in p.tracks if t.tidal_name_match == "version_mismatch"
        ],
        "Search: unverified (fuzzy name match)": [
            t for t in p.tracks if t.tidal_match_method == "search" and t.tidal_name_match not in ("exact", "version_mismatch", "mix_mismatch")
        ],
        "Unavailable on Spotify": [
            t for t in p.tracks if not t.is_available
        ],
    }

    attention = {label: tracks for label, tracks in groups.items() if tracks}
    if not attention:
        return

    click.echo(f"\n    Tracks needing attention in '{p.name}':")
    for label, tracks in attention.items():
        click.echo(f"    [{label}] ({len(tracks)})")
        for t in tracks:
            click.echo(_fmt(t))


@click.command()
@click.option(
    "--config",
    "config_path",
    default="config.toml",
    show_default=True,
    help="Path to TOML config file. CLI flags and env vars override values from this file.",
)
@click.option(
    "--client-id",
    envvar="SPOTIFY_CLIENT_ID",
    default=None,
    help="Spotify app client ID. Overrides config file. Falls back to SPOTIFY_CLIENT_ID env var.",
)
@click.option(
    "--client-secret",
    envvar="SPOTIFY_CLIENT_SECRET",
    default=None,
    help="Spotify app client secret. Overrides config file. Falls back to SPOTIFY_CLIENT_SECRET env var.",
)
@click.option(
    "--redirect-uri",
    default=None,
    help=(
        "OAuth redirect URI — must match one registered in your Spotify app. "
        "Overrides config file. Default: http://127.0.0.1:8888/callback"
    ),
)
@click.option(
    "--output-dir",
    default=None,
    help="Directory to write exported files into. Overrides config file. Default: output",
)
@click.option(
    "--format",
    "export_format",
    default=None,
    type=click.Choice(list(EXPORTERS.keys())),
    help="Export format. Overrides config file. Default: csv",
)
@click.option(
    "--market",
    default=None,
    metavar="CODE",
    help=(
        "ISO 3166-1 alpha-2 market code (e.g. IS, US, GB). "
        "Required for accurate track availability info. Overrides config file."
    ),
)
@click.option(
    "--playlist",
    "playlist_id",
    default=None,
    metavar="PLAYLIST_ID",
    help=(
        "Fetch a single playlist by its Spotify ID instead of a user's full library. "
        "Ignores --user and --owned-only when set."
    ),
)
@click.option(
    "--user",
    "target_user_id",
    default=None,
    metavar="USER_ID",
    help=(
        "Spotify user ID whose playlists to fetch. "
        "Omit to fetch the authenticated user's playlists (includes private). "
        "When set, only that user's PUBLIC playlists are returned."
    ),
)
@click.option(
    "--match-tidal",
    is_flag=True,
    default=False,
    help=(
        "After fetching Spotify tracks, look up each one on Tidal and populate "
        "tidal_id and tidal_match_method on every track. "
        "Tries ISRC first (high confidence), falls back to title+artist search. "
        "Unmatched tracks will have empty tidal_id in the export."
    ),
)
@click.option(
    "--connect-tidal",
    is_flag=True,
    default=False,
    help=(
        "Authenticate with Tidal and verify the connection, then exit. "
        "On first run this opens a browser login page. "
        "The session token is cached so subsequent runs skip the browser step."
    ),
)
@click.option(
    "--owned-only",
    is_flag=True,
    default=False,
    help="Only export playlists you own (skip followed playlists).",
)
@click.option(
    "--list-only",
    is_flag=True,
    default=False,
    help="List playlists without fetching tracks or exporting.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help=(
        "After each playlist summary, list tracks that need attention: "
        "not found on Tidal, unavailable in your region, "
        "low-confidence search matches, and tracks unavailable on Spotify."
    ),
)
def main(
    config_path: str,
    client_id: str | None,
    client_secret: str | None,
    redirect_uri: str | None,
    output_dir: str | None,
    export_format: str | None,
    market: str | None,
    playlist_id: str | None,
    target_user_id: str | None,
    match_tidal: bool,
    connect_tidal: bool,
    owned_only: bool,
    list_only: bool,
    verbose: bool,
) -> None:
    """Fetch Spotify playlists and export them.

    Configuration is loaded from config.toml (see config.toml.example).
    CLI flags and env vars (SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET) take
    precedence over the config file.

    By default fetches the authenticated user's playlists (private + public).
    Use --user to fetch another user's public playlists instead.
    Use --playlist to fetch a single playlist by ID.
    """
    conf = cfg_module.load(config_path)

    # Resolve values: CLI flag > env var (already in flag) > config file > hard default
    client_id = client_id or conf.spotify.client_id or None
    client_secret = client_secret or conf.spotify.client_secret or None
    redirect_uri = redirect_uri or conf.spotify.redirect_uri
    output_dir = output_dir or conf.defaults.output_dir
    export_format = export_format or conf.defaults.format
    market = market or conf.defaults.market or None

    if connect_tidal:
        click.echo("Connecting to Tidal…")
        tidal = create_tidal_client()
        user = tidal.user
        click.echo(f"Connected as: {user.first_name} {user.last_name} (id: {user.id})")
        return

    if not client_id or not client_secret:
        raise click.UsageError(
            "Spotify credentials are required. Provide them via:\n"
            "  --client-id / --client-secret flags\n"
            "  SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET env vars\n"
            "  [spotify] section in config.toml (see config.toml.example)"
        )

    sp = create_client(client_id, client_secret, redirect_uri)

    if playlist_id:
        click.echo(f"Fetching playlist {playlist_id}…")
        playlist = fetch_single_playlist(sp, playlist_id, market=market)
        click.echo(f"  {playlist.name} — {len(playlist.tracks)} tracks")
        playlists = [playlist]
    else:
        if target_user_id:
            click.echo(f"Fetching public playlists for user: {target_user_id}…")
        else:
            click.echo("Fetching playlists for authenticated user…")
        playlists = fetch_user_playlists(sp, target_user_id=target_user_id)

        if owned_only:
            playlists = [p for p in playlists if p.is_owned]

        owned_count = sum(1 for p in playlists if p.is_owned)
        followed_count = sum(1 for p in playlists if not p.is_owned)
        click.echo(
            f"Found {len(playlists)} playlists "
            f"({owned_count} owned, {followed_count} followed)."
        )

        if list_only:
            for p in playlists:
                tag = "owned" if p.is_owned else "followed"
                click.echo(f"  [{tag}] {p.name}  ({p.total_tracks} tracks)")
            return

        for i, playlist in enumerate(playlists, 1):
            click.echo(
                f"  [{i}/{len(playlists)}] {playlist.name} — fetching {playlist.total_tracks} tracks…"
            )
            playlist.tracks = fetch_playlist_tracks(sp, playlist.id, market=market)

    if match_tidal:
        click.echo("Matching tracks against Tidal catalog…")
        tidal = create_tidal_client()

        def on_progress(done: int, total: int) -> None:
            click.echo(f"\r  {done}/{total} unique tracks resolved…  ", nl=False)

        match_playlists(tidal, playlists, on_progress=on_progress)
        click.echo(f"\r  Matched {sum(len(p.tracks) for p in playlists)} tracks.           ")

        for p in playlists:
            click.echo(_playlist_summary(p))
            if verbose:
                _verbose_attention(p)

    exporter = EXPORTERS[export_format]
    exporter.export(playlists, output_dir)
    click.echo(f"Exported {len(playlists)} playlists to {output_dir}/")


if __name__ == "__main__":
    main()
