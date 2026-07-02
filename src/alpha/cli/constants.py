"""
CLI 相关常量定义。
"""

from __future__ import annotations

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent

CREDS_DIR = PROJECT_ROOT / ".credentials"
CACHE_DIR = PROJECT_ROOT / "cache"
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_CREDS_FILE = str(CREDS_DIR / "worldquant_brain_credentials.json")
DEFAULT_CREDS_KEY_FILE = str(CREDS_DIR / "worldquant_brain_credentials.key")
DEFAULT_TEMPLATE_LIBRARY_FILE = ""
DEFAULT_FIELDS_CACHE_FILE = ""
DEFAULT_OUTPUT_FILE = ""

