# Deleterr Development Guide

## Project Overview

Deleterr is an intelligent media library cleanup tool for Plex with user-friendly **"Leaving Soon" notifications**. Unlike traditional cleanup tools that delete content without warning, Deleterr's signature feature implements a "death row" pattern—items are first tagged to a "Leaving Soon" collection, users get notified via email/Discord/Slack/Telegram, and only on the next run are items actually deleted. This gives users time to watch content before it's removed.

**Key Features:**
- **Leaving Soon Collections** - Tag content for deletion, notify users, delete on next run
- **User Notifications** - Email, Discord, Slack, Telegram alerts about expiring content
- **Smart Exclusions** - Protect content by genre, actor, streaming availability (JustWatch), Trakt lists
- **Watch-Based Rules** - Delete based on watch history via Tautulli integration
- **Multi-Instance Support** - Manage multiple Radarr/Sonarr instances

## Development Workflow

### Branching Strategy
- Create feature branches from latest `main`
- Keep branches focused on a single feature or fix

### Commit Messages
Use conventional commits with scopes:
- `feat(notifications):` - New notification features
- `fix(radarr):` - Radarr-related fixes
- `test(integration):` - Integration test changes
- `refactor(config):` - Configuration refactoring

### Pull Requests
- Simple, focused PRs - one feature or fix per PR
- No generated descriptions or summaries
- Update tests for any behavioral changes

### GitHub Issues
- After closing a PR that references an issue, add a summary comment to the issue explaining what was implemented/fixed
- This helps users tracking the issue understand the resolution without reading the full PR

## Testing Philosophy

### Three-Tier Strategy

| Tier | Purpose | Characteristics |
|------|---------|-----------------|
| Unit | Module expectations | Mocks external APIs, tests logic in isolation |
| Integration | Real-world interactions | Docker containers with real Radarr/Sonarr/Tautulli |
| Regression | Config compatibility | Tests old config formats continue working |

### Critical Rules
- Never skip failing tests - fix the code or the test
- Never over-mock to the point nothing is tested
- Unit tests verify module behavior, not implementation details
- Integration tests use real services via Docker
- Regression tests ensure backward compatibility with old configs

### Config Compatibility Tests
When adding or deprecating a config property, add a YAML file to `tests/configs/` that exercises the change. These files are loaded by `test_config_files.py` to verify old configs keep parsing without errors.

- **Name files after the latest released version** (e.g., `0.2.13_feature_name.yaml`), not a future version. Check `git log` or release tags for the current version.
- **New features**: add a config that uses the new property alongside existing ones, proving the schema accepts it without breaking.
- **Deprecations/renames**: add a config using the old property name, proving backward-compatible migration still works.
- **Do not** add configs for unreleased versions - the point is to protect configs that users already have in the wild.

## Testing Commands

```bash
# Unit tests (fast, no Docker required)
pytest -m "not integration and not slow" -v

# Integration tests (requires Docker)
cd tests/integration
docker compose -f docker-compose.integration.yml up -d
pytest tests/integration/ -m integration -v --timeout=300
docker compose -f docker-compose.integration.yml down -v
```

## Documentation

When modifying `app/schema.py` (configuration schema), regenerate the documentation:

```bash
python -m scripts.generate_docs
```

This updates `docs/CONFIGURATION.md` from the Pydantic schema.

## Code Standards

- Python with type hints
- Follow existing patterns and conventions in the codebase
- Keep changes minimal and focused

## Project Structure

```
app/                    # Application source code
├── modules/            # Service integrations
│   ├── radarr.py
│   ├── sonarr.py
│   ├── tautulli.py
│   ├── notifications/  # Notification providers
│   └── ...
├── config.py
├── deleterr.py
└── media_cleaner.py

tests/                  # Unit tests
├── modules/
├── integration/        # Docker-based integration tests
│   └── docker-compose.integration.yml
└── configs/            # Config files for regression testing
```

## Known Pitfalls

### Tautulli: Episode vs Show GUIDs
- `get_history` returns **episode-level GUIDs** (`plex://episode/...`) for TV show plays, not show-level GUIDs (`plex://show/...`)
- `get_metadata` with `grandparent_rating_key` returns the correct show-level GUID
- `grandparent_rating_key` from history entries corresponds to `plex_media_item.ratingKey` in Plex
- Activity data is stored under both the episode GUID and the rating key to support matching for both movies and TV shows
