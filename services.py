from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

class AbstractUser(ABC):
    ...

class AbstractPlaylist(ABC):
    ...

class AbstractArtist(ABC):
    name: str

@dataclass
class AbstractTrack(ABC):
    name: str
    artists: list[AbstractArtist]
    duration_ms: int
    service_ids: dict[str, str] | None = None # e.g. {"spotify": "123", "tidal": "456"}
    isrc: str | None = None # ean and upc also options?
    release_date: date | None = None # for matching?
    # Might wanna include service here too
    # This calss will contain a lot of logic, I think.
    # ?? Market? in spotify it is restrictions.reason == market
    is_remix: bool | None = None
    remaster_version: str | None = None
    # Steal more of this stuff from Claudius' version

    @abstractmethod
    def __eq__(self, value):
        ...

class AlbumTrack(AbstractTrack):
    number: int
    # Album_ref? Maybe this can all just live in the track class and be None for non-album tracks.

class AbstractAlbum(ABC):
    name: str
    tracks: list[AlbumTrack]

class AbstractSingle(ABC):
    name: str
    track: AbstractTrack

class AbstractMusicService(ABC):
    def __init__(self, config: dict):
        self._config = config
        self.authenticate()

    @abstractmethod
    def authenticate(self) -> None:
        ...

    @abstractmethod
    def get_user_playlists(self, user: AbstractUser) -> list[AbstractPlaylist]:
        ...

    @abstractmethod
    def get_playlist_tracks(self, playlist: AbstractPlaylist) -> list[AbstractTrack]:
        ...

    @abstractmethod
    def find_track_by_isrc(self, isrc: str) -> AbstractTrack | None:
        ...

    @abstractmethod
    def find_track_fuzzy(self, track: AbstractTrack) -> AbstractTrack | None:
        ...

    @abstractmethod
    def write_playlist(self, playlist: AbstractPlaylist) -> None:
        ...
    
    # NYI: Methods for favorites.


# Use track art for matching?
# use preview url and musicbrainz id for matching if available?
