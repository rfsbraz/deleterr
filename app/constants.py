# Valid sort fields
VALID_SORT_FIELDS = [
    "title",
    "size",
    "release_year",
    "runtime",
    "added_date",
    "rating",
    "seasons",
    "episodes",
]

# Valid sort orders
VALID_SORT_ORDERS = ["asc", "desc"]

# Valid action modes
VALID_ACTION_MODES = ["delete"]

SETTINGS_PER_ACTION = {
    "exclude_on_delete": ["delete"],
}

SETTINGS_PER_INSTANCE = {
    "exclude_on_delete": ["radarr"],
}
