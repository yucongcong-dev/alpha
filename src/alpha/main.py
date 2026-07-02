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

from .bootstrap import (
    clean_runtime_artifacts,
    create_and_login_client,
    initialize_run_context,
    prepare_fields_for_execution,
)
from .cli.parser import normalize_args_paths, parse_args
from .finalize import finalize_run
from .run_loop import (
    build_field_resume_positions,
    normalize_resume_index,
    refresh_runtime_feedback,
    run_field_test_loop,
)

logger = logging.getLogger(__name__)

# 保留历史函数名，避免测试与外部导入立即失效。
_initialize = initialize_run_context
_run_field_test_loop = run_field_test_loop


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
    args = parse_args()

    if args.command == "clean":
        return clean_runtime_artifacts(args)

    run_paths = normalize_args_paths(args)

    init_result = initialize_run_context(args, run_paths)
    if init_result is None:
        return 1

    run_field_test_loop(
        args=args,
        run_ctx=init_result,
        run_paths=run_paths,
    )
    finalize_run(
        args=args,
        run_ctx=init_result,
        run_paths=run_paths,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.warning("[abort] 用户中断")
        raise SystemExit(130) from None
    except Exception as exc:
        logger.error("[error] %s", exc)
        raise SystemExit(1) from None
