from simplejustwatchapi.justwatch import search

from app import logger


class JustWatch:
    def __init__(self, country, language):
        self.country = country
        self.language = language
        logger.debug(
            "JustWatch instance created with country: %s and language: %s",
            country,
            language,
        )

    """
    Search for a title on JustWatch API
    Returns:
    [MediaEntry(entry_id='ts8', object_id=8, object_type='SHOW', title='Better Call Saul', url='https://justwatch.com/pt/serie/better-call-saul', release_year=2015, release_date='2015-02-08', runtime_minutes=50, short_description='Six years before Saul Goodman meets Walter White. We meet him when the man who will become Saul Goodman is known as Jimmy McGill, a small-time lawyer searching for his destiny, and, more immediately, hustling to make ends meet. Working alongside, and, often, against Jimmy, is “fixer” Mike Ehrmantraut. The series tracks Jimmy’s transformation into Saul Goodman, the man who puts “criminal” in “criminal lawyer".', genres=['crm', 'drm'], imdb_id='tt3032476', poster='https://images.justwatch.com/poster/269897858/s718/better-call-saul.jpg', backdrops=['https://images.justwatch.com/backdrop/171468199/s1920/better-call-saul.jpg', 'https://images.justwatch.com/backdrop/269897860/s1920/better-call-saul.jpg', 'https://images.justwatch.com/backdrop/302946702/s1920/better-call-saul.jpg', 'https://images.justwatch.com/backdrop/304447863/s1920/better-call-saul.jpg', 'https://images.justwatch.com/backdrop/273394969/s1920/better-call-saul.jpg'], offers=[Offer(id='b2Z8dHM4OlBUOjg6ZmxhdHJhdGU6NGs=', monetization_type='FLATRATE', presentation_type='_4K', price_string=None, price_value=None, price_currency='EUR', last_change_retail_price_value=None, type='AGGREGATED', package=OfferPackage(id='cGF8OA==', package_id=8, name='Netflix', technical_name='netflix', icon='https://images.justwatch.com/icon/207360008/s100/netflix.png'), url='http://www.netflix.com/title/80021955', element_count=6, available_to=None, deeplink_roku='launch/12?contentID=80021955&MediaType=show', subtitle_languages=[], video_technology=[], audio_technology=[], audio_languages=[])])]
    """

    def _search(self, title, max_results=5, detailed=False):
        return search(title, self.country, self.language, max_results, detailed)

    def search_by_title_and_year(self, title, year, media_type):
        results = self._search(title)
        for entry in results:
            if entry.title == title and entry.release_year == year:
                return entry
        return None

    def available_on(self, title, year, media_type, providers):
        result = self.search_by_title_and_year(title, year, media_type)
        if not result:
            logger.debug("No results found for title: {title}")
            return False

        if "any" in providers and result.offers:
            logger.debug("Title {title} available on any provider")
            return True

        for provider in providers:
            for offer in result.offers:
                if offer.package.technical_name == provider.lower():
                    logger.debug("Title {title} available on {provider}")
                    return True

        return False

    def is_not_available_on(self, title, year, media_type, providers):
        return not self.available_on(title, year, media_type, providers)
