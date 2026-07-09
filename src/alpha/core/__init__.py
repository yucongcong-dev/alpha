"""Compatibility export layer for core execution helpers.

This package keeps the historical ``alpha.core`` import surface stable while
avoiding eager imports of the whole execution stack at module import time.
Internal modules should prefer importing concrete submodules directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from .checkpoint import (
        delete_pipeline_state,
        load_pipeline_state,
        save_checkpoint,
        save_pipeline_state,
    )
    from .executor import (
        build_pending_templates_for_field,
        inflight_template_keys,
        print_dry_run_plan,
        should_skip_expression_by_history,
        should_skip_field,
    )
    from .result_processing import apply_completed_result, detect_result_congestion
    from .scheduler import (
        apply_congestion_cooldown,
        drain_completed_futures,
        handle_completed_future,
        maybe_restore_runtime_concurrency,
        register_queue_busy_field,
        throttle_before_submission,
    )
    from .simulation import (
        build_failure_result,
        create_simulation_with_retry,
        extract_alpha_id,
        extract_checks,
        extract_failed_checks,
        is_submittable_from_checks,
        poll_simulation_with_retry,
        run_field_test,
        run_field_test_in_worker,
        summarize_failure,
    )
    from .template_planning import (
        build_pending_template_variants,
        resolve_field_template_candidates,
    )

_EXPORT_MAP: ExportMap = {
    "delete_pipeline_state": (".checkpoint", "delete_pipeline_state"),
    "load_pipeline_state": (".checkpoint", "load_pipeline_state"),
    "save_checkpoint": (".checkpoint", "save_checkpoint"),
    "save_pipeline_state": (".checkpoint", "save_pipeline_state"),
    "build_pending_templates_for_field": (".executor", "build_pending_templates_for_field"),
    "inflight_template_keys": (".executor", "inflight_template_keys"),
    "print_dry_run_plan": (".executor", "print_dry_run_plan"),
    "should_skip_expression_by_history": (".executor", "should_skip_expression_by_history"),
    "should_skip_field": (".executor", "should_skip_field"),
    "apply_completed_result": (".result_processing", "apply_completed_result"),
    "detect_result_congestion": (".result_processing", "detect_result_congestion"),
    "apply_congestion_cooldown": (".scheduler", "apply_congestion_cooldown"),
    "drain_completed_futures": (".scheduler", "drain_completed_futures"),
    "handle_completed_future": (".scheduler", "handle_completed_future"),
    "maybe_restore_runtime_concurrency": (".scheduler", "maybe_restore_runtime_concurrency"),
    "register_queue_busy_field": (".scheduler", "register_queue_busy_field"),
    "throttle_before_submission": (".scheduler", "throttle_before_submission"),
    "build_failure_result": (".simulation", "build_failure_result"),
    "create_simulation_with_retry": (".simulation", "create_simulation_with_retry"),
    "extract_alpha_id": (".simulation", "extract_alpha_id"),
    "extract_checks": (".simulation", "extract_checks"),
    "extract_failed_checks": (".simulation", "extract_failed_checks"),
    "is_submittable_from_checks": (".simulation", "is_submittable_from_checks"),
    "poll_simulation_with_retry": (".simulation", "poll_simulation_with_retry"),
    "run_field_test": (".simulation", "run_field_test"),
    "run_field_test_in_worker": (".simulation", "run_field_test_in_worker"),
    "summarize_failure": (".simulation", "summarize_failure"),
    "build_pending_template_variants": (".template_planning", "build_pending_template_variants"),
    "resolve_field_template_candidates": (".template_planning", "resolve_field_template_candidates"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str) -> object:
    return resolve_export(
        name=name,
        export_map=_EXPORT_MAP,
        package=__package__ or "",
        namespace=__name__,
        target_globals=globals(),
    )


def __dir__() -> list[str]:
    return facade_dir(globals(), _EXPORT_MAP)
