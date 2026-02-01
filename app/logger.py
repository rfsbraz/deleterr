import logging
import os
import sys
from logging import handlers

# These settings are for file logging only
FILENAME = "deleterr.log"
MAX_SIZE = 5000000  # 5 MB
MAX_FILES = 5

logging.basicConfig()

# Deleterr logger
logger = logging.getLogger("deleterr")


class LogLevelFilter(logging.Filter):
    def __init__(self, max_level):
        super(LogLevelFilter, self).__init__()

        self.max_level = max_level

    def filter(self, record):
        return record.levelno <= self.max_level


def init_logger(console=False, log_dir=False, verbose=False):
    """
    Setup logging for Deleterr. It uses the logger instance with the name
    'deleterr'. Two log handlers are added:

    * RotatingFileHandler: for the file deleterr.log
    * StreamHandler: for console (if console)

    Console logging is only enabled if console is set to True. This method can
    be invoked multiple times, during different stages of Deleterr.
    """

    remove_old_handlers()
    configure_logger(verbose)

    if log_dir:
        setup_file_logger(log_dir)

    if console:
        setup_console_logger()


def remove_old_handlers():
    # Close and remove old handlers. This is required to reinit the loggers
    # at runtime
    log_handlers = logger.handlers[:]
    for handler in log_handlers:
        # Just make sure it is cleaned up.
        if isinstance(handler, handlers.RotatingFileHandler):
            handler.close()
        elif isinstance(handler, logging.StreamHandler):
            handler.flush()

        logger.removeHandler(handler)


def configure_logger(verbose):
    # Configure the logger to accept all messages
    logger.propagate = False
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


def setup_file_logger(log_dir):
    # Setup file logger
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)-7s :: %(filename)s :: %(name)s : %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    # Main logger
    filename = os.path.join(log_dir, FILENAME)
    file_handler = handlers.RotatingFileHandler(
        filename, maxBytes=MAX_SIZE, backupCount=MAX_FILES, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    logger.addHandler(file_handler)


def setup_console_logger():
    # Setup console logger
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s :: %(filename)s :: %(name)s : %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(console_formatter)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(LogLevelFilter(logging.INFO))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(console_formatter)
    stderr_handler.setLevel(logging.WARNING)

    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)


# Expose logger methods
# Main logger
info = logger.info
warn = logger.warning
error = logger.error
debug = logger.debug
warning = logger.warning
exception = logger.exception


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size string."""
    if size_bytes >= 1024**4:
        return f"{size_bytes / (1024**4):.2f} TB"
    elif size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration string."""
    if seconds >= 3600:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.1f}s"
    elif seconds >= 60:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    return f"{seconds:.1f}s"


def log_deletion(
    title: str,
    size_bytes: int,
    media_type: str,
    is_dry_run: bool,
    action_num: int = None,
    max_actions: int = None,
    extra_info: str = None,
):
    """
    Log a deletion action with consistent formatting.

    Args:
        title: Media title
        size_bytes: Size in bytes
        media_type: 'movie' or 'show'
        is_dry_run: Whether this is a dry run
        action_num: Current action number (optional)
        max_actions: Maximum actions per run (optional)
        extra_info: Additional info like episode count (optional)
    """
    prefix = "[DRY-RUN] " if is_dry_run else ""
    action_verb = "Would have deleted" if is_dry_run else "Deleting"

    # Format action counter if provided
    counter = ""
    if action_num is not None and max_actions is not None:
        counter = f"[{action_num}/{max_actions}] "

    # Format size and extra info
    size_str = format_size(size_bytes)
    extra = f" - {extra_info}" if extra_info else ""

    logger.info(f"{prefix}{counter}{action_verb} {media_type} '{title}' ({size_str}{extra})")


def log_freed_space(saved_space: int, media_type: str, is_dry_run: bool):
    """
    Log total freed space with consistent formatting.

    Args:
        saved_space: Bytes freed
        media_type: 'movie' or 'show' (pluralized in output)
        is_dry_run: Whether this is a dry run
    """
    prefix = "[DRY-RUN] " if is_dry_run else ""
    action_verb = "Would have freed" if is_dry_run else "Freed"
    media_plural = "movies" if media_type == "movie" else "shows"

    logger.info(f"{prefix}{action_verb} {format_size(saved_space)} of space by deleting {media_plural}")
