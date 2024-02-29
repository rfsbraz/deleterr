from logging import handlers
import logging
import os
import sys

# These settings are for file logging only
FILENAME = "deleterr.log"
MAX_SIZE = 5000000  # 5 MB
MAX_FILES = 5

# Deleterr logger
logger = logging.getLogger("deleterr")


class LogLevelFilter(logging.Filter):
    def __init__(self, max_level):
        super(LogLevelFilter, self).__init__()

        self.max_level = max_level

    def filter(self, record):
        return record.levelno <= self.max_level


def initLogger(console=False, log_dir=False, verbose=False):
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
        setup_console_logger(console)


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
