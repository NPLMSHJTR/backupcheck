"""backupcheck: verify a backup tree file by file and say what fast mode misses."""

from __future__ import annotations

__version__ = "0.1.0"

from .harness import build_tree, inject, run  # noqa: E402

__all__ = ["__version__", "build_tree", "inject", "run"]
