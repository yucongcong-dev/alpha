"""Realistic Brain API simulation-response contract regression.

Freezes one representative poll response shape (as observed on the WorldQuant
BRAIN simulate API) and pushes it through the full local parsing pipeline. If
the platform renames a key or changes a state value, this test fails loudly
instead of silently degrading parsing.
"""

from __future__ import annotations

from alpha.api.payloads import simulation_payload_is_pending
from alpha.core.simulation_parsing import (
    extract_alpha_id,
    extract_checks,
    extract_failed_checks,
    extract_pending_checks,
    extract_simulation_metrics,
    is_submittable_from_checks,
    summarize_failure,
)
from alpha.models.domain_parsers import parse_failed_check

COMPLETED_RESPONSE = {
    "status": "COMPLETED",
    "progress": "1.0",
    "alpha": "ALPHA_ID_CONTRACT_001",
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "neutralization": "SUBINDUSTRY",
    "decay": 4,
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "OFF",
    "is": {
        "sharpe": 2.13,
        "fitness": 1.41,
        "turnover": 0.23,
        "returns": 0.042,
        "volatility": 0.021,
        "maxdrawdown": -0.147,
        "checks": [
            {"name": "IS_SHARPE", "value": 2.13, "limit": 1.25, "result": "PASS"},
            {"name": "IS_FITNESS", "value": 1.41, "limit": 1.0, "result": "PASS"},
            {"name": "IS_TURNOVER", "value": 0.23, "limit": 0.70, "result": "PASS"},
            {"name": "IS_LOW_SUB_UNIVERSE_SHARPE", "value": 1.12, "limit": 1.0, "result": "PASS"},
            {"name": "IS_CONCENTRATED_WEIGHT", "value": 0.06, "limit": 0.10, "result": "PASS"},
            {"name": "IS_HIGH_TURNOVER", "value": 0.23, "limit": 0.70, "result": "PASS"},
        ],
    },
    "os": {"sharpe": 1.02, "fitness": 0.74},
}


def test_simulation_response_contract_lifecycle() -> None:
    """A completed Brain simulation response parses end to end."""
    pending, status, progress = simulation_payload_is_pending(COMPLETED_RESPONSE)
    assert pending is False
    assert status == "COMPLETED"
    assert progress == "1.0"

    assert extract_alpha_id(COMPLETED_RESPONSE) == "ALPHA_ID_CONTRACT_001"

    assert extract_failed_checks(COMPLETED_RESPONSE) == []
    all_checks = [
        parse_failed_check(check)
        for check in extract_checks(COMPLETED_RESPONSE)
        if isinstance(check, dict)
    ]
    assert len(all_checks) == 6
    assert is_submittable_from_checks(all_checks) is True

    metrics = extract_simulation_metrics(COMPLETED_RESPONSE)
    assert metrics["sharpe"] == 2.13
    assert metrics["fitness"] == 1.41
    assert metrics["turnover"] == 0.23
    assert "checks" not in metrics

    # A PENDING poll response stays in the active waiting set.
    pending_response = {
        "status": "PENDING",
        "progress": "0.0",
        "stage": "Queued",
        "queue_position": 3,
    }
    assert simulation_payload_is_pending(pending_response)[0] is True
    assert summarize_failure(pending_response) != ""

    # A terminal failure surfaces the platform detail message.
    failed_response = {
        "status": "ERROR",
        "detail": "Expression is invalid: division by zero",
    }
    assert summarize_failure(failed_response) == "Expression is invalid: division by zero"

    # A FAIL check survives extraction and blocks submittability.
    failing_response = {
        "status": "COMPLETED",
        "alpha": "ALPHA_ID_CONTRACT_002",
        "is": {
            "checks": [
                {"name": "IS_SHARPE", "value": 0.9, "limit": 1.25, "result": "FAIL"},
                {"name": "IS_FITNESS", "value": 0.8, "limit": 1.0, "result": "PASS"},
            ]
        },
    }
    failed = extract_failed_checks(failing_response)
    assert [check.name for check in failed] == ["IS_SHARPE"]
    assert is_submittable_from_checks(failed) is False
    assert summarize_failure(failing_response) == "failed checks: IS_SHARPE"
    assert extract_pending_checks(failing_response) == []
