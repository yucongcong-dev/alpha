"""
主入口模块。

本模块保留为精简入口，负责：
1. 解析命令行参数
2. 初始化运行上下文
3. 执行主循环
4. 完成最终收尾

兼容性说明：
- 历史上暴露给测试的辅助函数仍从这里转发导出
- 具体实现已拆分到 bootstrap/run_loop/finalize 模块
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any


def _bootstrap_config_environment() -> None:
    """Expose --config before importing the config package and app graph."""
    tokens = sys.argv[1:]
    for index, token in enumerate(tokens):
        value = ""
        if token == "--config" and index + 1 < len(tokens):
            value = tokens[index + 1]
        elif token.startswith("--config="):
            value = token.split("=", 1)[1]
        if value:
            os.environ["ALPHA_CONFIG_FILE"] = os.path.abspath(os.path.expanduser(value))
            return


_bootstrap_config_environment()

logger = logging.getLogger(__name__)


def parse_application_config() -> Any:
    """Lazy compatibility export for the CLI boundary parser."""
    from .cli.parser import parse_application_config as parse

    return parse()


def clean_runtime_artifacts(config: Any, **kwargs: Any) -> int:
    """Compatibility export that preserves lazy application imports."""
    from .app.bootstrap import clean_runtime_artifacts as clean

    return clean(config, **kwargs)


def initialize_run_context(config: Any, paths: Any) -> Any:
    from .app.bootstrap import initialize_run_context as initialize

    return initialize(config, paths)


def run_dry_run_plan(config: Any, paths: Any) -> bool:
    from .app.planning import run_dry_run_plan as plan

    return plan(config, paths)


def run_field_test_loop(config: Any, run_ctx: Any, paths: Any) -> None:
    from .app.run_loop import run_field_test_loop as run

    run(args=config, run_ctx=run_ctx, run_paths=paths)


def finalize_run(config: Any, run_ctx: Any, paths: Any) -> None:
    from .app.finalize import finalize_run as finalize

    finalize(args=config, run_ctx=run_ctx, run_paths=paths)


def main() -> int:
    """
    主入口函数，编排凭证加载、字段发现、候选测试与结果持久化的主流程。

    分为三个阶段：
    1. initialize_run_context(): 参数解析、凭证、客户端、模板、字段、历史状态
    2. run_field_test_loop(): 线程池中遍历字段、提交模拟、实时持久化
    3. finalize_run(): 最终落盘与中间状态清理

    Returns:
        int: 退出状态码（0=正常, 1=错误, 130=用户中断）。
    """
    config = parse_application_config()

    if config.command == "clean":
        return clean_runtime_artifacts(config)

    if config.dry_run_plan:
        return 0 if run_dry_run_plan(config, config.paths) else 1

    init_result = initialize_run_context(config, config.paths)
    if init_result is None:
        return 1

    run_field_test_loop(config, init_result, config.paths)
    finalize_run(config, init_result, config.paths)
    return 0


def run_cli_entry() -> int:
    """Run the main entrypoint with top-level CLI error handling."""
    try:
        return main()
    except KeyboardInterrupt:
        logger.warning("[abort] 用户中断")
        return 130
    except Exception as exc:
        logger.error("[error] %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_cli_entry())
