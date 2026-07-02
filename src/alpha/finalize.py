"""
运行收尾模块。

本模块承接主流程中的最终收尾阶段逻辑，包括：
- 最终结果汇总日志
- 全量结果落盘
- 中间状态文件清理
"""

from __future__ import annotations

import argparse
import logging
from typing import Any

from .analysis.stats import current_submittable_count
from .core import delete_pipeline_state
from .io.output import dump_results
from .models.base import InitializedRunContext

logger = logging.getLogger(__name__)


def finalize_run(
    args: argparse.Namespace,
    run_ctx: InitializedRunContext,
    run_paths: Any = None,
) -> None:
    """写出最终结果并清理运行中间状态。"""
    execution_state = run_ctx.execution_state
    logger.info(
        "[done] 测试完成：tested=%d submittable=%d errors=%d",
        len(execution_state.results),
        current_submittable_count(execution_state.results),
        sum(1 for result in execution_state.results if result.status == "error"),
    )
    dump_results(
        args.output,
        args.dataset_id,
        execution_state.results,
        settings_fingerprint=run_ctx.settings_fingerprint,
        template_library_fingerprint=run_ctx.template_library_fingerprint,
        run_config=run_ctx.run_config,
        auto_update_template_blacklist=getattr(args, "auto_update_blacklist", False),
    )
    delete_pipeline_state(getattr(run_paths, "state_file", ""))
