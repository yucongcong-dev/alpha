"""
CLI 相关常量定义。
"""

from __future__ import annotations

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent

CREDS_DIR = PROJECT_ROOT / ".credentials"
# Disk-backed runtime cache root used by generated files such as field caches.
CACHE_DIR = PROJECT_ROOT / "cache"
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "data"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
BLACKLISTS_DIR = PROJECT_ROOT / "blacklists"

DEFAULT_CREDS_FILE = str(CREDS_DIR / "worldquant_brain_credentials.json")
DEFAULT_CREDS_KEY_FILE = str(CREDS_DIR / "worldquant_brain_credentials.key")
DEFAULT_TEMPLATE_LIBRARY_FILE = ""
DEFAULT_FIELDS_CACHE_FILE = ""
DEFAULT_OUTPUT_FILE = ""
