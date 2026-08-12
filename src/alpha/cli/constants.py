"""
CLI 相关常量定义。
"""

from __future__ import annotations

from ..workspace import DEFAULT_WORKSPACE

PROJECT_ROOT = DEFAULT_WORKSPACE.root

CREDS_DIR = DEFAULT_WORKSPACE.credentials_dir

DEFAULT_CREDS_FILE = str(CREDS_DIR / "worldquant_brain_credentials.json")
DEFAULT_CREDS_KEY_FILE = str(CREDS_DIR / "worldquant_brain_credentials.key")
