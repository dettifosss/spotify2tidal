import click

from exporters import EXPORTERS
from spotify import create_client, fetch_playlist_tracks, fetch_user_playlists


@click.command()
@click.option(
    "--client-id",
    envvar="SPOTIFY_CLIENT_ID",
    required=True,
    help="Spotify app client ID (or set SPOTIFY_CLIENT_ID env var).",
)
@click.option(
    "--client-secret",
    envvar="SPOTIFY_CLIENT_SECRET",
    required=True,
    help="Spotify app client secret (or set SPOTIFY_CLIENT_SECRET env var).",
)
@click.option(
    "--redirect-uri",
    default="http://127.0.0.1:8888/callback",
    show_default=True,
    help="OAuth redirect URI — must match one registered in your Spotify app.",
)
@click.option(
    "--output-dir",
    default="output",
    show_default=True,
    help="Directory to write exported files into.",
)
@click.option(
    "--format",
    "export_format",
    default="csv",
    show_default=True,
    type=click.Choice(list(EXPORTERS.keys())),
    help="Export format.",
)
@click.option(
    "--market",
    default=None,
    metavar="CODE",
    help=(
        "ISO 3166-1 alpha-2 market code (e.g. IS, US, GB). "
        "Required for accurate track availability info."
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
def main(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    output_dir: str,
    export_format: str,
    market: str | None,
    owned_only: bool,
    list_only: bool,
) -> None:
    """Fetch your Spotify playlists and export them."""
    sp = create_client(client_id, client_secret, redirect_uri)

    click.echo("Fetching playlists…")
    playlists = fetch_user_playlists(sp)

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

    exporter = EXPORTERS[export_format]
    exporter.export(playlists, output_dir)
    click.echo(f"Exported {len(playlists)} playlists to {output_dir}/")


if __name__ == "__main__":
    main()
