"""Checkpoint file-system helpers."""

from __future__ import annotations

from contextlib import suppress
import json
import logging
import os
import tempfile
from typing import Any

logger = logging.getLogger(__name__)


def atomic_save(path: str, payload: dict[str, Any]) -> bool:
    """原子性保存 JSON 到文件（先写临时文件，再替换）。"""
    if not path:
        return False
    fd: int | None = None
    tmp = ""
    try:
        directory = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp_state_", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as exc:
        logger.error("[checkpoint] failed to save %s: %s", path, exc)
        return False
    finally:
        if fd is not None:
            with suppress(OSError):
                os.close(fd)
        with suppress(OSError):
            if tmp and os.path.exists(tmp):
                os.remove(tmp)


def delete_pipeline_state(state_file: str) -> None:
    """运行完成后删除状态文件（表示一次完整运行结束）。"""
    if state_file and os.path.exists(state_file):
        with suppress(OSError):
            os.remove(state_file)
            logger.debug("[checkpoint] removed completed state file %s", state_file)
