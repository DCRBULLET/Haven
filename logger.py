"""Shared logging configuration for Haven."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / ".haven" / "logs"
LOG_FILE = LOG_DIR / "haven.log"
_configured = False


def get_logger(name: str = "haven") -> logging.Logger:
    """Return a project logger that writes to stdout and a local log file."""
    global _configured

    root_logger = logging.getLogger("haven")
    if not _configured:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)

        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()
        root_logger.addHandler(stream_handler)
        root_logger.addHandler(file_handler)
        root_logger.propagate = False
        _configured = True

    return root_logger if name == "haven" else root_logger.getChild(name)


logger = get_logger()
