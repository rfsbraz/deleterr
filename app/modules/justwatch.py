from simplejustwatchapi.justwatch import search

from app import logger


class JustWatch:
    def __init__(self, country, language):
        self.country = country
        self.language = language
        self._search_cache = {}  # Cache for search results
        logger.debug(
            "JustWatch instance created with country: %s and language: %s",
            country,
            language,
        )

    def _search(self, title, max_results=5, detailed=False):
        """
        Search for a title on JustWatch API with caching and error handling.

        Returns:
            List of MediaEntry objects, or empty list on error
        """
        cache_key = f"{title}:{max_results}:{detailed}"

        if cache_key in self._search_cache:
            logger.debug(f"Cache hit for JustWatch search: {title}")
            return self._search_cache[cache_key]

        try:
            results = search(title, self.country, self.language, max_results, detailed)
            self._search_cache[cache_key] = results
            return results
        except Exception as e:
            logger.warning(f"JustWatch API error while searching for '{title}': {e}")
            return []

    def search_by_title_and_year(self, title, year, media_type):
        """
        Search for a specific title and year combination.

        Args:
            title: The title to search for
            year: The release year to match
            media_type: 'movie' or 'show' (currently unused but kept for future use)

        Returns:
            MediaEntry if found, None otherwise
        """
        results = self._search(title)
        if not results:
            return None

        # Try exact match first
        for entry in results:
            if entry.title == title and entry.release_year == year:
                return entry

        # Try case-insensitive match
        for entry in results:
            if entry.title.lower() == title.lower() and entry.release_year == year:
                return entry

        # Try with 1-year tolerance (release dates can vary by region)
        for entry in results:
            if (
                entry.title.lower() == title.lower()
                and year
                and entry.release_year
                and abs(entry.release_year - year) <= 1
            ):
                logger.debug(
                    f"Matched '{title}' with year tolerance: {entry.release_year} vs {year}"
                )
                return entry

        return None

    def available_on(self, title, year, media_type, providers):
        """
        Check if a title is available on any of the specified streaming providers.

        Args:
            title: The title to check
            year: The release year
            media_type: 'movie' or 'show'
            providers: List of provider technical names (e.g., ['netflix', 'amazon'])
                      Use ['any'] to match any streaming provider

        Returns:
            True if the title is available on any of the specified providers
        """
        result = self.search_by_title_and_year(title, year, media_type)
        if not result:
            logger.debug(f"No JustWatch results found for title: {title} ({year})")
            return False

        # Check if offers exist
        if not result.offers:
            logger.debug(f"No streaming offers found for: {title} ({year})")
            return False

        # Handle 'any' provider - matches if any offer exists
        providers_lower = [p.lower() for p in providers]
        if "any" in providers_lower:
            logger.debug(f"'{title}' is available on streaming (any provider match)")
            return True

        # Check for specific providers
        for offer in result.offers:
            if offer.package and offer.package.technical_name:
                offer_provider = offer.package.technical_name.lower()
                if offer_provider in providers_lower:
                    logger.debug(
                        f"'{title}' is available on {offer.package.technical_name}"
                    )
                    return True

        logger.debug(
            f"'{title}' is not available on any of the specified providers: {providers}"
        )
        return False

    def is_not_available_on(self, title, year, media_type, providers):
        """
        Check if a title is NOT available on the specified streaming providers.

        This is the inverse of available_on() - returns True if the title
        cannot be found on any of the specified providers.

        Args:
            title: The title to check
            year: The release year
            media_type: 'movie' or 'show'
            providers: List of provider technical names

        Returns:
            True if the title is NOT available on the specified providers
        """
        return not self.available_on(title, year, media_type, providers)

    def clear_cache(self):
        """Clear the search cache."""
        self._search_cache.clear()
        logger.debug("JustWatch search cache cleared")
