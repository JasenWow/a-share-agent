"""Unified logging configuration for aquan.

Phase 1: minimal — re-export stdlib logging with a project-default formatter.
Concrete log handlers/structured logging can be layered in later.
"""

from __future__ import annotations

import logging as _stdlib_logging
from logging import (
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL,
    Logger,
    getLogger,
)

__all__ = [
    "CRITICAL",
    "DEBUG",
    "ERROR",
    "INFO",
    "WARNING",
    "Logger",
    "getLogger",
    "stdlib",
]

# Re-export stdlib logging module under a stable name for advanced callers.
stdlib = _stdlib_logging


def get_logger(name: str = "aquan") -> Logger:
    """Return a logger preconfigured with aquan defaults (no handlers attached yet)."""
    logger = getLogger(name)
    if not logger.handlers:
        handler = _stdlib_logging.StreamHandler()
        handler.setFormatter(_stdlib_logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(INFO)
    return logger
