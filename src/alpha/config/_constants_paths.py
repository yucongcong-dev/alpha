"""Stable compatibility names for workspace-relative file paths.

Active runtime paths come from :mod:`alpha.workspace` and ``RunPaths``. These
legacy constants intentionally stay static so importing them never binds a
process to whichever YAML file happened to load first.
"""

from __future__ import annotations

DATASETS_DIR: str = "datasets"
