# encoding: utf-8
"""
Test notification providers with sample data.

Usage:
    docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications [options]

Options:
    --type TYPE         Notification type: 'leaving_soon' or 'run_summary' (default: leaving_soon)
    --provider NAME     Test specific provider only (email, discord, slack, telegram, webhook)
    --dry-run           Show what would be sent without actually sending
    --help              Show this help message

Examples:
    # Test all leaving_soon notifications
    docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications

    # Test only email provider for leaving_soon notifications
    docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications --provider email

    # Test only email provider for run summary notifications
    docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications --type run_summary --provider email

    # Test run summary notifications
    docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications --type run_summary

    # Preview without sending
    docker run --rm -v ./config:/config deleterr python -m scripts.test_notifications --dry-run
"""

import argparse
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import logger
from app.config import load_config
from app.modules.notifications.models import DeletedItem, RunResult
from app.modules.notifications.manager import NotificationManager

DEFAULT_CONFIG_PATH = "/config/settings.yaml"


def init_console_logging() -> None:
    """Initialize console logging for the standalone script."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.init_logger(console=True, verbose=log_level == "DEBUG")


def filter_providers(
    manager: NotificationManager,
    provider_filter: str | None,
    leaving_soon: bool = False,
) -> bool:
    """Optionally limit the manager to a single provider by name."""
    if not provider_filter:
        return True

    attr_name = "leaving_soon_providers" if leaving_soon else "providers"
    providers = getattr(manager, attr_name)
    filtered_providers = [provider for provider in providers if provider.name == provider_filter]
    setattr(manager, attr_name, filtered_providers)

    if filtered_providers:
        logger.info(f"Testing only provider: {provider_filter}")
        return True

    notification_type = "leaving_soon" if leaving_soon else "run_summary"
    logger.warning(
        f"Provider '{provider_filter}' is not configured for {notification_type} notifications"
    )
    return False


def create_sample_items() -> list[DeletedItem]:
    """Create sample DeletedItem objects for testing."""
    return [
        DeletedItem(
            title="The Matrix",
            year=1999,
            media_type="movie",
            size_bytes=15_000_000_000,  # 15 GB
            library_name="Movies",
            instance_name="Radarr",
        ),
        DeletedItem(
            title="Inception",
            year=2010,
            media_type="movie",
            size_bytes=12_500_000_000,  # 12.5 GB
            library_name="Movies",
            instance_name="Radarr",
        ),
        DeletedItem(
            title="Interstellar",
            year=2014,
            media_type="movie",
            size_bytes=18_000_000_000,  # 18 GB
            library_name="4K Movies",
            instance_name="Radarr",
        ),
        DeletedItem(
            title="Breaking Bad",
            year=2008,
            media_type="show",
            size_bytes=85_000_000_000,  # 85 GB
            library_name="TV Shows",
            instance_name="Sonarr",
        ),
        DeletedItem(
            title="The Office",
            year=2005,
            media_type="show",
            size_bytes=120_000_000_000,  # 120 GB
            library_name="TV Shows",
            instance_name="Sonarr",
        ),
    ]


def create_sample_run_result(is_dry_run: bool = False) -> RunResult:
    """Create a sample RunResult for testing run summary notifications."""
    items = create_sample_items()
    movies = [item for item in items if item.media_type == "movie"]
    shows = [item for item in items if item.media_type == "show"]
    result = RunResult(is_dry_run=is_dry_run)
    for item in movies[:2]:  # 2 deleted movies
        result.add_deleted(item)
    for item in shows[:1]:  # 1 deleted show
        result.add_deleted(item)
    for item in items[2:]:  # remaining as preview
        result.add_preview(item)
    return result


def test_leaving_soon(
    manager: NotificationManager,
    config: dict,
    provider_filter: str | None = None,
    dry_run: bool = False,
) -> bool:
    """Test leaving_soon notifications."""
    if not manager.is_leaving_soon_enabled():
        logger.warning("No leaving_soon notifications configured")
        return False

    if not filter_providers(manager, provider_filter, leaving_soon=True):
        return False

    items = create_sample_items()

    # Get URLs from config
    plex_url = None
    seerr_url = None

    if "plex" in config:
        plex_url = config["plex"].get("url")
    if "seerr" in config:
        seerr_url = config["seerr"].get("url")
    elif "overseerr" in config:
        seerr_url = config["overseerr"].get("url")

    logger.info("=" * 60)
    logger.info("Testing Leaving Soon Notifications")
    logger.info("=" * 60)
    logger.info(f"Sample items: {len(items)} ({sum(1 for i in items if i.media_type == 'movie')} movies, {sum(1 for i in items if i.media_type == 'show')} shows)")
    logger.info(f"Plex URL: {plex_url or 'Not configured'}")
    logger.info(f"Seerr URL: {seerr_url or 'Not configured'}")
    logger.info("-" * 60)

    if dry_run:
        logger.info("[DRY-RUN] Would send leaving_soon notification with:")
        for item in items:
            logger.info(f"  - {item.format_title()} ({item.media_type})")
        return True

    success = manager.send_leaving_soon(
        items=items,
        plex_url=plex_url,
        seerr_url=seerr_url,
    )

    if success:
        logger.info("Leaving soon notification sent successfully!")
    else:
        logger.error("Failed to send leaving soon notification")

    return success


def test_run_summary(
    manager: NotificationManager,
    provider_filter: str | None = None,
    dry_run: bool = False,
) -> bool:
    """Test run summary notifications."""
    if not manager.is_enabled():
        logger.warning("Notifications are disabled in config")
        return False

    if not filter_providers(manager, provider_filter, leaving_soon=False):
        return False

    result = create_sample_run_result(is_dry_run=dry_run)

    logger.info("=" * 60)
    logger.info("Testing Run Summary Notifications")
    logger.info("=" * 60)
    logger.info(f"Deleted movies: {len(result.deleted_movies)}")
    logger.info(f"Deleted shows: {len(result.deleted_shows)}")
    logger.info(f"Preview items: {len(result.preview_items)}")
    logger.info(f"Total freed: {result.total_freed_bytes:,} bytes")
    logger.info("-" * 60)

    if dry_run:
        logger.info("[DRY-RUN] Would send run summary notification")
        return True

    success = manager.send_run_summary(result)

    if success:
        logger.info("Run summary notification sent successfully!")
    else:
        logger.error("Failed to send run summary notification")

    return success


def show_config_status(config: dict) -> None:
    """Display current notification configuration status."""
    notifications = config.get("notifications", {})

    logger.info("=" * 60)
    logger.info("Notification Configuration Status")
    logger.info("=" * 60)

    # Main notification providers
    providers = ["discord", "slack", "telegram", "webhook", "email"]
    logger.info("Run Summary Providers:")
    for provider in providers:
        if notifications.get(provider):
            logger.info(f"  {provider}: Configured")
        else:
            logger.info(f"  {provider}: Not configured")

    # Leaving soon notifications
    leaving_soon = notifications.get("leaving_soon", {})
    if leaving_soon:
        logger.info("\nLeaving Soon Providers:")
        for provider in providers:
            if leaving_soon.get(provider):
                logger.info(f"  {provider}: Configured")

        if leaving_soon.get("template"):
            logger.info(f"\n  Custom template: {leaving_soon['template']}")
        if leaving_soon.get("subject"):
            logger.info(f"  Subject: {leaving_soon['subject']}")
    else:
        logger.info("\nLeaving Soon: Not configured")

    logger.info("-" * 60)


def main():
    init_console_logging()

    parser = argparse.ArgumentParser(
        description="Test notification providers with sample data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--type",
        choices=["leaving_soon", "run_summary"],
        default="leaving_soon",
        help="Notification type to test (default: leaving_soon)",
    )
    parser.add_argument(
        "--provider",
        choices=["email", "discord", "slack", "telegram", "webhook"],
        help="Test specific provider only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent without actually sending",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show configuration status only",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
    )

    args = parser.parse_args()

    # Load config
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        logger.error(f"Make sure {args.config} exists and is valid")
        sys.exit(1)

    settings = config.settings

    if args.status:
        show_config_status(settings)
        sys.exit(0)

    # Show config status first
    show_config_status(settings)

    # Initialize notification manager
    notifications_config = settings.get("notifications", {})
    if not notifications_config:
        logger.error("No notifications configured in settings.yaml")
        sys.exit(1)

    manager = NotificationManager(config)

    # Run the appropriate test
    if args.type == "leaving_soon":
        success = test_leaving_soon(manager, settings, args.provider, args.dry_run)
    else:
        success = test_run_summary(manager, args.provider, args.dry_run)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
