"""Centralized logging for agent-skeleton.

Usage (in each module):
    from .log import get_logger
    log = get_logger(__name__)

Log level is controlled by the AGENT_LOG_LEVEL environment variable
(default: INFO). Set to DEBUG for full request/response traces.

Examples:
    AGENT_LOG_LEVEL=DEBUG uv run python main.py
"""

import logging
import os
import sys

_FMT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATE_FMT = "%H:%M:%S"

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    level_name = os.environ.get("AGENT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))

    root = logging.getLogger("agent")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)
