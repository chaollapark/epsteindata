"""Logging setup with rotating file + console output."""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("epstein_scraper")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Rotating file handler (10MB per file, keep 5)
    fh = RotatingFileHandler(
        os.path.join(log_dir, "scraper.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
