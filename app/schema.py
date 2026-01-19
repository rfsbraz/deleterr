# encoding: utf-8
"""
Pydantic schema for Deleterr configuration.

This module serves as the single source of truth for:
1. Configuration validation
2. Documentation generation
3. Type hints

Run `python -m scripts.generate_docs` to regenerate documentation from this schema.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class PlexConfig(BaseModel):
    """Plex server connection settings."""

    url: str = Field(
        ...,
        description="URL of your Plex server",
        json_schema_extra={"example": "http://localhost:32400"},
    )
    token: str = Field(
        ...,
        description="Plex authentication token. [How to get](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)",
        json_schema_extra={"example": "YOUR_PLEX_TOKEN"},
    )


class TautulliConfig(BaseModel):
    """Tautulli connection settings for watch history tracking."""

    url: str = Field(
        ...,
        description="URL of your Tautulli server",
        json_schema_extra={"example": "http://localhost:8181"},
    )
    api_key: str = Field(
        ...,
        description="Tautulli API key",
        json_schema_extra={"example": "YOUR_TAUTULLI_API_KEY"},
    )


class RadarrInstance(BaseModel):
    """Radarr instance connection settings."""

    name: str = Field(
        ...,
        description="Identifier for this Radarr instance (used in library config)",
        json_schema_extra={"example": "Radarr"},
    )
    url: str = Field(
        ...,
        description="URL of your Radarr server",
        json_schema_extra={"example": "http://localhost:7878"},
    )
    api_key: str = Field(
        ...,
        description="Radarr API key",
        json_schema_extra={"example": "YOUR_RADARR_API_KEY"},
    )


class SonarrInstance(BaseModel):
    """Sonarr instance connection settings."""

    name: str = Field(
        ...,
        description="Identifier for this Sonarr instance (used in library config)",
        json_schema_extra={"example": "Sonarr"},
    )
    url: str = Field(
        ...,
        description="URL of your Sonarr server",
        json_schema_extra={"example": "http://localhost:8989"},
    )
    api_key: str = Field(
        ...,
        description="Sonarr API key",
        json_schema_extra={"example": "YOUR_SONARR_API_KEY"},
    )


class TraktConfig(BaseModel):
    """Trakt API credentials. Required only for Trakt list exclusions."""

    client_id: str = Field(
        ...,
        description="Trakt client ID. Create an app at [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications)",
        json_schema_extra={"example": "YOUR_TRAKT_CLIENT_ID"},
    )
    client_secret: str = Field(
        ...,
        description="Trakt client secret",
        json_schema_extra={"example": "YOUR_TRAKT_CLIENT_SECRET"},
    )


class JustWatchGlobalConfig(BaseModel):
    """Global JustWatch settings for streaming availability lookups."""

    country: Optional[str] = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country code (e.g., US, GB, DE)",
        json_schema_extra={"example": "US"},
    )
    language: str = Field(
        default="en",
        description="Language code for API responses",
        json_schema_extra={"example": "en"},
    )


class DiskSizeThreshold(BaseModel):
    """Disk size threshold configuration."""

    path: str = Field(
        ...,
        description="Path accessible by Sonarr/Radarr to check disk space",
        json_schema_extra={"example": "/data/media"},
    )
    threshold: str = Field(
        ...,
        description="Size threshold. Units: B, KB, MB, GB, TB, PB, EB",
        json_schema_extra={"example": "1TB"},
    )


class SortConfig(BaseModel):
    """Sorting configuration for deletion order."""

    field: Literal["title", "size", "release_year", "runtime", "added_date", "rating", "seasons", "episodes"] = Field(
        default="title",
        description="Field to sort by: title, size, release_year, runtime, added_date, rating, seasons, episodes",
    )
    order: Literal["asc", "desc"] = Field(
        default="asc",
        description="Sort order: asc (ascending), desc (descending)",
    )


class TraktExclusions(BaseModel):
    """Trakt list exclusions."""

    max_items_per_list: int = Field(
        default=100,
        description="Maximum items to fetch from each Trakt list",
    )
    lists: list[str] = Field(
        default_factory=list,
        description="Trakt list URLs to exclude. Supports official lists (trending, popular) and user lists",
        json_schema_extra={"example": ["https://trakt.tv/movies/trending", "https://trakt.tv/users/justin/lists/imdb-top-rated-movies"]},
    )


class JustWatchExclusions(BaseModel):
    """JustWatch streaming availability exclusions."""

    country: Optional[str] = Field(
        default=None,
        description="Override global country setting for this library",
        json_schema_extra={"example": "US"},
    )
    language: Optional[str] = Field(
        default=None,
        description="Override global language setting for this library",
    )
    available_on: Optional[list[str]] = Field(
        default=None,
        description="Exclude media available on these providers. Use ['any'] for any service. Mutually exclusive with not_available_on",
        json_schema_extra={"example": ["netflix", "disneyplus"]},
    )
    not_available_on: Optional[list[str]] = Field(
        default=None,
        description="Exclude media NOT available on these providers. Mutually exclusive with available_on",
        json_schema_extra={"example": ["any"]},
    )

    @model_validator(mode="after")
    def check_mutual_exclusivity(self):
        if self.available_on and self.not_available_on:
            raise ValueError("available_on and not_available_on are mutually exclusive")
        return self


class RadarrExclusions(BaseModel):
    """Radarr-specific exclusions. Only applies to movie libraries."""

    tags: list[str] = Field(
        default_factory=list,
        description="Radarr tags to exclude (case-insensitive)",
        json_schema_extra={"example": ["4K", "keep", "favorite"]},
    )
    quality_profiles: list[str] = Field(
        default_factory=list,
        description="Quality profiles to exclude (exact match)",
        json_schema_extra={"example": ["Remux-2160p", "Bluray-2160p"]},
    )
    paths: list[str] = Field(
        default_factory=list,
        description="Paths to exclude (substring match)",
        json_schema_extra={"example": ["/data/media/4k"]},
    )
    monitored: Optional[bool] = Field(
        default=None,
        description="True to exclude monitored movies, False to exclude unmonitored",
    )


class Exclusions(BaseModel):
    """Exclusion rules to protect media from deletion."""

    titles: list[str] = Field(
        default_factory=list,
        description="Exact titles to exclude",
        json_schema_extra={"example": ["Forrest Gump", "The Godfather"]},
    )
    plex_labels: list[str] = Field(
        default_factory=list,
        description="Plex labels to exclude",
        json_schema_extra={"example": ["favorite", "keep"]},
    )
    genres: list[str] = Field(
        default_factory=list,
        description="Genres to exclude",
        json_schema_extra={"example": ["documentary", "horror"]},
    )
    collections: list[str] = Field(
        default_factory=list,
        description="Collections to exclude",
        json_schema_extra={"example": ["Marvel Cinematic Universe"]},
    )
    actors: list[str] = Field(
        default_factory=list,
        description="Actors to exclude",
        json_schema_extra={"example": ["Tom Hanks", "Brad Pitt"]},
    )
    producers: list[str] = Field(
        default_factory=list,
        description="Producers to exclude",
        json_schema_extra={"example": ["Steven Spielberg"]},
    )
    directors: list[str] = Field(
        default_factory=list,
        description="Directors to exclude",
        json_schema_extra={"example": ["Christopher Nolan"]},
    )
    writers: list[str] = Field(
        default_factory=list,
        description="Writers to exclude",
        json_schema_extra={"example": ["Aaron Sorkin"]},
    )
    studios: list[str] = Field(
        default_factory=list,
        description="Studios to exclude",
        json_schema_extra={"example": ["Studio Ghibli", "A24"]},
    )
    release_years: int = Field(
        default=0,
        description="Exclude media released within last X years",
        json_schema_extra={"example": 2},
    )
    trakt: Optional[TraktExclusions] = Field(
        default=None,
        description="Trakt list exclusions",
    )
    justwatch: Optional[JustWatchExclusions] = Field(
        default=None,
        description="JustWatch streaming availability exclusions",
    )
    radarr: Optional[RadarrExclusions] = Field(
        default=None,
        description="Radarr-specific exclusions (movies only)",
    )


class LibraryConfig(BaseModel):
    """Configuration for a Plex library."""

    name: str = Field(
        ...,
        description="Name of the Plex library (must match exactly)",
        json_schema_extra={"example": "Movies"},
    )
    radarr: Optional[str] = Field(
        default=None,
        description="Name of the Radarr instance to use. Mutually exclusive with sonarr",
        json_schema_extra={"example": "Radarr"},
    )
    sonarr: Optional[str] = Field(
        default=None,
        description="Name of the Sonarr instance to use. Mutually exclusive with radarr",
        json_schema_extra={"example": "Sonarr"},
    )
    series_type: Literal["standard", "anime", "daily"] = Field(
        default="standard",
        description="Series type filter for Sonarr libraries",
    )
    action_mode: Literal["delete"] = Field(
        ...,
        description="Action to perform on matching media",
    )
    watch_status: Optional[Literal["watched", "unwatched"]] = Field(
        default=None,
        description="Filter by watch status. If not set, both watched and unwatched media are considered",
    )
    last_watched_threshold: Optional[int] = Field(
        default=None,
        description="Days since last watch. Media watched within this period is protected",
        json_schema_extra={"example": 90},
    )
    added_at_threshold: Optional[int] = Field(
        default=None,
        description="Days since added to Plex. Media added within this period is protected",
        json_schema_extra={"example": 180},
    )
    apply_last_watch_threshold_to_collections: bool = Field(
        default=False,
        description="Apply last watched threshold to all items in the same collection",
    )
    add_list_exclusion_on_delete: bool = Field(
        default=False,
        description="Prevent Radarr from re-importing deleted media from lists. Radarr only",
    )
    max_actions_per_run: int = Field(
        default=10,
        description="Maximum deletions per run",
    )
    disk_size_threshold: list[DiskSizeThreshold] = Field(
        default_factory=list,
        description="Only delete when disk space is below threshold",
    )
    sort: Optional[SortConfig] = Field(
        default=None,
        description="Sorting configuration for deletion order",
    )
    exclude: Optional[Exclusions] = Field(
        default=None,
        description="Exclusion rules to protect media",
    )

    @model_validator(mode="after")
    def check_instance_set(self):
        if not self.radarr and not self.sonarr:
            raise ValueError("Either radarr or sonarr must be set")
        if self.radarr and self.sonarr:
            raise ValueError("Only one of radarr or sonarr can be set")
        return self


class DeleterrConfig(BaseModel):
    """
    Root configuration for Deleterr.

    Deleterr uses Radarr, Sonarr, and Tautulli to identify and delete media files
    based on user-specified criteria.
    """

    # General settings
    dry_run: bool = Field(
        default=True,
        description="If true, actions are only logged, not performed",
    )
    interactive: bool = Field(
        default=False,
        description="If true, prompts for confirmation before each action",
    )
    ssl_verify: bool = Field(
        default=False,
        description="Enable SSL certificate verification for API connections",
    )
    action_delay: int = Field(
        default=0,
        description="Delay (in seconds) between actions. Increase if Plex/Sonarr/Radarr timeout on remote mounts",
    )
    plex_library_scan_after_actions: bool = Field(
        default=False,
        description="Trigger a Plex library scan after actions are performed",
    )
    tautulli_library_scan_after_actions: bool = Field(
        default=False,
        description="Trigger a Tautulli library scan after actions are performed",
    )

    # Service connections
    plex: PlexConfig = Field(
        ...,
        description="Plex server connection settings",
    )
    tautulli: TautulliConfig = Field(
        ...,
        description="Tautulli connection settings",
    )
    radarr: list[RadarrInstance] = Field(
        default_factory=list,
        description="Radarr instance connections. Configure multiple for 4K instances",
    )
    sonarr: list[SonarrInstance] = Field(
        default_factory=list,
        description="Sonarr instance connections. Configure multiple for 4K instances",
    )
    trakt: Optional[TraktConfig] = Field(
        default=None,
        description="Trakt API credentials. Required only for Trakt list exclusions",
    )
    justwatch: Optional[JustWatchGlobalConfig] = Field(
        default=None,
        description="Global JustWatch settings for streaming availability lookups",
    )

    # Libraries
    libraries: list[LibraryConfig] = Field(
        ...,
        description="Configuration for each Plex library to manage",
        min_length=1,
    )

    @model_validator(mode="after")
    def check_instances_exist(self):
        if not self.radarr and not self.sonarr:
            raise ValueError("At least one Radarr or Sonarr instance must be configured")
        return self
