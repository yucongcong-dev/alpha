"""
运行收尾模块。

本模块承接主流程中的最终收尾阶段逻辑，包括：
- 最终结果汇总日志
- 全量结果落盘
- 中间状态文件清理
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..analysis.field_stats import current_submittable_count
from ..config.constants import STATUS_ERROR
from ..core.checkpoint import delete_pipeline_state
from ..io.results_store import dump_results
from ..models.io_types import RunPaths
from ..models.runtime_options import ResultWriteOptions
from ..models.runtime_protocols import ResultWriteArgs
from ..policy import auto_update_blacklist
from ..runtime import InitializedRunContext


logger = logging.getLogger(__name__)


def _run_path_value(run_paths: RunPaths | None, attr: str) -> str:
    """从 RunPaths 读取路径属性。"""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def finalize_run(
    args: ResultWriteArgs,
    run_ctx: InitializedRunContext,
    run_paths: RunPaths | None = None,
) -> None:
    """写出最终结果并清理运行中间状态。"""
    execution_state = run_ctx.execution_state
    write_options = ResultWriteOptions.from_args(args)
    output_path = _run_path_value(run_paths, "output") or write_options.output_path
    state_file = _run_path_value(run_paths, "state_file")
    logger.info(
        "[done] 测试完成：tested=%d submittable=%d errors=%d",
        len(execution_state.results),
        current_submittable_count(execution_state.results),
        sum(1 for result in execution_state.results if result.status == STATUS_ERROR),
    )
    dump_results(
        output_path,
        write_options.dataset_id,
        execution_state.results,
        settings_fingerprint=run_ctx.settings_fingerprint,
        template_library_fingerprint=run_ctx.template_library_fingerprint,
        run_config=run_ctx.run_config,
        auto_update_template_blacklist=write_options.auto_update_blacklist,
        auto_update_blacklist_fn=auto_update_blacklist,
    )
    delete_pipeline_state(state_file)
