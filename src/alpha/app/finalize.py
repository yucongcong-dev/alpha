"""
运行收尾模块。

本模块承接主流程中的最终收尾阶段逻辑，包括：
- 最终结果汇总日志
- 全量结果落盘
- 中间状态文件清理
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, cast

from ..analysis.result_identity import (
    STATUS_PENDING_SELF_CORRELATION,
    is_self_correlation_pending_result,
)
from ..analysis.stats import current_submittable_count
from ..config.constants import STATUS_ERROR, STATUS_SIMULATED, STATUS_SUBMITTED
from ..config.getters import get_polling_default_wait
from ..core import delete_pipeline_state
from ..core.simulation_stages import checksubmit_with_retry, submit_with_retry
from ..io.results_store import dump_results
from ..models.io_types import RunPaths
from ..models.runtime import InitializedRunContext, ResultWriteArgs
from ..policy import auto_update_blacklist

if TYPE_CHECKING:
    from ..api.client import WorkerClientFactory

logger = logging.getLogger(__name__)


def _run_path_value(run_paths: object | None, attr: str) -> str:
    """兼容 RunPaths 与历史 attr-style 对象的路径读取。"""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def _refresh_pending_self_correlation_results(
    args: ResultWriteArgs,
    run_ctx: InitializedRunContext,
) -> int:
    """在最终落盘前统一复查仍处于 SELF_CORRELATION=PENDING 的结果。"""
    client_factory = cast("WorkerClientFactory | None", run_ctx.client_factory)
    if client_factory is None:
        return 0
    pending_results = [
        result
        for result in run_ctx.execution_state.results
        if result.alpha_id and is_self_correlation_pending_result(result)
    ]
    if not pending_results:
        return 0

    logger.info(
        "[finalize] rechecking %d pending self-correlation candidates before final flush",
        len(pending_results),
    )
    client = client_factory.get_client()
    refreshed_count = 0
    for result in pending_results:
        alpha_id = str(result.alpha_id or "")
        if not alpha_id:
            continue
        refreshed_count += 1
        result.self_correlation_recheck_count += 1
        result.self_correlation_last_recheck_at = time.time()
        submittable, message, failed_checks = checksubmit_with_retry(
            client,
            alpha_id,
            retries=int(getattr(args, "check_submit_retries", 3) or 3),
            self_correlation_max_polls=int(getattr(args, "self_correlation_max_polls", 0) or 0),
            self_correlation_poll_seconds=float(
                getattr(args, "self_correlation_poll_seconds", get_polling_default_wait())
                or get_polling_default_wait()
            ),
        )
        result.submittable = submittable
        result.message = message
        result.failed_checks = failed_checks
        if submittable is None:
            result.status = STATUS_PENDING_SELF_CORRELATION
        else:
            result.status = STATUS_SIMULATED
            result.self_correlation_pending_since = 0.0
        if submittable and bool(getattr(args, "submit", False)) and not result.submitted:
            submit_message = submit_with_retry(
                client,
                alpha_id,
                retries=int(getattr(args, "submit_retries", 3) or 3),
            )
            result.submitted = True
            result.status = STATUS_SUBMITTED
            result.message = submit_message
        logger.info(
            "[finalize] alpha_id=%s self-correlation recheck count=%d submittable=%s message=%s",
            alpha_id,
            result.self_correlation_recheck_count,
            result.submittable,
            result.message,
        )
    return refreshed_count


def recheck_pending_self_correlation_results(
    args: ResultWriteArgs,
    run_ctx: InitializedRunContext,
) -> int:
    """公开的 pending SELF_CORRELATION 复查入口。"""
    return _refresh_pending_self_correlation_results(args, run_ctx)


def should_finalize_recheck_pending_self_correlation(args: ResultWriteArgs) -> bool:
    """判断 finalize 阶段是否应同步复查 pending self-correlation 结果。"""
    return bool(getattr(args, "finalize_recheck_pending_self_correlation", False))


def finalize_run(
    args: ResultWriteArgs,
    run_ctx: InitializedRunContext,
    run_paths: RunPaths | object | None = None,
) -> None:
    """写出最终结果并清理运行中间状态。"""
    execution_state = run_ctx.execution_state
    output_path = cast("str", _run_path_value(run_paths, "output") or args.output)
    state_file = _run_path_value(run_paths, "state_file")
    if should_finalize_recheck_pending_self_correlation(args):
        _refresh_pending_self_correlation_results(args, run_ctx)
    logger.info(
        "[done] 测试完成：tested=%d submittable=%d errors=%d",
        len(execution_state.results),
        current_submittable_count(execution_state.results),
        sum(1 for result in execution_state.results if result.status == STATUS_ERROR),
    )
    dump_results(
        output_path,
        cast("str", args.dataset_id),
        execution_state.results,
        settings_fingerprint=run_ctx.settings_fingerprint,
        template_library_fingerprint=run_ctx.template_library_fingerprint,
        run_config=run_ctx.run_config,
        auto_update_template_blacklist=getattr(args, "auto_update_blacklist", False),
        auto_update_blacklist_fn=auto_update_blacklist,
    )
    delete_pipeline_state(state_file)
