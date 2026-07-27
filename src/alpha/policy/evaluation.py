"""Deterministic policy holdouts and evaluation summaries."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
from typing import Any

from ..models.domain import FieldTestResult

POLICY_ARM_ADAPTIVE = "adaptive"
POLICY_ARM_HOLDOUT = "holdout"


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


def summarize_policy_evaluation(results: Sequence[FieldTestResult]) -> dict[str, Any]:
    """Aggregate comparable outcome rates by policy version and experiment arm."""
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
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
    summaries: list[dict[str, Any]] = []
    for row in grouped.values():
        tested = int(row["tested"])
        row["submittable_rate"] = row["submittable"] / tested if tested else 0.0
        row["submitted_rate"] = row["submitted"] / tested if tested else 0.0
        summaries.append(row)
    return {
        "groups": sorted(
            summaries,
            key=lambda item: (str(item["policy_version"]), str(item["policy_arm"])),
        )
    }
