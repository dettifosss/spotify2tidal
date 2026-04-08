import csv
import os
import re
from abc import ABC, abstractmethod

from models import Playlist


def _safe_filename(name: str) -> str:
    """Replace characters that are invalid in filenames with underscores."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


class BaseExporter(ABC):
    @abstractmethod
    def export(self, playlists: list[Playlist], output_dir: str) -> None:
        """Export playlists to output_dir."""


class CSVExporter(BaseExporter):
    FIELDS = [
        "name",
        "artists",
        "album",
        "isrc",
        "duration_ms",
        "added_at",
        "spotify_id",
        "is_available",
        "is_local",
        "tidal_id",
        "tidal_match_method",
        "tidal_is_available",
        "tidal_isrc",
        "tidal_name_match",
        "tidal_name_similarity",
        "tidal_artist_match",
    ]

    def export(self, playlists: list[Playlist], output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        for playlist in playlists:
            filename = _safe_filename(playlist.name) + ".csv"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDS)
                writer.writeheader()
                for track in playlist.tracks:
                    writer.writerow({
                        "name": track.name,
                        "artists": "; ".join(track.artists),
                        "album": track.album,
                        "isrc": track.isrc or "",
                        "duration_ms": track.duration_ms,
                        "added_at": track.added_at or "",
                        "spotify_id": track.spotify_id or "",
                        "is_available": track.is_available,
                        "is_local": track.is_local,
                        "tidal_id": track.tidal_id or "",
                        "tidal_match_method": track.tidal_match_method or "",
                        "tidal_is_available": "" if track.tidal_is_available is None else track.tidal_is_available,
                        "tidal_isrc": track.tidal_isrc or "",
                        "tidal_name_match": track.tidal_name_match or "",
                        "tidal_name_similarity": "" if track.tidal_name_similarity is None else round(track.tidal_name_similarity),
                        "tidal_artist_match": "" if track.tidal_artist_match is None else track.tidal_artist_match,
                    })


EXPORTERS: dict[str, BaseExporter] = {
    "csv": CSVExporter(),
}
