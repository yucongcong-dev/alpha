"""Context construction helpers for the run loop."""

from __future__ import annotations

from ..core.executor import build_template_build_context
from ..models.domain import TemplateField
from ..models.runtime_options import ResultWriteOptions, TemplateBuildOptions
from ..runtime.contexts import FutureCompletionContext, TemplateBuildContext
from ..runtime.state import InitializedRunContext


def resolve_future_completion_context(
    run_ctx: InitializedRunContext,
    result_write_options: ResultWriteOptions,
) -> FutureCompletionContext:
    """Build the shared completion context once for the whole run loop."""
    return FutureCompletionContext(
        result_write_options=result_write_options,
        settings_fingerprint=run_ctx.settings_fingerprint,
        template_library_fingerprint=run_ctx.template_library_fingerprint,
        run_config=run_ctx.run_config,
    )


def create_template_build_context(
    *,
    options: TemplateBuildOptions,
    run_ctx: InitializedRunContext,
    fields: list[TemplateField],
    existing_results_count: int,
) -> TemplateBuildContext:
    """Construct the template build context and seed its feedback cache count."""
    template_build_ctx = build_template_build_context(
        options=options,
        fields=fields,
        template_library=run_ctx.template_library,
        historical_state=run_ctx.historical_state,
        filters=run_ctx.filters,
        use_dataset_heuristics=run_ctx.use_dataset_heuristics,
        existing_results_count=existing_results_count,
    )
    if run_ctx.expression_policy is not None:
        template_build_ctx.expression_policy = run_ctx.expression_policy
    return template_build_ctx
