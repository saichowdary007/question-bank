from __future__ import annotations

"""Utility helpers shared across the project.

Currently only provides a lightweight ``timing`` context-manager that logs the
elapsed time of the wrapped block. Designed so existing behaviour is
completely unaffected when it is *not* imported.
"""

import logging
import time
from contextlib import contextmanager


@contextmanager
def timing(label: str) -> None:  # noqa: D401
    """Log the execution time of a *with* block using the existing log format."""
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        logging.info("⏱️  %s completed in %.2fs", label, elapsed) 