"""
运行收尾模块。

本模块承接主流程中的最终收尾阶段逻辑，包括：
- 最终结果汇总日志
- 全量结果落盘
- 中间状态文件清理
"""

from __future__ import annotations

import logging

from .analysis.stats import current_submittable_count
from .core import delete_pipeline_state
from .io.results_store import dump_results
from .models.base import InitializedRunContext, ResultWriteArgs, RunPaths
from .policy import auto_update_blacklist

logger = logging.getLogger(__name__)


def _run_path_value(run_paths: object | None, attr: str) -> str:
    """兼容 RunPaths 与历史 attr-style 对象的路径读取。"""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def finalize_run(
    args: ResultWriteArgs,
    run_ctx: InitializedRunContext,
    run_paths: RunPaths | object | None = None,
) -> None:
    """写出最终结果并清理运行中间状态。"""
    execution_state = run_ctx.execution_state
    output_path = _run_path_value(run_paths, "output") or args.output
    state_file = _run_path_value(run_paths, "state_file")
    logger.info(
        "[done] 测试完成：tested=%d submittable=%d errors=%d",
        len(execution_state.results),
        current_submittable_count(execution_state.results),
        sum(1 for result in execution_state.results if result.status == "error"),
    )
    dump_results(
        output_path,
        args.dataset_id,
        execution_state.results,
        settings_fingerprint=run_ctx.settings_fingerprint,
        template_library_fingerprint=run_ctx.template_library_fingerprint,
        run_config=run_ctx.run_config,
        auto_update_template_blacklist=getattr(args, "auto_update_blacklist", False),
        auto_update_blacklist_fn=auto_update_blacklist,
    )
    delete_pipeline_state(state_file)
