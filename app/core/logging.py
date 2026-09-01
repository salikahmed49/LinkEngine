import logging
import sys

from app.core.config import get_settings

settings = get_settings()


def setup_logging() -> None:
    log_level = logging.DEBUG if settings.debug else logging.INFO
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
