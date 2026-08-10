"""
启动与初始化编排模块。

本模块承接主入口中的前置阶段逻辑，包括：
- 字段过滤与优先级排序
- 运行产物清理
- 客户端创建与登录
- 运行上下文初始化
"""

from __future__ import annotations

from dataclasses import replace
import logging

from ..api.client import BrainClient
from ..config.application import ApplicationConfig
from ..generators.fingerprint import stable_fingerprint
from ..generators.payload import build_settings_fingerprint
from ..models.io_types import RunPaths
from ..models.runtime_options import (
    ApiClientOptions,
    BootstrapFieldOptions,
    CredentialLoadOptions,
    TemplateBuildOptions,
)
from ..models.runtime_protocols import RunConfig
from ..runtime.state import InitializedRunContext
from .bootstrap_cleanup import clean_runtime_artifacts as clean_runtime_artifacts
from .bootstrap_clients import create_and_login_client, resolve_credentials
from .bootstrap_field_resources import load_bootstrap_fields, log_field_selection_stats
from .bootstrap_fields import prepare_fields_for_execution
from .bootstrap_pending_checks import reconcile_pending_check_results
from .bootstrap_run_context import assemble_initialized_run_context, build_runtime_concurrency
from .bootstrap_runtime_outputs import (
    prepare_runtime_outputs,
)
from .bootstrap_state import build_execution_state
from .bootstrap_supporting_resources import load_bootstrap_supporting_resources
from .bootstrap_types import PreparedBootstrapResources
from .run_identity import build_research_run_fingerprint, validate_existing_run_identity

logger = logging.getLogger(__name__)


def initialize_run_context(args: ApplicationConfig) -> InitializedRunContext | None:
    """执行主流程的初始化阶段，返回结构化运行上下文。"""
    api_client_options = ApiClientOptions.from_config(args)
    field_options = BootstrapFieldOptions.from_config(args)
    template_options = TemplateBuildOptions.from_config(args)
    paths = args.paths
    run_config = prepare_runtime_outputs(args)
    email, password = resolve_credentials(
        CredentialLoadOptions.from_config(args),
    )
    if not email or not password:
        logger.error("[error] 缺少凭证，无法继续")
        return None

    bootstrap_client, client_factory = create_and_login_client(
        email,
        password,
        api_client_options,
    )
    run_context: InitializedRunContext | None = None
    try:
        try:
            prepared = prepare_bootstrap_resources(
                field_options,
                template_options,
                paths,
                bootstrap_client,
                run_config=run_config,
            )
        finally:
            close = getattr(bootstrap_client, "close", None)
            if callable(close):
                close()
        if prepared is None:
            return None

        execution_state = build_execution_state(
            dataset_id=args.dataset.dataset_id,
            output_file=paths.output,
            historical_state=prepared.historical_state,
            settings_fingerprint=prepared.settings_fingerprint,
            template_library_fingerprint=prepared.template_library_fingerprint,
            run_fingerprint=prepared.run_fingerprint,
            run_config=prepared.run_config,
        )

        concurrency = build_runtime_concurrency(args.execution)
        run_context = assemble_initialized_run_context(
            client_factory=client_factory,
            prepared=prepared,
            execution_state=execution_state,
            runtime_state=concurrency.runtime_state,
            create_semaphore=concurrency.create_semaphore,
        )
        return run_context
    finally:
        if run_context is None:
            close_factory = getattr(client_factory, "close", None)
            if callable(close_factory):
                close_factory()


def prepare_bootstrap_resources(
    field_options: BootstrapFieldOptions,
    template_options: TemplateBuildOptions,
    paths: RunPaths,
    bootstrap_client: BrainClient,
    *,
    run_config: RunConfig,
) -> PreparedBootstrapResources | None:
    """Load template, feedback, and field resources needed to build the run context."""
    dataset_id = field_options.dataset_id
    supporting_resources = load_bootstrap_supporting_resources(
        dataset_id=dataset_id,
        paths=paths,
        backfill_window=template_options.backfill_window,
    )
    expression_policy = supporting_resources.expression_policy
    effective_run_config = dict(run_config)
    effective_run_config["heuristic_policy"] = {
        "dataset_id": dataset_id,
        "policy_version": str(getattr(expression_policy, "policy_version", "unversioned")),
        "feedback_scope": str(getattr(expression_policy, "feedback_scope", "field_type")),
        "use_curated_heuristics": bool(expression_policy.use_curated_heuristics),
    }
    template_library_fingerprint = stable_fingerprint(supporting_resources.template_library)
    settings_fingerprint = build_settings_fingerprint(template_options)
    run_fingerprint = build_research_run_fingerprint(
        run_config=effective_run_config,
        template_library=supporting_resources.template_library,
        filters=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        blacklist_payload=supporting_resources.blacklist_payload,
    )
    validate_existing_run_identity(
        paths.output,
        run_fingerprint=run_fingerprint,
        run_config=effective_run_config,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
    )
    historical_state = supporting_resources.historical_state
    reconciled_historical_state = reconcile_pending_check_results(
        bootstrap_client,
        historical_state,
        retries=field_options.check_submission_retries,
        output_file=paths.output,
        feedback_output=paths.feedback_output,
        dataset_id=dataset_id,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_fingerprint=run_fingerprint,
        run_config=effective_run_config,
    )
    if reconciled_historical_state is not historical_state:
        supporting_resources = replace(
            supporting_resources,
            historical_state=reconciled_historical_state,
        )
    fields = load_bootstrap_fields(
        dataset_id=dataset_id,
        bootstrap_client=bootstrap_client,
        paths=paths,
        field_fetch_options=field_options.fetch,
    )
    if not fields:
        logger.error("[error] 数据集 %s 未返回任何字段", dataset_id)
        return None

    prepared_fields, field_stats = prepare_fields_for_execution(
        list(fields),
        filters_dict=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        historical_state=supporting_resources.historical_state,
        selection_options=field_options.selection,
    )
    log_field_selection_stats(
        dataset_id=dataset_id,
        selection_options=field_options.selection,
        field_stats=field_stats,
        fields=prepared_fields,
    )
    if not prepared_fields:
        return None
    if supporting_resources.historical_state.existing_results:
        logger.info(
            "[resume] 从 %s 加载 %d 个历史结果",
            paths.output,
            len(supporting_resources.historical_state.existing_results),
        )

    return PreparedBootstrapResources(
        template_library=supporting_resources.template_library,
        filters=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        use_dataset_heuristics=supporting_resources.expression_policy.use_curated_heuristics,
        template_library_fingerprint=template_library_fingerprint,
        settings_fingerprint=settings_fingerprint,
        run_fingerprint=run_fingerprint,
        historical_state=supporting_resources.historical_state,
        fields=prepared_fields,
        run_config=effective_run_config,
    )
