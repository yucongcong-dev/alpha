"""Refresh unresolved submission checks before scheduling new simulations."""

from __future__ import annotations

from dataclasses import replace
import logging

from ..api.client import BrainClient
from ..core.simulation_stages import checksubmit_with_retry
from ..models.domain import FieldTestResult
from ..models.result_predicates import has_pending_checks

logger = logging.getLogger(__name__)


def refresh_pending_check_results(
    client: BrainClient,
    results: list[FieldTestResult],
    *,
    retries: int,
) -> tuple[list[FieldTestResult], int]:
    """Resolve historical PENDING checks without recreating their simulations."""
    refreshed_results = list(results)
    refreshed_count = 0
    for index, result in enumerate(results):
        if not has_pending_checks(result) or not result.alpha_id:
            continue
        try:
            submittable, message, failed_checks = checksubmit_with_retry(
                client,
                result.alpha_id,
                retries,
            )
        except Exception as exc:
            logger.warning(
                "[checksubmit-resume] failed alpha_id=%s field=%s template=%s: %s",
                result.alpha_id,
                result.field_id,
                result.template_name,
                exc,
            )
            continue
        if submittable is None:
            logger.info(
                "[checksubmit-resume] still pending alpha_id=%s field=%s template=%s",
                result.alpha_id,
                result.field_id,
                result.template_name,
            )
            continue
        refreshed_results[index] = replace(
            result,
            submittable=submittable,
            message=message,
            failed_stage=None,
            failed_checks=failed_checks,
        )
        refreshed_count += 1
        logger.info(
            "[checksubmit-resume] resolved alpha_id=%s field=%s template=%s submittable=%s",
            result.alpha_id,
            result.field_id,
            result.template_name,
            submittable,
        )
    return refreshed_results, refreshed_count
