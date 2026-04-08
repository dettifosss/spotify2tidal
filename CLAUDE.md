# Claude Code — Project Instructions

## Project overview
`spotify2tidal` is a CLI tool that fetches Spotify playlists (owned and followed) for the
authenticated user and exports them. The long-term goal is to migrate playlists to Tidal.
Tidal functionality is **not yet implemented**.

## Committing
- Commit after every logical unit of work — do not let changes pile up across multiple features
- Group related changes into one commit; separate unrelated changes into separate commits
- Write descriptive commit messages that explain what changed and why

## Allowed without asking
- Editing any source file in this repo
- Running `uv sync`, `uv run`, and `uv add`
- Running the test suite (once tests exist)
- Creating new source files that fit the existing structure

## Always ask before
- `git push` — confirm before pushing to any remote
- Adding new top-level dependencies (discuss the choice first)
- Deleting files

## Code conventions
- Python 3.13+; use modern syntax (`X | Y` unions, `match`, etc.)
- Dataclasses for models (`models.py`); no Pydantic unless asked
- New export formats go in `exporters.py` as a `BaseExporter` subclass, registered in `EXPORTERS`
- Spotify API logic stays in `spotify.py`; keep it free of CLI concerns
- CLI lives in `main.py` (Click); keep option parsing separate from business logic

## Secrets & security
- `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` come from env vars — never hard-code or commit them
- Redirect URI must use `127.0.0.1` (not `localhost`) per Spotify's requirements
- `.cache` and `.cache-*` (spotipy token files) are gitignored — keep them that way

## Future work (not yet implemented)
- Tidal export/migration
- Spotify folder structure via local prefs/localStorage parsing
- Additional export formats (JSON, m3u, …)
