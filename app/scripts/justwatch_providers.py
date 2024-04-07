from app.modules.justwatch import JustWatch

SHOWS = [
    ("Loki", 2021),
    ("Stranger Things", 2016),
    ("Reacher", 2022),
    ("Logan", 2017),
    ("Severance", 2022),
    ("Cobra Kai", 2018),
    ("Bo Burnham: What", 2013),
    ("Interstellar", 2014),
    ("Eraserhead", 1977),
    ("Life on Earth", 1979),
    ("24", 2001),
    ("Current Sea", 2020),
]


def gather_providers():
    # Create a JustWatch instance
    justwatch = JustWatch("US", "en")

    # Create a set to store the providers
    providers = set()

    # Iterate shows and collect all the different providers in a set
    for title, year in SHOWS:
        result = justwatch.search_by_title_and_year(title, year, "show")
        if result:
            for offer in result.offers:
                providers.add(offer.package.technical_name)

    # Print the providers
    print(providers)
