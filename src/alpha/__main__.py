"""
Alpha 测试系统命令行入口模块

支持通过 `python3.10 -m alpha` 或安装后的 `alpha` 命令运行 Alpha 测试系统。

Usage:
    python3.10 -m alpha [OPTIONS]

Example:
    python3.10 -m alpha --dataset-id model51 --region USA --universe TOP3000
"""

from __future__ import annotations

import coloredlogs

from .main import run_cli_entry

# 确保在 setup_runtime_logging 尚未调用时也有基本的日志输出（带颜色）
coloredlogs.install(
    level="INFO",
    fmt="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)


if __name__ == "__main__":
    raise SystemExit(run_cli_entry())
