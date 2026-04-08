import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SpotifyConfig:
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://127.0.0.1:8888/callback"


@dataclass
class UserConfig:
    """Per-user overrides — useful when fetching private playlists for multiple
    accounts, each of which has its own Spotify developer app."""
    name: str = ""
    spotify_id: str = ""
    # If set, overrides the global [spotify] credentials for this user.
    spotify_client_id: str = ""
    spotify_client_secret: str = ""


@dataclass
class Defaults:
    market: str = ""
    output_dir: str = "output"
    format: str = "csv"


@dataclass
class Config:
    spotify: SpotifyConfig = field(default_factory=SpotifyConfig)
    defaults: Defaults = field(default_factory=Defaults)
    users: list[UserConfig] = field(default_factory=list)


def load(path: str | Path = "config.toml") -> Config:
    """Load config from a TOML file.  Returns an empty Config if the file
    does not exist, so the tool still works via CLI flags / env vars alone."""
    p = Path(path)
    if not p.exists():
        return Config()

    with p.open("rb") as f:
        data = tomllib.load(f)

    spotify_raw = data.get("spotify", {})
    defaults_raw = data.get("defaults", {})
    users_raw = data.get("users", [])

    return Config(
        spotify=SpotifyConfig(
            client_id=spotify_raw.get("client_id", ""),
            client_secret=spotify_raw.get("client_secret", ""),
            redirect_uri=spotify_raw.get("redirect_uri", "http://127.0.0.1:8888/callback"),
        ),
        defaults=Defaults(
            market=defaults_raw.get("market", ""),
            output_dir=defaults_raw.get("output_dir", "output"),
            format=defaults_raw.get("format", "csv"),
        ),
        users=[
            UserConfig(
                name=u.get("name", ""),
                spotify_id=u.get("spotify_id", ""),
                spotify_client_id=u.get("spotify_client_id", ""),
                spotify_client_secret=u.get("spotify_client_secret", ""),
            )
            for u in users_raw
        ],
    )
