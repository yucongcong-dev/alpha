"""
Alpha 测试系统命令行入口模块

支持通过 `python3.10 -m alpha` 或安装后的 `alpha` 命令运行 Alpha 测试系统。

Usage:
    python3.10 -m alpha [OPTIONS]

Example:
    python3.10 -m alpha --dataset-id model51 --region USA --universe TOP3000
"""

from __future__ import annotations

import logging

import coloredlogs

# 确保在 setup_runtime_logging 尚未调用时也有基本的日志输出（带颜色）
coloredlogs.install(
    level="INFO",
    fmt="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def main() -> int:
    """
    Alpha 测试系统的命令行入口函数。

    从 alpha.main 模块导入并调用主入口函数。
    支持 Ctrl+C 中断和异常处理。

    Returns:
        int: 退出状态码。
            - 0: 正常完成
            - 1: 发生错误
            - 130: 用户中断（Ctrl+C）
    """
    try:
        from .main import main as _main

        return _main()
    except KeyboardInterrupt:
        logger.warning("[abort] 用户中断")
        return 130
    except Exception as exc:
        logger.error("[error] %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
