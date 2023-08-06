import trakt

class Trakt:
    def __init__(self, config):
        trakt.Trakt.configuration.defaults.client(
            id=config.get("trakt").get("client_id"),
            secret=config.get("trakt").get("client_secret"),
        )

    def test_connection(self):
        # Test connection
        trakt.Trakt['lists'].trending(exceptions=True, per_page=1)