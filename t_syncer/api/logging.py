import logging
import sys

LOGGER_NAME = "tsyncer"
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

logger = logging.getLogger(LOGGER_NAME)


def _pin_query_logger() -> None:
    """Keep peewee's query log off, whatever level the app runs at.

    It logs every statement with its bound parameters, so a DEBUG run would put
    the Jira API token into the container log in clear text.
    """
    logging.getLogger("peewee").setLevel(logging.WARNING)


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Send the app's own log to stdout, where Docker picks it up.

    Idempotent: create_app runs once per process in production and once per
    test, and a second call must not double every line.
    """
    logger.setLevel(level.upper())
    _pin_query_logger()
    for existing in logger.handlers:
        if getattr(existing, "_tsyncer", False):

            return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler._tsyncer = True
    logger.addHandler(handler)

    return logger
