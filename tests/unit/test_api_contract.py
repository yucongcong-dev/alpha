"""Brain API response contract regressions driven by recorded snapshots.

The response payloads come from tests/unit/fixtures/worldquant_api_snapshots.json,
which freezes representative WorldQuant BRAIN API shapes so a platform key
rename or state change fails loudly instead of silently degrading parsing. The
HTTP transport is still faked offline; the payloads it carries are the
snapshots.
"""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import Any

from alpha.api.alphas import BrainAlphasMixin
from alpha.api.fields import BrainFieldsMixin
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

_SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "worldquant_api_snapshots.json"
_SNAPSHOTS = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _snapshot(name: str) -> dict[str, Any]:
    return _SNAPSHOTS[name]


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def test_simulation_response_contract_lifecycle() -> None:
    """A completed Brain simulation response parses end to end."""
    completed = _snapshot("simulation_completed")
    pending, status, progress = simulation_payload_is_pending(completed)
    assert pending is False
    assert status == "COMPLETED"
    assert progress == "1.0"

    assert extract_alpha_id(completed) == "ALPHA_ID_CONTRACT_001"

    assert extract_failed_checks(completed) == []
    all_checks = [
        parse_failed_check(check) for check in extract_checks(completed) if isinstance(check, dict)
    ]
    assert len(all_checks) == 6
    assert is_submittable_from_checks(all_checks) is True

    metrics = extract_simulation_metrics(completed)
    assert metrics["sharpe"] == 2.13
    assert metrics["fitness"] == 1.41
    assert metrics["turnover"] == 0.23
    assert "checks" not in metrics

    # A PENDING poll response stays in the active waiting set.
    pending_response = _snapshot("simulation_pending")
    assert simulation_payload_is_pending(pending_response)[0] is True
    assert summarize_failure(pending_response) != ""

    # A terminal failure surfaces the platform detail message.
    error_response = _snapshot("simulation_error")
    assert summarize_failure(error_response) == "Expression is invalid: division by zero"

    # A FAIL check survives extraction and blocks submittability.
    failing_response = _snapshot("simulation_failing")
    failed = extract_failed_checks(failing_response)
    assert [check.name for check in failed] == ["IS_SHARPE"]
    assert is_submittable_from_checks(failed) is False
    assert summarize_failure(failing_response) == "failed checks: IS_SHARPE"
    assert extract_pending_checks(failing_response) == []


class _FakeAlphasClient(BrainAlphasMixin):
    def __init__(self, responses: Iterable[tuple[int, dict[str, str], bytes]]) -> None:
        self.responses = iter(responses)
        self.requests: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **kwargs: Any):
        self.requests.append((method, url))
        return next(self.responses)


class _FakeFieldsClient(BrainFieldsMixin):
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = iter(pages)
        self.calls: list[tuple[int, int]] = []

    def _fetch_dataset_fields_page(
        self,
        dataset_id: str,
        limit: int,
        offset: int,
        *,
        region: str,
        universe: str,
        instrument_type: str,
        delay: int,
    ) -> dict[str, Any]:
        self.calls.append((limit, offset))
        return next(self.pages)


def test_check_submission_response_contract() -> None:
    """A real check-submission response parses into pending/failed/submittable."""
    client = _FakeAlphasClient([(200, {}, _json_bytes(_snapshot("check_submission")))])

    payload = client.check_alpha_submission("ALPHA_ID_CONTRACT_003")
    assert client.requests == [
        ("GET", "https://api.worldquantbrain.com/alphas/ALPHA_ID_CONTRACT_003/check")
    ]

    checks = [parse_failed_check(c) for c in extract_checks(payload) if isinstance(c, dict)]
    failed = [c for c in checks if str(c.result or "").upper() == "FAIL"]
    pending = [c for c in checks if str(c.result or "").upper() == "PENDING"]
    assert len(checks) == 4
    assert [c.name for c in failed] == ["IS_CONCENTRATED_WEIGHT"]
    assert [c.name for c in pending] == ["IS_TURNOVER"]
    assert extract_pending_checks(payload)[0].name == "IS_TURNOVER"


def test_fields_pagination_contract() -> None:
    """Recorded data-fields pages paginate into the full field list."""
    client = _FakeFieldsClient(_snapshot("fields_pages"))

    rows = client.fetch_dataset_fields(
        "fundamental6",
        limit=0,
        offset=0,
        page_size=2,
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
    )

    assert [row["id"] for row in rows] == ["f1", "f2", "f3"]
    assert rows[0]["fieldType"] == "MATRIX"
    assert rows[1]["mnemonic"] == "market_cap"
    assert client.calls == [(2, 0), (2, 2)]


def test_rate_limit_retry_recovers_after_transient_429(monkeypatch) -> None:
    """A 429 with Retry-After is retried and the request eventually succeeds."""
    from alpha.api.client import BrainClient

    client = BrainClient("user@example.com", "secret")
    responses = iter(
        [
            (429, {"Retry-After": "3"}, b'{"detail": "too fast"}'),
            (200, {}, b"ok"),
        ]
    )
    waits: list[float] = []
    monkeypatch.setattr(client, "raw_request", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(
        "alpha.api.session.wait_seconds",
        lambda seconds, reason, **_kwargs: waits.append(seconds),
    )

    status, _, content = client.request("GET", "https://example.test", expected={200}, retries=2)

    assert (status, content) == (200, b"ok")
    assert waits == [6.0]
