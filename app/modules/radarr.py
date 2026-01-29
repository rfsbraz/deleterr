from pyarr.radarr import RadarrAPI
from app import logger


class DRadarr:
    def __init__(self, radarr_name, radarr_url, radarr_api_key):
        self.quality_profiles = None
        self.tags = None
        self.radarr_url = radarr_url
        self.radarr_api_key = radarr_api_key
        self.radarr_name = radarr_name

        self.instance = RadarrAPI(radarr_url, radarr_api_key)

    def __getattr__(self, name):
        """Delegate unknown attributes to the underlying RadarrAPI instance.

        This is a safeguard to prevent AttributeError when wrapper methods
        are missing. It logs a warning so developers know to add an explicit
        wrapper method.
        """
        if hasattr(self.instance, name):
            logger.warning(
                "DRadarr.%s() not explicitly defined, delegating to RadarrAPI. "
                "Consider adding an explicit wrapper method.",
                name
            )
            return getattr(self.instance, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def get_movies(self):
        return self.instance.get_movie()

    def get_movie(self, movie_id):
        return self.instance.get_movie(movie_id, tmdb=True)

    def get_tags(self):
        if not self.tags:
            self.tags = self.instance.get_tag()

        return self.tags

    def get_quality_profiles(self):
        if not self.quality_profiles:
            self.quality_profiles = self.instance.get_quality_profile()

        return self.quality_profiles

    def check_movie_has_tags(self, movie, tags):
        movie_tags = movie.get("tags", [])

        # Get the numeric id of all the tags (case-insensitive comparison)
        tags_lower = [t.lower() for t in tags]
        tag_ids = [tag['id'] for tag in self.get_tags() if tag["label"].lower() in tags_lower]

        # See if movie tags and tags have any common elements
        return bool(set(movie_tags) & set(tag_ids))

    def check_movie_has_quality_profiles(self, movie, quality_profiles):
        movie_quality_profile = movie.get("qualityProfileId", [])

        # Get the numeric id of all the tags
        quality_profile_ids = [quality_profile['id'] for quality_profile in self.get_quality_profiles() if quality_profile["name"] in quality_profiles]

        # See if movie tags and tags have any common elements
        return movie_quality_profile in quality_profile_ids

    def get_disk_space(self):
        return self.instance.get_disk_space()

    def del_movie(self, movie_id, delete_files=False, add_exclusion=False):
        return self.instance.del_movie(movie_id, delete_files=delete_files, add_exclusion=add_exclusion)

    def validate_connection(self):
        try:
            self.instance.get_health()
            return True
        except Exception as e:
            logger.debug("Error: %s", e)
        return False
