"""
运行收尾模块。

本模块承接主流程中的最终收尾阶段逻辑，包括：
- 最终结果汇总日志
- 全量结果落盘
- 中间状态文件清理
"""

from __future__ import annotations

import logging

from ..analysis.feedback_run_index import persist_feedback_run_index
from ..analysis.result_identity import merge_latest_results_by_identity, merge_results_for_update
from ..analysis.result_provenance import enrich_results_provenance
from ..analysis.results_loader import load_existing_results
from ..analysis.results_persistence import dump_results
from ..config.application import ApplicationConfig
from ..core.checkpoint_files import delete_pipeline_state
from ..core.pending_check_refresh import (
    DEFAULT_PENDING_CHECK_REFRESH_LIMIT,
    DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS,
    refresh_pending_check_results,
)
from ..io.results_store import exclusive_results_transaction
from ..models.domain_serializers import serialize_field_test_result
from ..models.result_predicates import needs_submission_check_refresh
from ..models.runtime_options import ResultWriteOptions
from ..runtime.state import InitializedRunContext

logger = logging.getLogger(__name__)


def finalize_run(
    args: ApplicationConfig,
    run_ctx: InitializedRunContext,
) -> None:
    """写出最终结果并清理运行中间状态。"""
    execution_state = run_ctx.execution_state
    write_options = ResultWriteOptions.from_config(args)
    paths = args.paths
    output_path = paths.output
    feedback_output_path = paths.feedback_output
    state_file = paths.state_file
    result_ledger = execution_state.result_ledger
    results = result_ledger.results
    journal_rows_before = [serialize_field_test_result(result) for result in results]
    refreshable_before = sum(needs_submission_check_refresh(result) for result in results)
    if refreshable_before:
        original_results = list(results)
        refreshed_results, resolved_count = refresh_pending_check_results(
            run_ctx.client_factory,
            original_results,
            retries=args.execution.check_submission_retries,
            refresh_limit=DEFAULT_PENDING_CHECK_REFRESH_LIMIT,
            max_refresh_seconds=DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS,
            max_workers=run_ctx.runtime_state.max_workers,
        )
        attempted_count = sum(
            before.updated_at != after.updated_at
            for before, after in zip(original_results, refreshed_results, strict=True)
        )
        results[:] = refreshed_results
        result_ledger.refresh_metrics()
        logger.info(
            "[check-submission-finalize] attempted=%d resolved=%d remaining=%d",
            attempted_count,
            resolved_count,
            sum(needs_submission_check_refresh(result) for result in results),
        )
    enrich_results_provenance(
        results,
        output_path=output_path,
        run_config=run_ctx.run_config,
    )
    rebuild_run_journal = journal_rows_before != [
        serialize_field_test_result(result) for result in results
    ]
    metrics = result_ledger.metrics
    logger.info(
        "[done] 测试完成：tested=%d submittable=%d errors=%d",
        len(results),
        metrics.submittable_count,
        metrics.error_count,
    )
    dump_results(
        output_path,
        write_options.dataset_id,
        results,
        settings_fingerprint=run_ctx.settings_fingerprint,
        template_library_fingerprint=run_ctx.template_library_fingerprint,
        run_fingerprint=run_ctx.run_fingerprint,
        run_config=run_ctx.run_config,
        rebuild_journal=rebuild_run_journal,
    )
    if feedback_output_path and feedback_output_path != output_path:
        with exclusive_results_transaction(feedback_output_path):
            feedback_results = merge_latest_results_by_identity(
                load_existing_results(feedback_output_path),
                run_ctx.historical_state.feedback_results,
            )
            feedback_results = merge_results_for_update(
                feedback_results,
                results,
            )
            dump_results(
                feedback_output_path,
                write_options.dataset_id,
                feedback_results,
                settings_fingerprint=run_ctx.settings_fingerprint,
                template_library_fingerprint=run_ctx.template_library_fingerprint,
                run_fingerprint=run_ctx.run_fingerprint,
                run_config=run_ctx.run_config,
                metadata_scope="feedback",
            )
            persist_feedback_run_index(feedback_output_path)
        logger.info(
            "[feedback] updated dataset history: %s (results=%d)",
            feedback_output_path,
            len(feedback_results),
        )
    delete_pipeline_state(state_file)
