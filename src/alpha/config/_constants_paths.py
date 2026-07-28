"""Stable compatibility names for workspace-relative file paths.

Active runtime paths come from :mod:`alpha.workspace` and ``RunPaths``. These
legacy constants intentionally stay static so importing them never binds a
process to whichever YAML file happened to load first.
"""

from __future__ import annotations

CREDENTIALS_DIR: str = ".credentials"
DATASETS_DIR: str = "datasets"
CREDENTIALS_FILENAME: str = "worldquant_brain_credentials.json"
CREDENTIALS_KEY_FILENAME: str = "worldquant_brain_credentials.key"
ANALYSIS_SUFFIX: str = "_analysis.json"
RESULTS_JOURNAL_SUFFIX: str = "_results.jsonl"
STATE_SUFFIX: str = "_state.json"
