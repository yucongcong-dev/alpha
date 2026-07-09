"""Path and context helpers for the run loop."""

from __future__ import annotations

from ..models.io_types import RunPaths
from ..models.domain import TemplateField
from ..models.runtime_options import ResultWriteOptions, TemplateBuildOptions
from ..models.runtime_protocols import ResultWriteArgs, TemplateBuildArgs
from ..runtime import InitializedRunContext, TemplateBuildContext


def run_path_value(run_paths: RunPaths | None, attr: str) -> str:
    """Read a path from RunPaths."""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def resolve_result_write_options(
    args: ResultWriteArgs,
    run_paths: RunPaths | None,
) -> ResultWriteOptions:
    """Prefer run_paths output over raw args output to avoid legacy mutation coupling."""
    options = ResultWriteOptions.from_args(args)
    output_path = run_path_value(run_paths, "output") or options.output_path
    return ResultWriteOptions(
        dataset_id=options.dataset_id,
        output_path=output_path,
        auto_update_blacklist=options.auto_update_blacklist,
    )


def create_template_build_context(
    *,
    args: TemplateBuildArgs,
    run_ctx: InitializedRunContext,
    fields: list[TemplateField],
    existing_results_count: int,
) -> TemplateBuildContext:
    """Construct the template build context and seed its feedback cache count."""
    template_build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        template_library_file=str(getattr(args, "template_library_file", "") or ""),
        all_fields=fields,
        template_library=run_ctx.template_library,
        template_registry=run_ctx.historical_state.template_registry,
        template_family_registry=run_ctx.historical_state.template_family_registry,
        template_registry_overrides=run_ctx.historical_state.template_registry_overrides,
        field_feedback=run_ctx.historical_state.field_feedback,
        global_failed_check_counts=run_ctx.historical_state.global_failed_check_counts,
        include_templates=run_ctx.filters.include_templates,
        exclude_templates=run_ctx.filters.exclude_templates,
        use_dataset_heuristics=run_ctx.use_dataset_heuristics,
        expression_policy=run_ctx.expression_policy,
    )
    template_build_ctx.feedback_result_count = existing_results_count
    return template_build_ctx
