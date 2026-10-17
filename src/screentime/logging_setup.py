"""Logging estructurado a archivo rotativo (y consola si existe)."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from screentime.config import DATA_DIR
from screentime.config_env import get_str

LOG_PATH = os.path.join(DATA_DIR, "app.log")
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return

    level_name = get_str("SCREENTIME_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger("screentime")
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(_FORMAT)
    try:
        file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=1, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        pass

    if sys.stderr is not None:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(stream_handler)

    _configured = True


def get_logger(name: str = "screentime") -> logging.Logger:
    setup_logging()
    full_name = "screentime" if name == "screentime" else f"screentime.{name}"
    return logging.getLogger(full_name)
