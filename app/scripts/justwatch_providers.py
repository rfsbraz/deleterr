from app.modules.justwatch import JustWatch
from app.modules.trakt import Trakt


def gather_providers(trakt_id, trakt_secret):
    # Create a Trakt instance
    trakt = Trakt(
        trakt_id,
        trakt_secret,
    )

    # Get the most popular shows
    shows = trakt.get_all_items_for_url(
        "show",
        {
            "max_items_per_list": 200,
            "lists": [
                "https://trakt.tv/shows/trending",
                "https://trakt.tv/shows/popular",
                "https://trakt.tv/shows/watched/yearly",
                "https://trakt.tv/shows/collected/yearly",
            ],
        },
    )

    # List of country codes to check providers for
    countries = [
        "US",
        "BR",
        "NG",
        "IN",
        "CN",
        "RU",
        "AU",
        "PT",
        "FR",
        "DE",
        "ES",
        "IT",
        "JP",
        "KR",
        "GB",
    ]

    # Create a set to store the providers
    providers = set()

    # Iterate over the countries
    for country in countries:
        # Create a JustWatch instance for the current country
        justwatch = JustWatch(country, "en")

        # Iterate shows and collect all the different providers in a set
        for show in shows:
            try:
                title = shows[show]["trakt"].title
                year = shows[show]["trakt"].year
                result = justwatch.search_by_title_and_year(title, year, "show")
                if result:
                    for offer in result.offers:
                        providers.add(offer.package.technical_name)
            except AttributeError:
                # Skip if the show doesn't have a title or year
                continue
            except TypeError:
                # There is a null error inside justwatch library, this is a workaround
                continue

    # Print the providers
    return providers
