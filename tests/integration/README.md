# Integration Tests

This directory contains integration tests that run Deleterr against real Radarr, Sonarr, and Tautulli instances via Docker.

## Architecture

```
tests/integration/
├── conftest.py                     # pytest fixtures for container lifecycle
├── docker-compose.integration.yml  # Service definitions
├── configs/                        # Sample YAML configuration files
│   ├── basic_movie_deletion.yaml   # Basic movie deletion setup
│   ├── basic_series_deletion.yaml  # Basic series deletion setup
│   ├── dry_run_mode.yaml           # Dry run testing
│   ├── added_at_threshold.yaml     # Recently added protection
│   ├── exclusions_by_*.yaml        # Various exclusion rules
│   ├── watch_status_*.yaml         # Watch status filtering
│   ├── anime_series.yaml           # Anime series filtering
│   ├── max_actions_limit.yaml      # Action limiting
│   ├── sort_by_*.yaml              # Sorting configurations
│   ├── multi_instance.yaml         # Multi-Radarr/Sonarr setup
│   ├── collection_threshold.yaml   # Collection protection
│   └── combined_exclusions.yaml    # Multiple exclusion rules
├── fixtures/
│   ├── seeders.py                  # API-based data seeding
│   ├── plex_mock.py                # Mock Plex server (Flask app)
│   └── Dockerfile.plex-mock        # Dockerfile for mock Plex
├── seed_data/
│   ├── radarr/movies.json          # Test movie definitions
│   ├── sonarr/series.json          # Test series definitions
│   └── tautulli/
│       ├── create_db.py            # Script to generate test DB
│       └── tautulli.db             # Pre-populated watch history
├── test_radarr_integration.py      # Radarr API tests
├── test_sonarr_integration.py      # Sonarr API tests
├── test_deletion_workflows.py      # End-to-end workflow tests
├── test_media_cleaner.py           # MediaCleaner helper function unit tests
├── test_real_deletion.py           # Real deletion operation tests
├── test_deleterr_deletion.py       # Direct deletion method tests
└── test_deleterr_e2e.py            # Full E2E tests: seed→configure→delete→verify
```

## Prerequisites

- Docker and Docker Compose
- Python 3.12+
- pytest and pytest-timeout

## Running Tests Locally

### 1. Generate Tautulli Database

```bash
cd tests/integration/seed_data/tautulli
python create_db.py
```

### 2. Start Docker Services

```bash
cd tests/integration
docker-compose -f docker-compose.integration.yml up -d --build
```

### 3. Wait for Services

Services need time to initialize. You can check health:

```bash
curl http://localhost:32400/health  # Plex mock
curl http://localhost:7878/ping     # Radarr
curl http://localhost:8989/ping     # Sonarr
curl http://localhost:8181/status   # Tautulli
```

### 4. Run Tests

```bash
# From project root
pytest tests/integration/ -v -m integration
```

### 5. Cleanup

```bash
cd tests/integration
docker-compose -f docker-compose.integration.yml down -v --remove-orphans
```

## Test Categories

### Connection Tests (`test_radarr_integration.py`, `test_sonarr_integration.py`)
Verify basic connectivity and API authentication with Radarr/Sonarr.

### CRUD Operations
Test create, read, update, delete operations for movies and series.

### MediaCleaner Helper Function Tests (`test_media_cleaner.py`)
Unit-style tests for the standalone helper functions in `media_cleaner.py`:
- **Exclusions by Title**: Case-insensitive title matching
- **Exclusions by Genre**: Genre-based protection rules
- **Exclusions by Collection**: Plex collection protection
- **Exclusions by Label**: Plex label-based exclusions
- **Exclusions by Release Year**: Recent release protection
- **Exclusions by Studio**: Studio-based protection (e.g., Studio Ghibli)
- **Exclusions by Director**: Director-based protection
- **Exclusions by Actor**: Actor-based protection
- **Added At Threshold**: Recently added item protection
- **Watched Status**: Filter by watched/unwatched status
- **Collection Threshold**: Protect entire collections when any item recently watched
- **Sorting Behavior**: Verify sort by size, date, rating
- **Series Type Filtering**: Filter standard/anime/daily series
- **Disk Space Threshold**: Skip libraries with sufficient disk space
- **Dry Run Mode**: Ensure no deletions in dry run
- **Max Actions Per Run**: Verify action limits are respected
- **Add List Exclusion**: Verify exclusion list behavior on delete
- **Combined Exclusions**: Multiple rules working together

### Real Deletion Tests (`test_real_deletion.py`)
Tests that perform actual deletion operations against Radarr/Sonarr:
- Delete movie removes from library
- Delete with exclusion adds to exclusion list
- Delete without exclusion does NOT add to list
- Series deletion removes from library
- Episode unmonitoring before series deletion
- Batch deletion operations
- Action limit respects max_actions_per_run
- Statistics updated after deletion

### Deletion Workflows (`test_deletion_workflows.py`, `test_deleterr_deletion.py`)
Tests for deletion workflows and direct deletion methods:
- Dry run mode
- Max actions per run limit
- Recently added protection
- Exclusion rules
- Watch history thresholds

### End-to-End Tests (`test_deleterr_e2e.py`)
Full end-to-end tests that seed Radarr/Sonarr, configure rules, and verify correct deletion:
- **Exclusion rules**: Title, genre, collection exclusions against real Radarr
- **Threshold rules**: Added at threshold protection
- **Series type filtering**: Standard vs anime series
- **Max actions limit**: Verify deletion stops at configured limit
- **Dry run mode**: Verify no deletions occur
- **Add list exclusion**: Verify deleted movies added to exclusion list
- **Combined rules**: Multiple rules must all pass for deletion

## Sample Configuration Files

The `configs/` directory contains sample YAML configuration files for testing various Deleterr features:

### Basic Configurations
| File | Purpose |
|------|---------|
| `basic_movie_deletion.yaml` | Simple movie deletion with 30-day watched threshold |
| `basic_series_deletion.yaml` | Simple series deletion setup |
| `dry_run_mode.yaml` | Test dry run mode (no actual deletions) |

### Threshold Configurations
| File | Purpose |
|------|---------|
| `added_at_threshold.yaml` | Protect items added within 14 days |
| `collection_threshold.yaml` | Protect entire collections when any item recently watched |

### Exclusion Rules
| File | Purpose |
|------|---------|
| `exclusions_by_title.yaml` | Protect specific movie/series titles |
| `exclusions_by_genre.yaml` | Protect items by genre (Horror, Documentary) |
| `exclusions_by_collection.yaml` | Protect items in specific Plex collections |
| `exclusions_by_label.yaml` | Protect items with specific Plex labels |
| `exclusions_by_release_year.yaml` | Protect recent releases (within 2 years) |
| `combined_exclusions.yaml` | Multiple exclusion rules working together |

### Watch Status & Filtering
| File | Purpose |
|------|---------|
| `watch_status_watched.yaml` | Only delete watched items |
| `watch_status_unwatched.yaml` | Only delete unwatched items |
| `anime_series.yaml` | Filter only anime series type |

### Sorting & Limits
| File | Purpose |
|------|---------|
| `sort_by_size_desc.yaml` | Delete largest files first |
| `sort_by_added_date_asc.yaml` | Delete oldest added items first |
| `max_actions_limit.yaml` | Limit to 5 deletions per run |

### Advanced Configurations
| File | Purpose |
|------|---------|
| `multi_instance.yaml` | Multiple Radarr/Sonarr instances (regular + 4K) |
| `add_list_exclusion.yaml` | Add deleted items to Radarr exclusion list |

## Mock Plex Server

Since Plex requires authentication tokens and is complex to automate, we use a Flask-based mock server that:
- Simulates Plex API responses
- Provides controllable test data
- Runs without authentication requirements
- Supports extended metadata (labels, studio, directors, writers, actors, producers)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RADARR_URL` | `http://localhost:7878` | Radarr API URL |
| `SONARR_URL` | `http://localhost:8989` | Sonarr API URL |
| `TAUTULLI_URL` | `http://localhost:8181` | Tautulli API URL |
| `PLEX_MOCK_URL` | `http://localhost:32400` | Mock Plex URL |
| `USE_EXTERNAL_SERVICES` | `false` | Skip Docker, use external services |

## CI/CD

Integration tests run automatically on:
- Every pull request
- Pushes to `main` branch

See `.github/workflows/integration-tests.yml` for the workflow configuration.

## Adding New Tests

1. Create test file with `test_` prefix
2. Add `pytestmark = pytest.mark.integration` at module level
3. Use provided fixtures (`seeded_radarr`, `seeded_sonarr`, etc.)
4. Clean up any test data you create
