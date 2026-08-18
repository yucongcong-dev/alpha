"""CLI lifecycle orchestration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config.application import ApplicationConfig

logger = logging.getLogger(__name__)


def _configure_application_logging(config: ApplicationConfig) -> None:
    """Configure console/file logging once after the CLI boundary is parsed."""
    from .cli import filters as cli_filters

    writes_runtime_log = config.command == "check-submissions" or (
        config.command == "run" and not config.planning.dry_run_plan
    )
    cli_filters.setup_runtime_logging(
        config.paths.log_file if writes_runtime_log else "",
        verbose=config.runtime_flags.verbose,
        quiet=config.runtime_flags.quiet,
    )


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
    # These modules are imported after ``run_cli_entry`` has bound the active
    # settings file; static configuration resolves lazily via ``get_static_config``.
    from .app import bootstrap, finalize, planning, run_lock, run_loop, submission_check_refresh
    from .cli import parser
    from .config.application import CleanConfig

    config = parser.parse_application_config()
    if isinstance(config, CleanConfig):
        return bootstrap.clean_runtime_artifacts(config)
    _configure_application_logging(config)
    if config.command == "check-submissions":
        with run_lock.exclusive_run_lock(config.paths.output):
            return 0 if submission_check_refresh.refresh_submission_checks(config) else 1
    if config.planning.dry_run_plan:
        return 0 if planning.run_dry_run_plan(config) else 1

    with run_lock.exclusive_run_lock(config.paths.output):
        init_result = bootstrap.initialize_run_context(config)
        if init_result is None:
            return 1

        try:
            run_loop.run_field_test_loop(config, init_result)
            finalize.finalize_run(config, init_result)
        finally:
            init_result.client_factory.close()
    return 0


def run_cli_entry() -> int:
    """Run the main entrypoint with top-level CLI error handling."""
    try:
        # Keep raw argv handling at the CLI dispatcher.  ``__main__`` only
        # performs interpreter/logging setup before it delegates here.
        from .config.yaml import activate_config_from_argv

        activate_config_from_argv()
        return main()
    except KeyboardInterrupt:
        logger.warning("[abort] 用户中断")
        return 130
    except Exception as exc:
        logger.error("[error] %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_cli_entry())
