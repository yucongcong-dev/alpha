"""
模拟生命周期模块单元测试（pytest 风格）

测试 alpha.core.simulation 中的核心函数，覆盖边界条件和异常路径。
使用 conftest.py 中的共享 fixtures 消除重复 setup。
"""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from alpha.config.constants import STATUS_SKIPPED
from alpha.core.simulation import (
    resume_field_test,
    resume_field_test_in_worker,
    run_field_test,
    run_field_test_in_worker,
)
from alpha.core.simulation_parsing import (
    extract_alpha_id,
    extract_checks,
    extract_failed_checks,
    extract_pending_checks,
    is_submittable_from_checks,
    summarize_failure,
)
from alpha.core.simulation_precheck import PrecheckConfig, precheck_simulation_metrics
from alpha.core.simulation_results import build_failure_result
from alpha.core.simulation_stages import (
    check_submission_with_retry,
    run_check_submission_stage,
    run_simulation_create_stage,
    run_simulation_poll_stage,
)
from alpha.exceptions import BrainHTTPError, BrainStopRequested, BrainTransientError
from alpha.models.domain import (
    FailedCheck,
    FieldTestContext,
    FieldTestResult,
    SettingsVariant,
    TemplateField,
)
from alpha.models.runtime import PendingFutureContext
from tests.conftest import MockArgs

# ============================================================================
# extract_alpha_id 测试
# ============================================================================


class TestExtractAlphaId:
    """extract_alpha_id 函数测试"""

    # ---- 顶层字段提取 ----
    def test_direct_alpha_field(self) -> None:
        assert extract_alpha_id({"alpha": "alpha_123"}) == "alpha_123"

    def test_alphaId_field(self) -> None:  # noqa: N802
        assert extract_alpha_id({"alphaId": "alpha_456"}) == "alpha_456"

    def test_id_with_type_ALPHA(self) -> None:  # noqa: N802
        assert extract_alpha_id({"type": "ALPHA", "id": "alpha_789"}) == "alpha_789"

    def test_id_not_alpha_type(self) -> None:
        assert extract_alpha_id({"type": "SIMULATION", "id": "sim_123"}) is None

    # ---- 嵌套字典提取 ----
    def test_nested_alpha_dict(self) -> None:
        assert extract_alpha_id({"alpha": {"id": "alpha_nested"}}) == "alpha_nested"

    def test_nested_alpha_alpha_field(self) -> None:
        assert extract_alpha_id({"alpha": {"alpha": "alpha_inner"}}) == "alpha_inner"

    # ---- location URL 提取 ----
    def test_location_url_extraction(self) -> None:
        assert extract_alpha_id({"location": "/alphas/alpha_url"}) == "alpha_url"

    def test_location_url_with_suffix(self) -> None:
        assert (
            extract_alpha_id(
                {"location": "https://api.worldquantbrain.com/alphas/alpha_full_path/details"}
            )
            == "alpha_full_path"
        )

    # ---- 空/缺失字段 ----
    def test_empty_payload(self) -> None:
        assert extract_alpha_id({}) is None

    def test_no_alpha_field(self) -> None:
        assert extract_alpha_id({"status": "COMPLETED"}) is None

    def test_alpha_empty_string_skipped(self) -> None:
        assert extract_alpha_id({"alpha": ""}) is None

    # ---- children 递归 ----
    def test_children_recursive(self) -> None:
        payload = {
            "type": "FOLDER",
            "children": [{"type": "ALPHA", "id": "alpha_from_child"}],
        }
        assert extract_alpha_id(payload) == "alpha_from_child"

    def test_children_nested_deep(self) -> None:
        payload = {"children": [{"children": [{"alpha": "alpha_deep"}]}]}
        assert extract_alpha_id(payload) == "alpha_deep"

    def test_children_non_dict_skipped(self) -> None:
        payload = {"children": ["not_a_dict", {"alpha": "alpha_skip_test"}]}
        assert extract_alpha_id(payload) == "alpha_skip_test"

    # ---- 优先级 ----
    def test_priority_order_alpha_over_location(self) -> None:
        assert (
            extract_alpha_id({"alpha": "alpha_first", "location": "/alphas/alpha_second"})
            == "alpha_first"
        )


# ============================================================================
# extract_checks 测试
# ============================================================================


class TestExtractChecks:
    """extract_checks 函数测试"""

    def test_is_checks_path(self) -> None:
        payload = {"is": {"checks": [{"name": "LOW_SHARPE", "result": "FAIL"}]}}
        assert extract_checks(payload) == [{"name": "LOW_SHARPE", "result": "FAIL"}]

    def test_top_level_checks(self) -> None:
        payload = {"checks": [{"name": "LOW_FITNESS", "result": "PASS"}]}
        assert extract_checks(payload) == [{"name": "LOW_FITNESS", "result": "PASS"}]

    def test_is_checks_over_top_level(self) -> None:
        payload = {
            "is": {"checks": [{"name": "NESTED", "result": "FAIL"}]},
            "checks": [{"name": "TOP", "result": "PASS"}],
        }
        assert extract_checks(payload) == [{"name": "NESTED", "result": "FAIL"}]

    def test_empty_payload(self) -> None:
        assert extract_checks({}) == []

    def test_is_section_not_dict(self) -> None:
        payload = {"is": "not_a_dict", "checks": [{"name": "FALLBACK"}]}
        assert extract_checks(payload) == [{"name": "FALLBACK"}]

    def test_checks_not_list(self) -> None:
        assert extract_checks({"checks": "not_a_list"}) == []

    def test_is_checks_not_list(self) -> None:
        payload = {"is": {"checks": "not_list"}, "checks": [{"name": "FALLBACK2"}]}
        assert extract_checks(payload) == [{"name": "FALLBACK2"}]


# ============================================================================
# extract_failed_checks 测试
# ============================================================================


class TestExtractFailedChecks:
    """extract_failed_checks 函数测试"""

    def test_only_failed_checks(self) -> None:
        payload = {
            "checks": [
                {"name": "LOW_SHARPE", "result": "FAIL", "value": 0.8, "limit": 1.0},
                {"name": "LOW_FITNESS", "result": "PASS", "value": 1.2, "limit": 1.0},
            ]
        }
        result = extract_failed_checks(payload)
        assert len(result) == 1
        assert result[0].name == "LOW_SHARPE"

    def test_all_pass(self) -> None:
        payload = {"checks": [{"name": "LOW_SHARPE", "result": "PASS", "value": 1.5, "limit": 1.0}]}
        assert extract_failed_checks(payload) == []

    def test_case_insensitive_fail(self) -> None:
        payload = {"checks": [{"name": "TEST", "result": "fail", "value": 0.5, "limit": 1.0}]}
        result = extract_failed_checks(payload)
        assert len(result) == 1

    def test_uses_threshold_when_no_limit(self) -> None:
        payload = {"checks": [{"name": "TEST", "result": "FAIL", "value": 0.5, "threshold": 1.0}]}
        result = extract_failed_checks(payload)
        assert result[0].limit == 1.0

    def test_limit_over_threshold(self) -> None:
        payload = {
            "checks": [
                {"name": "TEST", "result": "FAIL", "value": 0.5, "limit": 2.0, "threshold": 1.0}
            ]
        }
        result = extract_failed_checks(payload)
        assert result[0].limit == 2.0

    def test_no_result_field(self) -> None:
        assert extract_failed_checks({"checks": [{"name": "TEST"}]}) == []

    def test_empty_checks_payload(self) -> None:
        """无 checks 字段的 payload 返回空列表。"""
        assert extract_failed_checks({"status": "OK"}) == []


class TestExtractPendingChecks:
    """extract_pending_checks 函数测试"""

    def test_only_pending_checks(self) -> None:
        payload = {
            "checks": [
                {"name": "SELF_CORRELATION", "result": "PENDING"},
                {"name": "LOW_SHARPE", "result": "PASS", "value": 1.3, "limit": 1.25},
            ]
        }
        result = extract_pending_checks(payload)
        assert len(result) == 1
        assert result[0].name == "SELF_CORRELATION"
        assert result[0].result == "PENDING"


# ============================================================================
# is_submittable_from_checks 测试
# ============================================================================


class TestIsSubmittableFromChecks:
    """is_submittable_from_checks 函数测试"""

    def test_all_pass(self) -> None:
        assert is_submittable_from_checks([FailedCheck(name="LOW_SHARPE", result="PASS")]) is True

    def test_any_fail(self) -> None:
        assert (
            is_submittable_from_checks(
                [
                    FailedCheck(name="LOW_SHARPE", result="PASS"),
                    FailedCheck(name="LOW_FITNESS", result="FAIL"),
                ]
            )
            is False
        )

    def test_pending_is_unresolved(self) -> None:
        assert (
            is_submittable_from_checks([FailedCheck(name="SELF_CORRELATION", result="PENDING")])
            is None
        )

    def test_pending_takes_precedence_over_failure(self) -> None:
        assert (
            is_submittable_from_checks(
                [
                    FailedCheck(name="LOW_FITNESS", result="FAIL"),
                    FailedCheck(name="SELF_CORRELATION", result="PENDING"),
                ]
            )
            is None
        )


class TestCheckSubmissionWithRetry:
    """check_submission_with_retry 测试"""

    def test_all_pass(self, monkeypatch) -> None:
        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                return {"is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}}

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", lambda *a, **k: a[2]())

        result = check_submission_with_retry(
            DummyClient(),
            "alpha_1",
            retries=3,
        )

        assert result == (True, "checks passed", [])

    def test_checks_failed(self, monkeypatch) -> None:
        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                return {
                    "is": {
                        "checks": [
                            {
                                "name": "SELF_CORRELATION",
                                "result": "FAIL",
                                "value": 0.91,
                                "limit": 0.7,
                            }
                        ]
                    }
                }

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", lambda *a, **k: a[2]())

        result = check_submission_with_retry(
            DummyClient(),
            "alpha_1",
            retries=3,
        )

        assert result == (
            False,
            "checks failed",
            [FailedCheck(name="SELF_CORRELATION", result="FAIL", value=0.91, limit=0.7)],
        )

    def test_failure_waits_for_unrelated_pending_checks(self, monkeypatch) -> None:
        calls = 0

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                nonlocal calls
                calls += 1
                return {
                    "is": {
                        "checks": [
                            {
                                "name": "LOW_FITNESS",
                                "result": "FAIL",
                                "value": 0.9,
                                "limit": 1.0,
                            },
                            {"name": "SELF_CORRELATION", "result": "PENDING"},
                        ]
                    }
                }

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", lambda *a, **k: a[2]())
        monkeypatch.setattr("alpha.core.simulation_stages.wait_seconds", lambda *_a, **_k: None)

        result = check_submission_with_retry(DummyClient(), "alpha_1", retries=3)

        assert calls == 3
        assert result == (
            None,
            "checks pending",
            [
                FailedCheck(name="LOW_FITNESS", result="FAIL", value=0.9, limit=1.0),
                FailedCheck(name="SELF_CORRELATION", result="PENDING"),
            ],
        )

    def test_pending_checks_are_polled_until_terminal(self, monkeypatch) -> None:
        responses = iter(
            [
                {"is": {"checks": [{"name": "SELF_CORRELATION", "result": "PENDING"}]}},
                {"is": {"checks": [{"name": "SELF_CORRELATION", "result": "PASS"}]}},
            ]
        )
        waits: list[str] = []
        transport_attempts: list[int] = []

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                return next(responses)

        def _retry(_name, attempts, operation, **_kwargs):
            transport_attempts.append(attempts)
            return operation()

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", _retry)
        monkeypatch.setattr(
            "alpha.core.simulation_stages.wait_seconds",
            lambda _seconds, reason, **_kwargs: waits.append(reason),
        )

        result = check_submission_with_retry(DummyClient(), "alpha_1", retries=3)

        assert result == (True, "checks passed", [])
        assert waits == ["waiting for submission checks for alpha alpha_1"]
        assert transport_attempts == [2, 2]

    def test_api_failure_remains_unresolved(self, monkeypatch) -> None:
        transport_attempts: list[int] = []
        waits: list[str] = []

        def _retry(_name, attempts, _operation, **_kwargs):
            transport_attempts.append(attempts)
            raise BrainTransientError("network unavailable")

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", _retry)
        monkeypatch.setattr(
            "alpha.core.simulation_stages.wait_seconds",
            lambda _seconds, reason, **_kwargs: waits.append(reason),
        )

        result = check_submission_with_retry(object(), "alpha_1", retries=2)

        assert result == (None, "checks unavailable", [])
        assert transport_attempts == [2, 2]
        assert waits == ["waiting for submission checks for alpha alpha_1"]

    def test_permanent_http_failure_is_not_left_pending(self, monkeypatch) -> None:
        def _retry(*_args, **_kwargs):
            raise BrainHTTPError("GET /alphas/missing/check failed: 404", status=404)

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", _retry)

        with pytest.raises(BrainHTTPError) as exc_info:
            check_submission_with_retry(object(), "missing", retries=3)

        assert exc_info.value.status == 404

    def test_transient_http_failure_remains_unresolved(self, monkeypatch) -> None:
        def _retry(*_args, **_kwargs):
            raise BrainHTTPError("GET /alphas/a/check failed: 503", status=503)

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", _retry)
        monkeypatch.setattr("alpha.core.simulation_stages.wait_seconds", lambda *_a, **_k: None)

        assert check_submission_with_retry(object(), "a", retries=1) == (
            None,
            "checks unavailable",
            [],
        )

    def test_unavailable_checks_are_polled_until_available(self, monkeypatch) -> None:
        responses = iter(
            [
                {},
                {"is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}},
            ]
        )
        waits: list[str] = []

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                return next(responses)

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", lambda *a, **k: a[2]())
        monkeypatch.setattr(
            "alpha.core.simulation_stages.wait_seconds",
            lambda _seconds, reason, **_kwargs: waits.append(reason),
        )

        result = check_submission_with_retry(DummyClient(), "alpha_1", retries=3)

        assert result == (True, "checks passed", [])
        assert waits == ["waiting for submission checks for alpha alpha_1"]

    def test_unavailable_checks_stop_after_retry_budget(self, monkeypatch) -> None:
        calls = 0

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                nonlocal calls
                calls += 1
                return {}

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", lambda *a, **k: a[2]())
        monkeypatch.setattr("alpha.core.simulation_stages.wait_seconds", lambda *_a, **_k: None)

        result = check_submission_with_retry(DummyClient(), "alpha_1", retries=2)

        assert calls == 2
        assert result == (None, "checks unavailable", [])

    def test_pending_checks_stop_after_retry_budget(self, monkeypatch) -> None:
        calls = 0

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                nonlocal calls
                calls += 1
                return {"is": {"checks": [{"name": "SELF_CORRELATION", "result": "PENDING"}]}}

        monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", lambda *a, **k: a[2]())
        monkeypatch.setattr("alpha.core.simulation_stages.wait_seconds", lambda *_a, **_k: None)

        result = check_submission_with_retry(DummyClient(), "alpha_1", retries=2)

        assert calls == 2
        assert result == (
            None,
            "checks pending",
            [FailedCheck(name="SELF_CORRELATION", result="PENDING")],
        )

    def test_empty_list(self) -> None:
        assert is_submittable_from_checks([]) is None

    def test_case_insensitive(self) -> None:
        assert is_submittable_from_checks([FailedCheck(name="LOW_SHARPE", result="fail")]) is False

    def test_multiple_fail_first_wins(self) -> None:
        assert (
            is_submittable_from_checks(
                [
                    FailedCheck(name="A", result="FAIL"),
                    FailedCheck(name="B", result="PASS"),
                ]
            )
            is False
        )

    def test_missing_result_field_is_unresolved(self) -> None:
        """缺少 result 字段时不能推断检查已经通过。"""
        assert (
            is_submittable_from_checks(
                [
                    FailedCheck(name="A", result="PASS"),
                    FailedCheck(name="B", result=None),  # no result field
                ]
            )
            is None
        )

    def test_unknown_result_is_unresolved(self) -> None:
        assert is_submittable_from_checks([FailedCheck(name="A", result="UNKNOWN")]) is None


# ============================================================================
# summarize_failure 测试
# ============================================================================


class TestSummarizeFailure:
    """summarize_failure 函数测试"""

    # ---- 优先级链 ----
    def test_detail_field(self) -> None:
        assert summarize_failure({"detail": "Invalid expression"}) == "Invalid expression"

    def test_detail_preferred_over_message(self) -> None:
        assert summarize_failure({"detail": "A", "message": "B"}) == "A"

    def test_message_when_no_detail(self) -> None:
        assert summarize_failure({"message": "B"}) == "B"

    def test_error_fallback(self) -> None:
        assert summarize_failure({"error": "Something wrong"}) == "Something wrong"


def test_precheck_simulation_metrics_loads_runtime_defaults(monkeypatch) -> None:
    payload = {"is": {"sharpe": 0.8, "fitness": 0.9, "turnover": 0.05, "maxWeight": 0.02}}

    monkeypatch.setattr(
        "alpha.core.simulation_precheck.build_default_submit_precheck_config",
        lambda: PrecheckConfig(
            min_sharpe=1.0,
            min_fitness=1.0,
            min_turnover=0.01,
            max_turnover=0.7,
            max_weight=0.01,
        ),
    )

    passed, _reason, failures = precheck_simulation_metrics(payload)

    assert passed is False
    assert {item["name"] for item in failures} == {
        "LOW_SHARPE",
        "LOW_FITNESS",
        "CONCENTRATED_WEIGHT",
    }


def test_precheck_simulation_metrics_preserves_explicit_thresholds(monkeypatch) -> None:
    payload = {"is": {"sharpe": 0.8, "fitness": 1.2, "turnover": 0.05, "maxWeight": 0.02}}

    monkeypatch.setattr(
        "alpha.core.simulation_precheck.build_default_submit_precheck_config",
        lambda: PrecheckConfig(
            min_sharpe=5.0,
            min_fitness=5.0,
            min_turnover=5.0,
            max_turnover=5.0,
            max_weight=5.0,
        ),
    )

    passed, _reason, failures = precheck_simulation_metrics(
        payload,
        min_sharpe=0.5,
        min_fitness=1.0,
        min_turnover=0.01,
        max_turnover=0.7,
        max_weight=0.01,
    )

    assert passed is False
    assert {item["name"] for item in failures} == {"CONCENTRATED_WEIGHT"}

    # ---- 失败检查摘要 ----
    def test_failed_checks_summary(self) -> None:
        assert (
            summarize_failure(
                {
                    "checks": [
                        {"name": "LOW_SHARPE", "result": "FAIL"},
                        {"name": "LOW_FITNESS", "result": "FAIL"},
                    ]
                }
            )
            == "failed checks: LOW_SHARPE, LOW_FITNESS"
        )

    def test_failed_checks_capped_at_5(self) -> None:
        checks = [{"name": f"CHECK_{i}", "result": "FAIL"} for i in range(10)]
        result = summarize_failure({"checks": checks})
        for i in range(5):
            assert f"CHECK_{i}" in result
        assert "CHECK_5" not in result
        assert "CHECK_9" not in result

    def test_mixed_pass_fail_checks(self) -> None:
        """混合 PASS/FAIL 时只列出 FAIL 的检查项。"""
        result = summarize_failure(
            {
                "checks": [
                    {"name": "LOW_SHARPE", "result": "FAIL"},
                    {"name": "LOW_FITNESS", "result": "PASS"},
                ]
            }
        )
        assert "LOW_SHARPE" in result
        assert "LOW_FITNESS" not in result

    # ---- 回退行为 ----
    def test_empty_payload_returns_json_dump(self) -> None:
        assert summarize_failure({}) == "{}"

    def test_truncation_at_300(self) -> None:
        """JSON 回退路径：内容截断为 300 字符。"""
        payload = {"raw": "x" * 500}
        result = summarize_failure(payload)
        assert len(result) <= 300

    def test_none_fields_skipped(self) -> None:
        payload = {"detail": None, "message": None, "error": "Real error"}
        assert summarize_failure(payload) == "Real error"

    def test_unknown_check_name_defaults(self) -> None:
        """无 name 字段的检查项使用 UNKNOWN 替代。"""
        result = summarize_failure({"checks": [{"result": "FAIL"}]})
        assert "UNKNOWN" in result


# ============================================================================
# build_failure_result 测试
# ============================================================================


class TestBuildFailureResult:
    """build_failure_result 函数测试"""

    def test_basic_failure(self) -> None:
        result = build_failure_result(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="ts_mean_20",
            simulation_id=None,
            alpha_id=None,
            expression="rank(sales)",
            settings_fingerprint="abc",
            template_library_fingerprint="def",
            failed_stage="simulation",
            message="Network error",
        )
        assert isinstance(result, FieldTestResult)
        assert result.field_id == "sales"
        assert result.status == "error"
        assert result.submittable is False
        assert result.submitted is False
        assert result.failed_stage == "simulation"

    def test_failure_with_failed_checks(self) -> None:
        checks = [{"name": "LOW_SHARPE", "value": 0.8, "limit": 1.0}]
        result = build_failure_result(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="test",
            simulation_id="sim_1",
            alpha_id="alpha_1",
            expression="rank(sales)",
            settings_fingerprint="abc",
            template_library_fingerprint="def",
            failed_stage="check_submission",
            message="checks failed",
            status="simulation_failed",
            failed_checks=checks,
        )
        assert result.failed_checks == [FailedCheck(name="LOW_SHARPE", value=0.8, limit=1.0)]
        assert result.simulation_id == "sim_1"
        assert result.alpha_id == "alpha_1"
        assert result.status == "simulation_failed"

    def test_default_status_is_error(self) -> None:
        result = build_failure_result(
            field_id="x",
            field_type="VECTOR",
            field_name="x",
            template_name="x",
            simulation_id=None,
            alpha_id=None,
            expression="x",
            settings_fingerprint="x",
            template_library_fingerprint="x",
            failed_stage="worker",
            message="x",
        )
        assert result.status == "error"

    def test_all_fingerprints_preserved(self) -> None:
        """验证所有指纹字段在失败结果中保持。"""
        result = build_failure_result(
            field_id="f1",
            field_type="MATRIX",
            field_name="f1",
            template_name="t1",
            simulation_id=None,
            alpha_id=None,
            expression="e1",
            settings_fingerprint="s_fp",
            template_library_fingerprint="tl_fp",
            failed_stage="simulation",
            message="err",
        )
        assert result.settings_fingerprint == "s_fp"
        assert result.template_library_fingerprint == "tl_fp"
        assert result.expression == "e1"


# ============================================================================
# FieldTestContext 测试
# ============================================================================


class TestFieldTestContext:
    """FieldTestContext 数据类测试"""

    def test_failure_method(self, basic_test_context: FieldTestContext) -> None:
        result = basic_test_context.failure(failed_stage="simulation", message="error msg")
        assert result.field_id == "sales"
        assert result.submittable is False
        assert result.failed_stage == "simulation"

    def test_success_method(self, basic_test_context: FieldTestContext) -> None:
        result = basic_test_context.success(
            simulation_id="sim_1",
            alpha_id="alpha_1",
            submittable=True,
            submitted=False,
            message="checks passed",
            status="simulated",
        )
        assert result.field_id == "sales"
        assert result.submittable is True
        assert result.submitted is False
        assert result.status == "simulated"

    def test_failure_with_optional_fields(self, minimal_test_context: FieldTestContext) -> None:
        result = minimal_test_context.failure(
            failed_stage="check_submission",
            message="err",
            simulation_id="sim_1",
            alpha_id="alpha_1",
            status="check_submission_failed",
        )
        assert result.simulation_id == "sim_1"
        assert result.alpha_id == "alpha_1"
        assert result.status == "check_submission_failed"

    def test_failure_default_status_is_error(self, minimal_test_context: FieldTestContext) -> None:
        result = minimal_test_context.failure(failed_stage="simulation", message="err")
        assert result.status == "error"

    def test_success_default_status_is_simulated(
        self, minimal_test_context: FieldTestContext
    ) -> None:
        result = minimal_test_context.success(
            simulation_id="s1",
            alpha_id="a1",
            submittable=True,
            submitted=False,
            message="ok",
        )
        assert result.status == "simulated"

    def test_failure_with_failed_checks(self, basic_test_context: FieldTestContext) -> None:
        checks = [{"name": "LOW_SHARPE", "value": 0.5, "limit": 1.0}]
        result = basic_test_context.failure(
            failed_stage="check_submission",
            message="checks failed",
            failed_checks=checks,
        )
        assert result.failed_checks == [FailedCheck(name="LOW_SHARPE", value=0.5, limit=1.0)]


def test_run_check_submission_stage_with_self_correlation_pending(monkeypatch) -> None:
    ctx = FieldTestContext(
        field_id="f1",
        field_type="MATRIX",
        field_name="f1",
        template_name="t1",
        expression="rank(f1)",
        settings_fingerprint="s1",
        template_library_fingerprint="tlib1",
    )
    args = MockArgs(
        check_submission_retries=3,
        min_sharpe=1.25,
        min_fitness=1.0,
        min_turnover=0.01,
        max_turnover=0.7,
        max_weight=0.1,
    )

    class DummyClient:
        def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
            return {"is": {"checks": [{"name": "SELF_CORRELATION", "result": "PENDING"}]}}

    monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", lambda *a, **k: a[2]())

    result = run_check_submission_stage(
        ctx,
        DummyClient(),
        args,
        alpha_id="alpha_1",
        simulation_id="sim_1",
        simulation_result=None,
    )

    assert result == (
        None,
        "checks pending",
        [FailedCheck(name="SELF_CORRELATION", result="PENDING")],
    )

    def test_context_fields_independent(self) -> None:
        """不同 context 实例的字段相互独立。"""
        ctx1 = FieldTestContext(
            field_id="a",
            field_type="MATRIX",
            field_name="a",
            template_name="ta",
            expression="ea",
        )
        ctx2 = FieldTestContext(
            field_id="b",
            field_type="VECTOR",
            field_name="b",
            template_name="tb",
            expression="eb",
        )
        r1 = ctx1.failure(failed_stage="simulation", message="e1")
        r2 = ctx2.failure(failed_stage="simulation", message="e2")
        assert r1.field_id == "a"
        assert r2.field_id == "b"
        assert r1.field_type == "MATRIX"
        assert r2.field_type == "VECTOR"


def test_run_simulation_create_stage_merges_dict_settings_with_baseline(monkeypatch) -> None:
    ctx = FieldTestContext(
        field_id="cash_st",
        field_type="MATRIX",
        field_name="cash_st",
        template_name="account_ts_rank_60",
        expression="rank(ts_rank(cash_st, 60))",
        settings_fingerprint="fp1",
        template_library_fingerprint="lib1",
    )
    args = MockArgs(
        instrument_type=None,
        region=None,
        universe=None,
        delay=None,
        decay=None,
        neutralization=None,
        truncation=None,
        pasteurization=None,
        unit_handling=None,
        nan_handling=None,
        language=None,
        start_date=None,
        end_date=None,
        simulation_create_retries=3,
        simulation_poll_retries=3,
        simulation_max_polls=10,
        simulation_max_wait_seconds=60,
        simulation_max_pending_cycles=10,
        simulation_max_queue_seconds=30,
        check_submission_retries=3,
        min_sharpe=1.25,
        min_fitness=1.0,
        min_turnover=0.01,
        max_turnover=0.7,
        max_weight=0.1,
    )
    captured: dict[str, object] = {}

    class DummyClient:
        def create_simulation(self, payload: dict[str, object]) -> str:
            captured["payload"] = payload
            return "/simulations/sim_123"

    monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", lambda *a, **k: a[2]())

    result = run_simulation_create_stage(
        ctx,
        DummyClient(),
        args,
        simulation_settings={"decay": 2, "neutralization": "MARKET"},
    )

    assert result == ("/simulations/sim_123", "sim_123")
    payload = captured["payload"]
    assert isinstance(payload, dict)
    settings = payload["settings"]
    assert isinstance(settings, dict)
    assert settings["instrumentType"] == "EQUITY"
    assert settings["region"] == "USA"
    assert settings["unitHandling"] == "VERIFY"
    assert settings["nanHandling"] == "OFF"
    assert settings["maxTrade"] == "OFF"
    assert settings["visualization"] is False
    assert settings["decay"] == 2
    assert settings["neutralization"] == "MARKET"


def test_run_simulation_create_stage_merges_settings_variant_with_baseline(monkeypatch) -> None:
    ctx = FieldTestContext(
        field_id="cash_st",
        field_type="MATRIX",
        field_name="cash_st",
        template_name="account_ts_rank_252",
        expression="rank(ts_rank(cash_st, 252))",
        settings_fingerprint="fp2",
        template_library_fingerprint="lib2",
    )
    args = MockArgs(
        instrument_type=None,
        region=None,
        universe=None,
        delay=None,
        decay=None,
        neutralization=None,
        truncation=None,
        pasteurization=None,
        unit_handling=None,
        nan_handling=None,
        language=None,
        start_date=None,
        end_date=None,
        simulation_create_retries=3,
        simulation_poll_retries=3,
        simulation_max_polls=10,
        simulation_max_wait_seconds=60,
        simulation_max_pending_cycles=10,
        simulation_max_queue_seconds=30,
        check_submission_retries=3,
        min_sharpe=1.25,
        min_fitness=1.0,
        min_turnover=0.01,
        max_turnover=0.7,
        max_weight=0.1,
    )
    captured: dict[str, object] = {}

    class DummyClient:
        def create_simulation(self, payload: dict[str, object]) -> str:
            captured["payload"] = payload
            return "/simulations/sim_456"

    monkeypatch.setattr("alpha.core.simulation_stages.retry_operation", lambda *a, **k: a[2]())

    result = run_simulation_create_stage(
        ctx,
        DummyClient(),
        args,
        simulation_settings=SettingsVariant(decay=6, truncation=0.05),
    )

    assert result == ("/simulations/sim_456", "sim_456")
    payload = captured["payload"]
    assert isinstance(payload, dict)
    settings = payload["settings"]
    assert isinstance(settings, dict)
    assert settings["instrumentType"] == "EQUITY"
    assert settings["visualization"] is False
    assert settings["decay"] == 6
    assert settings["truncation"] == 0.05


def test_run_simulation_create_stage_skips_when_stop_signal_is_set() -> None:
    ctx = FieldTestContext(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="cashflow_op",
        template_name="group_ratio",
        expression="rank(cashflow_op)",
        settings_fingerprint="fp-stop",
        template_library_fingerprint="lib-stop",
    )
    stop_signal = Event()
    stop_signal.set()

    result = run_simulation_create_stage(
        ctx,
        client=object(),  # type: ignore[arg-type]
        args=MockArgs(),
        should_abort=stop_signal.is_set,
    )

    assert isinstance(result, FieldTestResult)
    assert result.status == STATUS_SKIPPED
    assert result.failed_stage == "stopped"


def test_run_simulation_poll_stage_skips_when_stop_is_requested() -> None:
    ctx = FieldTestContext(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="cashflow_op",
        template_name="group_ratio",
        expression="rank(cashflow_op)",
        settings_fingerprint="fp-stop",
        template_library_fingerprint="lib-stop",
    )

    with (
        patch(
            "alpha.core.simulation_stages.SimulationStageConfig.from_stage_args",
            return_value=SimpleNamespace(
                simulation_poll_retries=3,
                simulation_max_polls=10,
                simulation_max_wait_seconds=60,
                simulation_max_pending_cycles=10,
                simulation_max_queue_seconds=30,
            ),
        ),
        patch(
            "alpha.core.simulation_stages.poll_simulation_with_retry",
            side_effect=BrainStopRequested("polling stopped"),
        ),
    ):
        result = run_simulation_poll_stage(
            ctx,
            client=object(),  # type: ignore[arg-type]
            args=MockArgs(),
            simulation_location="/simulations/sim-1",
            simulation_id="sim-1",
            should_abort=lambda: True,
        )

    assert isinstance(result, FieldTestResult)
    assert result.status == STATUS_SKIPPED
    assert result.failed_stage == "stopped"
    assert result.simulation_id == "sim-1"


def test_resume_field_test_skips_create_and_completes_existing_simulation() -> None:
    pending = PendingFutureContext(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="Cashflow",
        template_name="group_ratio",
        expression="rank(cashflow_op)",
        settings_fingerprint="settings-v1",
        simulation_location="/simulations/sim-1",
        simulation_id="sim-1",
    )

    with (
        patch("alpha.core.simulation.run_simulation_create_stage") as mock_create,
        patch(
            "alpha.core.simulation.run_simulation_poll_stage",
            return_value=("alpha-1", {"status": "COMPLETE"}),
        ) as mock_poll,
        patch(
            "alpha.core.simulation.run_check_submission_stage",
            return_value=(True, "checks passed", []),
        ),
    ):
        result = resume_field_test(
            client=object(),  # type: ignore[arg-type]
            args=MockArgs(),
            pending=pending,
            template_library_fingerprint="library-v1",
        )

    mock_create.assert_not_called()
    mock_poll.assert_called_once()
    assert result.simulation_id == "sim-1"
    assert result.alpha_id == "alpha-1"
    assert result.submittable is True


def _orchestration_field() -> TemplateField:
    return TemplateField(
        field_id="cashflow_op",
        field_name="Cashflow",
        field_type="MATRIX",
        metadata={
            "id": "cashflow_op",
            "name": "Cashflow",
            "type": "MATRIX",
            "template_family": "rank",
            "template_stage": "first_order",
        },
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"expression": ""}, "expression cannot be empty"),
        ({"template_name": ""}, "template_name cannot be empty"),
        ({"settings_fingerprint": ""}, "settings_fingerprint cannot be empty"),
        ({"template_library_fingerprint": ""}, "template_library_fingerprint cannot be empty"),
    ],
)
def test_run_field_test_validates_required_inputs(overrides, message) -> None:
    kwargs = {
        "client": object(),
        "args": MockArgs(),
        "field": _orchestration_field(),
        "template_name": "rank",
        "expression": "rank(cashflow_op)",
        "settings_fingerprint": "settings",
        "template_library_fingerprint": "templates",
    }
    kwargs.update(overrides)

    with pytest.raises(ValueError, match=message):
        run_field_test(**kwargs)  # type: ignore[arg-type]


def test_run_field_test_rejects_field_without_id() -> None:
    field = TemplateField("", "Field", "MATRIX", metadata={"name": "Field"})

    with pytest.raises(ValueError, match="field_id cannot be empty"):
        run_field_test(
            object(),  # type: ignore[arg-type]
            MockArgs(),
            field,
            "rank",
            "rank(field)",
            "settings",
            "templates",
        )


def test_run_field_test_calls_create_callback_and_completion() -> None:
    completed = FieldTestResult(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="Cashflow",
        template_name="rank",
        status="simulated",
        submittable=True,
        expression="rank(cashflow_op)",
    )
    callback_calls: list[tuple[str, str]] = []
    with (
        patch(
            "alpha.core.simulation.run_simulation_create_stage",
            return_value=("/simulations/sim-7", "sim-7"),
        ),
        patch(
            "alpha.core.simulation._complete_field_test_from_simulation",
            return_value=completed,
        ) as mock_complete,
    ):
        result = run_field_test(
            object(),  # type: ignore[arg-type]
            MockArgs(),
            _orchestration_field(),
            "rank",
            "rank(cashflow_op)",
            "settings",
            "templates",
            simulation_settings=SettingsVariant(decay=4),
            on_simulation_created=lambda location, simulation_id: callback_calls.append(
                (location, simulation_id)
            ),
        )

    assert result is completed
    assert callback_calls == [("/simulations/sim-7", "sim-7")]
    assert mock_complete.call_args.kwargs["simulation_id"] == "sim-7"


def test_run_field_test_returns_create_stage_failure() -> None:
    failure = FieldTestContext(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="Cashflow",
        template_name="rank",
        expression="rank(cashflow_op)",
    ).failure(failed_stage="create", message="queue busy")
    with patch("alpha.core.simulation.run_simulation_create_stage", return_value=failure):
        result = run_field_test(
            object(),  # type: ignore[arg-type]
            MockArgs(),
            _orchestration_field(),
            "rank",
            "rank(cashflow_op)",
            "settings",
            "templates",
        )

    assert result is failure


def test_resume_field_test_requires_location() -> None:
    with pytest.raises(ValueError, match="must contain simulation_location"):
        resume_field_test(
            object(),  # type: ignore[arg-type]
            MockArgs(),
            PendingFutureContext(),
            "templates",
        )


def test_worker_entrypoints_resolve_thread_client() -> None:
    client = object()
    factory = SimpleNamespace(get_client=lambda: client)
    completed = FieldTestResult(
        field_id="f",
        field_type="MATRIX",
        field_name="f",
        template_name="rank",
        expression="rank(f)",
    )
    pending = PendingFutureContext(simulation_location="/simulations/s1")
    with (
        patch("alpha.core.simulation.run_field_test", return_value=completed) as mock_run,
        patch("alpha.core.simulation.resume_field_test", return_value=completed) as mock_resume,
    ):
        assert (
            run_field_test_in_worker(
                factory,
                MockArgs(),
                _orchestration_field(),
                "rank",
                "rank(cashflow_op)",
                "settings",
                "templates",
            )
            is completed
        )
        assert resume_field_test_in_worker(factory, MockArgs(), pending, "templates") is completed

    assert mock_run.call_args.args[0] is client
    assert mock_resume.call_args.args[0] is client
