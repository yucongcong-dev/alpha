"""
CLI 相关常量定义。
"""

from __future__ import annotations

from ..workspace import DEFAULT_WORKSPACE

PROJECT_ROOT = DEFAULT_WORKSPACE.root

CREDS_DIR = DEFAULT_WORKSPACE.credentials_dir
# Disk-backed runtime cache root used by generated files such as field caches.
CACHE_DIR = DEFAULT_WORKSPACE.cache_dir
RESULTS_DIR = DEFAULT_WORKSPACE.results_dir
DATA_DIR = DEFAULT_WORKSPACE.data_dir
TEMPLATES_DIR = DEFAULT_WORKSPACE.templates_dir
BLACKLISTS_DIR = DEFAULT_WORKSPACE.blacklists_dir

DEFAULT_CREDS_FILE = str(CREDS_DIR / "worldquant_brain_credentials.json")
DEFAULT_CREDS_KEY_FILE = str(CREDS_DIR / "worldquant_brain_credentials.key")
DEFAULT_TEMPLATE_LIBRARY_FILE = ""
DEFAULT_FIELDS_CACHE_FILE = ""
DEFAULT_OUTPUT_FILE = ""
