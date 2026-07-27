"""Deterministic policy holdouts and evaluation summaries."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import math
from typing import Any

from ..models.domain import FieldTestResult

POLICY_ARM_ADAPTIVE = "adaptive"
POLICY_ARM_HOLDOUT = "holdout"
DEFAULT_MIN_FIELDS_PER_ARM = 20
WILSON_Z_95 = 1.959963984540054


def assign_policy_arm(
    *,
    dataset_id: str,
    field_id: str,
    policy_version: str,
    holdout_percent: int,
) -> str:
    """Assign a field deterministically so repeated runs keep the same arm."""
    bounded_percent = min(100, max(0, int(holdout_percent)))
    identity = f"{dataset_id}\0{field_id}\0{policy_version}".encode()
    bucket = int.from_bytes(hashlib.sha256(identity).digest()[:4], "big") % 100
    return POLICY_ARM_HOLDOUT if bucket < bounded_percent else POLICY_ARM_ADAPTIVE


def _wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    rate = successes / total
    z_squared = WILSON_Z_95**2
    denominator = 1 + z_squared / total
    center = (rate + z_squared / (2 * total)) / denominator
    margin = (
        WILSON_Z_95 * math.sqrt((rate * (1 - rate) + z_squared / (4 * total)) / total) / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _build_policy_comparisons(
    summaries: Sequence[dict[str, Any]],
    *,
    min_fields_per_arm: int,
) -> list[dict[str, Any]]:
    by_version: dict[str, dict[str, dict[str, Any]]] = {}
    for row in summaries:
        version = str(row["policy_version"])
        arm = str(row["policy_arm"])
        by_version.setdefault(version, {})[arm] = row

    comparisons: list[dict[str, Any]] = []
    for version, arms in sorted(by_version.items()):
        adaptive = arms.get(POLICY_ARM_ADAPTIVE)
        holdout = arms.get(POLICY_ARM_HOLDOUT)
        adaptive_fields = int(adaptive["fields_tested"]) if adaptive else 0
        holdout_fields = int(holdout["fields_tested"]) if holdout else 0
        adaptive_rate = float(adaptive["field_submittable_rate"]) if adaptive else 0.0
        holdout_rate = float(holdout["field_submittable_rate"]) if holdout else 0.0
        recommendation = "insufficient_data"
        eligible = adaptive_fields >= min_fields_per_arm and holdout_fields >= min_fields_per_arm
        if eligible and adaptive is not None and holdout is not None:
            adaptive_interval = adaptive["field_submittable_rate_ci95"]
            holdout_interval = holdout["field_submittable_rate_ci95"]
            if adaptive_interval[0] > holdout_interval[1]:
                recommendation = "promote"
            elif adaptive_interval[1] < holdout_interval[0]:
                recommendation = "rollback"
            else:
                recommendation = "hold"
        comparisons.append(
            {
                "policy_version": version,
                "adaptive_fields": adaptive_fields,
                "holdout_fields": holdout_fields,
                "minimum_fields_per_arm": min_fields_per_arm,
                "eligible": eligible,
                "field_submittable_rate_lift": adaptive_rate - holdout_rate,
                "recommendation": recommendation,
            }
        )
    return comparisons


def summarize_policy_evaluation(
    results: Sequence[FieldTestResult],
    *,
    min_fields_per_arm: int = DEFAULT_MIN_FIELDS_PER_ARM,
) -> dict[str, Any]:
    """Aggregate simulation diagnostics and field-level policy comparisons."""
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    field_outcomes: dict[tuple[str, str, str], dict[str, bool]] = {}
    for result in results:
        version = result.policy_version or "unversioned"
        arm = result.policy_arm or "unassigned"
        row = grouped.setdefault(
            (version, arm),
            {
                "policy_version": version,
                "policy_arm": arm,
                "tested": 0,
                "submittable": 0,
                "submitted": 0,
            },
        )
        row["tested"] += 1
        row["submittable"] += int(result.submittable is True)
        row["submitted"] += int(result.submitted)
        outcome = field_outcomes.setdefault(
            (version, arm, result.field_id),
            {"submittable": False, "submitted": False},
        )
        outcome["submittable"] = outcome["submittable"] or result.submittable is True
        outcome["submitted"] = outcome["submitted"] or bool(result.submitted)
    summaries: list[dict[str, Any]] = []
    for (version, arm), row in grouped.items():
        tested = int(row["tested"])
        row["submittable_rate"] = row["submittable"] / tested if tested else 0.0
        row["submitted_rate"] = row["submitted"] / tested if tested else 0.0
        outcomes = [
            outcome
            for (outcome_version, outcome_arm, _field_id), outcome in field_outcomes.items()
            if outcome_version == version and outcome_arm == arm
        ]
        fields_tested = len(outcomes)
        submittable_fields = sum(int(outcome["submittable"]) for outcome in outcomes)
        submitted_fields = sum(int(outcome["submitted"]) for outcome in outcomes)
        field_submittable_rate = submittable_fields / fields_tested if fields_tested else 0.0
        field_submitted_rate = submitted_fields / fields_tested if fields_tested else 0.0
        row.update(
            {
                "fields_tested": fields_tested,
                "submittable_fields": submittable_fields,
                "submitted_fields": submitted_fields,
                "field_submittable_rate": field_submittable_rate,
                "field_submitted_rate": field_submitted_rate,
                "field_submittable_rate_ci95": list(
                    _wilson_interval(submittable_fields, fields_tested)
                ),
                "field_submitted_rate_ci95": list(
                    _wilson_interval(submitted_fields, fields_tested)
                ),
            }
        )
        summaries.append(row)
    sorted_summaries = sorted(
        summaries,
        key=lambda item: (str(item["policy_version"]), str(item["policy_arm"])),
    )
    return {
        "evaluation_unit": "field",
        "confidence_level": 0.95,
        "minimum_fields_per_arm": max(1, int(min_fields_per_arm)),
        "groups": sorted_summaries,
        "comparisons": _build_policy_comparisons(
            sorted_summaries,
            min_fields_per_arm=max(1, int(min_fields_per_arm)),
        ),
    }
