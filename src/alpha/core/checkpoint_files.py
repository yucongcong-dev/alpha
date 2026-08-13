"""Checkpoint file-system helpers."""

from __future__ import annotations

from contextlib import suppress
import logging
import os
from typing import Any

from ..io.common import atomic_write_json

logger = logging.getLogger(__name__)


def atomic_save(path: str, payload: dict[str, Any]) -> bool:
    """Durably save checkpoint JSON while retaining the boolean error contract."""
    if not path:
        return False
    try:
        atomic_write_json(path, payload)
        return True
    except Exception as exc:
        logger.error("[checkpoint] failed to save %s: %s", path, exc)
        return False


def delete_pipeline_state(state_file: str) -> None:
    """运行完成后删除状态文件（表示一次完整运行结束）。"""
    if state_file and os.path.exists(state_file):
        with suppress(OSError):
            os.remove(state_file)
            logger.debug("[checkpoint] removed completed state file %s", state_file)
