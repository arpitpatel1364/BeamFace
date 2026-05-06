"""
Logging configuration for BeamFace.

Provides a factory function that creates a named logger writing to both
a rotating file in the logs directory and the console. All modules should
obtain their logger via this function rather than calling logging.getLogger
directly, to ensure consistent formatting and output paths.
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from core.config import LOG_DIR

_MAX_BYTES = 5 * 1024 * 1024    # 5 MB per log file
_BACKUP_COUNT = 3
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized_loggers: set = set()


def setup_logger(name: str) -> logging.Logger:
    """
    Create or retrieve a named logger that writes to file and console.

    On first call for a given name, adds both a RotatingFileHandler and a
    StreamHandler. Subsequent calls for the same name return the existing
    logger without adding duplicate handlers.

    Parameters
    ----------
    name : str
        Logger name, typically the module's dotted path (e.g. "beamface.core").

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    if name in _initialized_loggers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    # File handler (rotating)
    os.makedirs(LOG_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    log_path = os.path.join(LOG_DIR, f"beamface_{date_str}.log")
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    _initialized_loggers.add(name)
    return logger
