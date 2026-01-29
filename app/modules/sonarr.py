from pyarr.sonarr import SonarrAPI
from app import logger


class DSonarr:
    def __init__(self, sonarr_name, sonarr_url, sonarr_api_key):
        self.quality_profiles = None
        self.tags = None
        self.sonarr_url = sonarr_url
        self.sonarr_api_key = sonarr_api_key
        self.sonarr_name = sonarr_name

        self.instance = SonarrAPI(sonarr_url, sonarr_api_key)

    def __getattr__(self, name):
        """Delegate unknown attributes to the underlying SonarrAPI instance.

        This is a safeguard to prevent AttributeError when wrapper methods
        are missing. It logs a warning so developers know to add an explicit
        wrapper method.
        """
        if hasattr(self.instance, name):
            logger.warning(
                "DSonarr.%s() not explicitly defined, delegating to SonarrAPI. "
                "Consider adding an explicit wrapper method.",
                name
            )
            return getattr(self.instance, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def get_series(self):
        return self.instance.get_series()

    def get_series_by_tvdb(self, tvdb_id):
        return self.instance.get_series(tvdb_id=tvdb_id)

    def get_tags(self):
        if not self.tags:
            self.tags = self.instance.get_tag()

        return self.tags

    def get_quality_profiles(self):
        if not self.quality_profiles:
            self.quality_profiles = self.instance.get_quality_profile()

        return self.quality_profiles

    def check_series_has_tags(self, series, tags):
        series_tags = series.get("tags", [])

        # Get the numeric id of all the tags (case-insensitive comparison)
        tags_lower = [t.lower() for t in tags]
        tag_ids = [tag['id'] for tag in self.get_tags() if tag["label"].lower() in tags_lower]

        # See if series tags and tags have any common elements
        return bool(set(series_tags) & set(tag_ids))

    def check_series_has_quality_profiles(self, series, quality_profiles):
        series_quality_profile = series.get("qualityProfileId", 0)

        # Get the numeric id of all the quality profiles
        quality_profile_ids = [quality_profile['id'] for quality_profile in self.get_quality_profiles() if quality_profile["name"] in quality_profiles]

        # See if series quality profile is in the list
        return series_quality_profile in quality_profile_ids

    def get_disk_space(self):
        return self.instance.get_disk_space()

    def get_episode(self, series_id, series=False):
        return self.instance.get_episode(series_id, series=series)

    def upd_episode_monitor(self, episode_ids, monitored):
        return self.instance.upd_episode_monitor(episode_ids, monitored)

    def del_episode_file(self, episode_file_id):
        return self.instance.del_episode_file(episode_file_id)

    def del_series(self, series_id, delete_files=False):
        return self.instance.del_series(series_id, delete_files=delete_files)

    def validate_connection(self):
        try:
            self.instance.get_health()
            return True
        except Exception as e:
            logger.debug("Error: %s", e)
        return False
