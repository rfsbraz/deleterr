# Integration Tests

This directory contains integration tests that run Deleterr against real Radarr, Sonarr, and Tautulli instances via Docker.

## Architecture

```
tests/integration/
├── conftest.py                     # pytest fixtures for container lifecycle
├── docker-compose.integration.yml  # Service definitions
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
└── test_deletion_workflows.py      # End-to-end workflow tests
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

### Connection Tests
Verify basic connectivity and API authentication with Radarr/Sonarr.

### CRUD Operations
Test create, read, update, delete operations for movies and series.

### Deletion Workflows
End-to-end tests simulating Deleterr's deletion logic:
- Dry run mode
- Max actions per run limit
- Recently added protection
- Exclusion rules
- Watch history thresholds

## Mock Plex Server

Since Plex requires authentication tokens and is complex to automate, we use a Flask-based mock server that:
- Simulates Plex API responses
- Provides controllable test data
- Runs without authentication requirements

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
- Pushes to `develop` and `main` branches

See `.github/workflows/integration-tests.yml` for the workflow configuration.

## Adding New Tests

1. Create test file with `test_` prefix
2. Add `pytestmark = pytest.mark.integration` at module level
3. Use provided fixtures (`seeded_radarr`, `seeded_sonarr`, etc.)
4. Clean up any test data you create
