"""
模拟生命周期管理模块。

本模块保留 `alpha.core.simulation` 的兼容入口，主文件只负责字段测试编排，
解析、预检、阶段执行和结果构建细节已拆到辅助模块。
"""

from __future__ import annotations

from collections.abc import Callable
import logging

from ..api.client import BrainClient
from ..config.static_config import get_static_config
from ..generators.fields import choose_field_type
from ..models.domain import (
    FieldTestContext,
    FieldTestResult,
    SettingsVariant,
    TemplateField,
)
from ..models.domain_serializers import serialize_settings_variant
from ..models.runtime_config import SimulationStageConfig
from ..models.runtime_protocols import ClientFactoryLike, SemaphoreLike
from ..runtime.contexts import PendingFutureContext
from ..utils.helpers import first_non_empty
from .simulation_create import run_simulation_create_stage
from .simulation_parsing import (
    extract_simulation_metrics,
)
from .simulation_poll import run_simulation_poll_stage
from .submission_checks import run_check_submission_stage

logger = logging.getLogger(__name__)

SimulationCreatedCallback = Callable[[str, str], None]


def _complete_field_test_from_simulation(
    ctx: FieldTestContext,
    client: BrainClient,
    config: SimulationStageConfig,
    *,
    simulation_location: str,
    simulation_id: str,
    should_abort: Callable[[], bool] | None = None,
) -> FieldTestResult:
    """Poll an existing simulation and execute the remaining check stage."""
    poll_result = run_simulation_poll_stage(
        ctx,
        client,
        config,
        simulation_location=simulation_location,
        simulation_id=simulation_id,
        should_abort=should_abort,
    )
    if isinstance(poll_result, FieldTestResult):
        return poll_result
    alpha_id, simulation_result = poll_result
    ctx.metrics = extract_simulation_metrics(simulation_result)
    if should_abort is not None and should_abort():
        return ctx.failure(
            failed_stage="stopped",
            message="submission checks aborted because stop was requested",
            simulation_id=simulation_id,
            alpha_id=alpha_id,
            status=get_static_config().status_skipped,
        )

    check_result = run_check_submission_stage(
        ctx,
        client,
        config,
        alpha_id=alpha_id,
        simulation_id=simulation_id,
        simulation_result=simulation_result,
        should_abort=should_abort,
    )
    if isinstance(check_result, FieldTestResult):
        return check_result
    submittable, message, failed_checks = check_result

    if submittable:
        logger.info(
            "[check-submission] submittable alpha_id=%s simulation_id=%s simulation_location=%s",
            alpha_id,
            simulation_id,
            simulation_location,
        )

    return ctx.success(
        simulation_id=simulation_id,
        alpha_id=alpha_id,
        submittable=submittable,
        message=message,
        status="simulated",
        failed_checks=failed_checks,
        metrics=ctx.metrics,
    )


def run_field_test(
    client: BrainClient,
    config: SimulationStageConfig,
    field: TemplateField,
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: SemaphoreLike | None = None,
    should_abort: Callable[[], bool] | None = None,
    on_simulation_created: SimulationCreatedCallback | None = None,
) -> FieldTestResult:
    """执行单个候选表达式的 simulation / Check Submission 两阶段流程。"""
    if not expression or not expression.strip():
        raise ValueError("expression cannot be empty")
    if not template_name or not template_name.strip():
        raise ValueError("template_name cannot be empty")
    if not field.field_id.strip():
        raise ValueError("field_id cannot be empty")
    if not settings_fingerprint:
        raise ValueError("settings_fingerprint cannot be empty")
    if not template_library_fingerprint:
        raise ValueError("template_library_fingerprint cannot be empty")

    ctx = FieldTestContext(
        field_id=str(first_non_empty(field.field_id, get_static_config().sentinel_unknown)),
        field_type=choose_field_type(field),
        field_name=str(
            first_non_empty(field.field_name, field.field_id, get_static_config().sentinel_unknown)
        ),
        template_name=template_name,
        template_family=str(first_non_empty(field.metadata.get("template_family"), "")),
        template_stage=str(first_non_empty(field.metadata.get("template_stage"), "")),
        template_role=str(first_non_empty(field.metadata.get("template_role"), "")),
        template_activation_scope=str(
            first_non_empty(field.metadata.get("template_activation_scope"), "")
        ),
        policy_version=str(first_non_empty(field.metadata.get("policy_version"), "")),
        expression=expression,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        settings=(
            serialize_settings_variant(simulation_settings)
            if simulation_settings is not None
            else {}
        ),
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
        config,
        simulation_settings=simulation_settings,
        create_semaphore=create_semaphore,
        should_abort=should_abort,
    )
    if isinstance(create_result, FieldTestResult):
        return create_result
    simulation_location, simulation_id = create_result
    if on_simulation_created is not None:
        on_simulation_created(simulation_location, simulation_id)

    return _complete_field_test_from_simulation(
        ctx,
        client,
        config,
        simulation_location=simulation_location,
        simulation_id=simulation_id,
        should_abort=should_abort,
    )


def resume_field_test(
    client: BrainClient,
    config: SimulationStageConfig,
    pending: PendingFutureContext,
    template_library_fingerprint: str,
    should_abort: Callable[[], bool] | None = None,
) -> FieldTestResult:
    """Resume polling a previously created remote simulation."""
    if not pending.simulation_location:
        raise ValueError("resumable simulation must contain simulation_location")
    simulation_id = (
        pending.simulation_id or pending.simulation_location.rstrip("/").rsplit("/", 1)[-1]
    )
    ctx = FieldTestContext(
        field_id=pending.field_id,
        field_type=pending.field_type,
        field_name=pending.field_name,
        template_name=pending.template_name,
        template_family=pending.template_family,
        template_stage=pending.template_stage,
        template_role=pending.template_role,
        template_activation_scope=pending.template_activation_scope,
        policy_version=pending.policy_version,
        expression=pending.expression,
        settings_fingerprint=pending.settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        settings=dict(pending.settings),
    )
    logger.info(
        "[resume] continuing simulation_id=%s location=%s field=%s template=%s",
        simulation_id,
        pending.simulation_location,
        pending.field_id,
        pending.template_name,
    )
    return _complete_field_test_from_simulation(
        ctx,
        client,
        config,
        simulation_location=pending.simulation_location,
        simulation_id=simulation_id,
        should_abort=should_abort,
    )


def run_field_test_in_worker(
    client_factory: ClientFactoryLike,
    config: SimulationStageConfig,
    field: TemplateField,
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: SemaphoreLike | None = None,
    should_abort: Callable[[], bool] | None = None,
    on_simulation_created: SimulationCreatedCallback | None = None,
) -> FieldTestResult:
    """工作线程入口，先解析线程本地客户端再执行测试。"""
    client = client_factory.get_client(request_abort=should_abort)
    return run_field_test(
        client,
        config,
        field,
        template_name,
        expression,
        settings_fingerprint,
        template_library_fingerprint,
        simulation_settings,
        create_semaphore,
        should_abort,
        on_simulation_created,
    )


def resume_field_test_in_worker(
    client_factory: ClientFactoryLike,
    config: SimulationStageConfig,
    pending: PendingFutureContext,
    template_library_fingerprint: str,
    should_abort: Callable[[], bool] | None = None,
) -> FieldTestResult:
    """Worker entrypoint for resuming an existing remote simulation."""
    client = client_factory.get_client(request_abort=should_abort)
    return resume_field_test(
        client,
        config,
        pending,
        template_library_fingerprint,
        should_abort,
    )


__all__ = [
    "resume_field_test",
    "resume_field_test_in_worker",
    "run_field_test",
    "run_field_test_in_worker",
]
