"""
模拟生命周期管理模块。

本模块保留 `alpha.core.simulation` 的兼容入口，主文件只负责字段测试编排，
解析、预检、阶段执行和结果构建细节已拆到辅助模块。
"""

from __future__ import annotations

import logging

from ..api.client import BrainClient, WorkerClientFactory
from ..config.constants import SENTINEL_UNKNOWN
from ..generators.fields import choose_field_type
from ..models.domain import (
    FieldTestContext,
    FieldTestResult,
    SettingsVariant,
)
from ..models.domain import TemplateField
from ..models.runtime_protocols import ClientFactoryLike, SemaphoreLike, SimulationStageArgs
from ..utils.helpers import first_non_empty
from .simulation_parsing import (
    extract_alpha_id,
    extract_checks,
    extract_failed_checks,
    extract_pending_checks,
    is_submittable_from_checks,
    summarize_failure,
)
from .simulation_results import build_failure_result
from .simulation_stages import (
    PrecheckConfig,
    checksubmit_with_retry,
    create_simulation_with_retry,
    poll_simulation_with_retry,
    precheck_simulation_metrics,
    run_checksubmit_stage,
    run_simulation_create_stage,
    run_simulation_poll_stage,

)

logger = logging.getLogger(__name__)


def run_field_test(
    client: BrainClient,
    args: SimulationStageArgs,
    field: TemplateField,
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: SemaphoreLike | None = None,
) -> FieldTestResult:
    """执行单个候选表达式的 simulation / checksubmit 两阶段流程。"""
    if not expression or not expression.strip():
        raise ValueError("expression cannot be empty")
    if not template_name or not template_name.strip():
        raise ValueError("template_name cannot be empty")
    if "id" not in field.metadata:
        raise ValueError("field must contain 'id' key")
    if not settings_fingerprint:
        raise ValueError("settings_fingerprint cannot be empty")
    if not template_library_fingerprint:
        raise ValueError("template_library_fingerprint cannot be empty")

    ctx = FieldTestContext(
        field_id=str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
        field_type=choose_field_type(field),
        field_name=str(first_non_empty(field.get("name"), field.get("id"), SENTINEL_UNKNOWN)),
        template_name=template_name,
        template_family=str(first_non_empty(field.get("template_family"), "")),
        template_stage=str(first_non_empty(field.get("template_stage"), "")),
        template_role=str(first_non_empty(field.get("template_role"), "")),
        template_activation_scope=str(first_non_empty(field.get("template_activation_scope"), "")),
        expression=expression,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
    )

    logger.info(
        "[field] testing %s (%s) template=%s expression: %s",
        ctx.field_id,
        ctx.field_type,
        template_name,
        expression,
    )

    create_result = run_simulation_create_stage(
        ctx,
        client,
        args,
        simulation_settings=simulation_settings,
        create_semaphore=create_semaphore,
    )
    if isinstance(create_result, FieldTestResult):
        return create_result
    simulation_location, simulation_id = create_result

    poll_result = run_simulation_poll_stage(
        ctx,
        client,
        args,
        simulation_location=simulation_location,
        simulation_id=simulation_id,
    )
    if isinstance(poll_result, FieldTestResult):
        return poll_result
    alpha_id, simulation_result = poll_result

    check_result = run_checksubmit_stage(
        ctx,
        client,
        args,
        alpha_id=alpha_id,
        simulation_id=simulation_id,
        simulation_result=simulation_result,
    )
    if isinstance(check_result, FieldTestResult):
        return check_result
    submittable, message, failed_checks = check_result

    if submittable:
        logger.info(
            "[checksubmit] submittable alpha_id=%s simulation_id=%s simulation_location=%s",
            alpha_id,
            simulation_id,
            simulation_location,
        )

    result = ctx.success(
        simulation_id=simulation_id,
        alpha_id=alpha_id,
        submittable=submittable,
        submitted=False,
        message=message,
        status="simulated",
        failed_checks=failed_checks,
    )

    return result


def run_field_test_in_worker(
    client_factory: ClientFactoryLike,
    args: SimulationStageArgs,
    field: TemplateField,
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: SemaphoreLike | None = None,
) -> FieldTestResult:
    """工作线程入口，先解析线程本地客户端再执行测试。"""
    client = client_factory.get_client()
    return run_field_test(
        client,
        args,
        field,
        template_name,
        expression,
        settings_fingerprint,
        template_library_fingerprint,
        simulation_settings,
        create_semaphore,
    )


__all__ = [
    "PrecheckConfig",
    "build_failure_result",
    "checksubmit_with_retry",
    "create_simulation_with_retry",
    "extract_alpha_id",
    "extract_checks",
    "extract_failed_checks",
    "extract_pending_checks",
    "is_submittable_from_checks",
    "poll_simulation_with_retry",
    "precheck_simulation_metrics",
    "run_field_test",
    "run_field_test_in_worker",

    "summarize_failure",
]
