"""
并发调度与拥塞控制模块单元测试（pytest 风格）

测试 alpha.core.scheduler 中的核心函数，覆盖拥塞控制和并发管理边界条件。
使用 conftest.py 中的共享 fixtures 消除重复 setup 和 MagicMock 风险。
"""

from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor
import time
from unittest.mock import patch

from alpha.core.scheduler import (
    apply_congestion_cooldown,
    drain_completed_futures,
    maybe_restore_runtime_concurrency,
    register_queue_busy_template,
    throttle_before_submission,
)
from alpha.core.scheduler_decisions import (
    decide_drain_state_updates,
    should_restore_runtime_concurrency,
    submission_throttle_delay,
)
from alpha.models.domain import FieldTestResult
from alpha.models.runtime import (
    ExecutionState,
    PendingFutureContext,
    ResultWriteOptions,
    RuntimeConcurrencyState,
)
from tests.conftest import MockArgs


def test_drain_state_decision_combines_stop_and_cooldown() -> None:
    decision = decide_drain_state_updates(
        stop_threshold=2,
        current_submittable_count=2,
        congestion_detected=True,
    )

    assert decision.activate_stop_signal is True
    assert decision.apply_congestion_cooldown is True


def test_submission_throttle_delay_is_deterministic_and_clamped() -> None:
    assert (
        submission_throttle_delay(
            interval_seconds=5.0,
            last_submission_at=100.0,
            now=103.5,
        )
        == 1.5
    )
    assert (
        submission_throttle_delay(
            interval_seconds=5.0,
            last_submission_at=100.0,
            now=106.0,
        )
        == 0.0
    )


def test_restore_concurrency_decision_has_no_clock_side_effect() -> None:
    assert (
        should_restore_runtime_concurrency(
            cooldown_until=10.0,
            runtime_max_workers=1,
            max_workers=5,
            now=10.0,
        )
        is True
    )


# ============================================================================
# maybe_restore_runtime_concurrency 测试
# ============================================================================


class TestMaybeRestoreRuntimeConcurrency:
    """maybe_restore_runtime_concurrency 函数测试"""

    def test_restores_when_cooldown_expired(
        self, runtime_state_cooldown_expired: RuntimeConcurrencyState
    ) -> None:
        maybe_restore_runtime_concurrency(runtime_state_cooldown_expired)
        assert runtime_state_cooldown_expired.runtime_max_workers == 5
        assert runtime_state_cooldown_expired.cooldown_until == 0.0

    def test_no_restore_when_still_cooling(
        self, runtime_state_cooling_down: RuntimeConcurrencyState
    ) -> None:
        maybe_restore_runtime_concurrency(runtime_state_cooling_down)
        assert runtime_state_cooling_down.runtime_max_workers == 1

    def test_no_restore_when_already_max(
        self, runtime_state_max_workers_5: RuntimeConcurrencyState
    ) -> None:
        state = runtime_state_max_workers_5
        state.cooldown_until = max(0.001, time.monotonic() / 2)
        maybe_restore_runtime_concurrency(state)
        assert state.runtime_max_workers == 5

    def test_no_cooldown_zero(self) -> None:
        state = RuntimeConcurrencyState(max_workers=5, runtime_max_workers=1, cooldown_until=0.0)
        maybe_restore_runtime_concurrency(state)
        assert state.runtime_max_workers == 1

    def test_restore_logs_message(self) -> None:
        state = RuntimeConcurrencyState(
            max_workers=10,
            runtime_max_workers=2,
            cooldown_until=max(0.001, time.monotonic() / 2),
        )
        with patch("alpha.core.scheduler.logger") as mock_logger:
            maybe_restore_runtime_concurrency(state)
            assert state.runtime_max_workers == 10
            assert any(
                "restored runtime concurrency" in str(call)
                for call in mock_logger.info.call_args_list
            )


# ============================================================================
# apply_congestion_cooldown 测试
# ============================================================================


class TestApplyCongestionCooldown:
    """apply_congestion_cooldown 函数测试"""

    def test_sets_workers_to_1(
        self,
        scheduler_args: MockArgs,
        runtime_state_max_workers_5: RuntimeConcurrencyState,
    ) -> None:
        apply_congestion_cooldown(scheduler_args, runtime_state_max_workers_5)
        assert runtime_state_max_workers_5.runtime_max_workers == 1
        assert runtime_state_max_workers_5.cooldown_until > time.monotonic()

    def test_sets_cooldown_until(
        self,
        scheduler_args: MockArgs,
        runtime_state_max_workers_5: RuntimeConcurrencyState,
    ) -> None:
        scheduler_args.queue_busy_cooldown_seconds = 60
        now = time.monotonic()
        apply_congestion_cooldown(scheduler_args, runtime_state_max_workers_5)
        expected_cooldown = now + 60
        assert abs(runtime_state_max_workers_5.cooldown_until - expected_cooldown) < 0.5

    def test_negative_cooldown_clamped(
        self,
        scheduler_args: MockArgs,
        runtime_state_max_workers_5: RuntimeConcurrencyState,
    ) -> None:
        scheduler_args.queue_busy_cooldown_seconds = -10
        apply_congestion_cooldown(scheduler_args, runtime_state_max_workers_5)
        assert runtime_state_max_workers_5.runtime_max_workers == 1
        # cooldown 应该被 clamp 到当前时间附近
        assert runtime_state_max_workers_5.cooldown_until <= time.monotonic() + 0.5

    def test_zero_cooldown(
        self,
        scheduler_args: MockArgs,
        runtime_state_max_workers_5: RuntimeConcurrencyState,
    ) -> None:
        scheduler_args.queue_busy_cooldown_seconds = 0
        now = time.monotonic()
        apply_congestion_cooldown(scheduler_args, runtime_state_max_workers_5)
        assert abs(runtime_state_max_workers_5.cooldown_until - now) < 0.5


class TestRegisterQueueBusyTemplate:
    def test_exhausts_only_one_candidate_key(
        self,
        scheduler_args: MockArgs,
        empty_execution_state: ExecutionState,
    ) -> None:
        scheduler_args.queue_busy_retry_limit = 2
        first_key = ("field_1", "template_1", "rank(field_1)", "settings_1")
        second_key = ("field_1", "template_2", "rank(field_1)", "settings_1")

        register_queue_busy_template(first_key, scheduler_args, empty_execution_state)
        register_queue_busy_template(first_key, scheduler_args, empty_execution_state)

        retry_state = empty_execution_state.queue_retry_state
        assert first_key in retry_state.exhausted_keys
        assert second_key not in retry_state.exhausted_keys

    def test_zero_retry_limit_keeps_candidate_retryable(
        self,
        scheduler_args: MockArgs,
        empty_execution_state: ExecutionState,
    ) -> None:
        scheduler_args.queue_busy_retry_limit = 0
        key = ("field_1", "template_1", "rank(field_1)", "settings_1")

        for _ in range(3):
            register_queue_busy_template(key, scheduler_args, empty_execution_state)

        retry_state = empty_execution_state.queue_retry_state
        assert retry_state.retry_counts[key] == 3
        assert retry_state.exhausted_keys == set()


# ============================================================================
# throttle_before_submission 测试
# ============================================================================


class TestThrottleBeforeSubmission:
    """throttle_before_submission 函数测试"""

    def test_no_sleep_when_disabled(
        self,
        scheduler_args: MockArgs,
        empty_execution_state: ExecutionState,
    ) -> None:
        scheduler_args.sleep_between_fields = 0
        with patch("alpha.core.scheduler.wait_seconds") as mock_wait:
            throttle_before_submission(scheduler_args, empty_execution_state)
            mock_wait.assert_not_called()

    def test_no_sleep_on_first_submission(
        self,
        scheduler_args: MockArgs,
        empty_execution_state: ExecutionState,
    ) -> None:
        with patch("alpha.core.scheduler.wait_seconds") as mock_wait:
            throttle_before_submission(scheduler_args, empty_execution_state)
            mock_wait.assert_not_called()

    def test_sleeps_when_too_soon(
        self,
        scheduler_args: MockArgs,
        execution_state_after_submit: ExecutionState,
    ) -> None:
        with patch("alpha.core.scheduler.wait_seconds") as mock_wait:
            throttle_before_submission(scheduler_args, execution_state_after_submit)
            mock_wait.assert_called_once()

    def test_no_sleep_when_enough_elapsed(
        self,
        scheduler_args: MockArgs,
        execution_state_long_ago_submit: ExecutionState,
    ) -> None:
        with patch("alpha.core.scheduler.wait_seconds") as mock_wait:
            throttle_before_submission(scheduler_args, execution_state_long_ago_submit)
            mock_wait.assert_not_called()

    def test_zero_sleep_between_fields_never_waits(self) -> None:
        """sleep_between_fields=0 时永远不等待，无论上次提交时间。"""
        state = ExecutionState.create(
            last_submission_at=time.monotonic(),  # 刚刚提交
        )
        args = MockArgs(sleep_between_fields=0)
        with patch("alpha.core.scheduler.wait_seconds") as mock_wait:
            throttle_before_submission(args, state)
            mock_wait.assert_not_called()


# ============================================================================
# RuntimeConcurrencyState 方法测试
# ============================================================================


class TestRuntimeConcurrencyState:
    """RuntimeConcurrencyState 数据类测试"""

    def test_is_cooling_down_true(
        self, runtime_state_cooling_down: RuntimeConcurrencyState
    ) -> None:
        assert runtime_state_cooling_down.is_cooling_down() is True

    def test_is_cooling_down_false(
        self, runtime_state_max_workers_5: RuntimeConcurrencyState
    ) -> None:
        assert runtime_state_max_workers_5.is_cooling_down() is False

    def test_is_cooling_down_zero(self) -> None:
        state = RuntimeConcurrencyState(cooldown_until=0.0)
        assert state.is_cooling_down() is False

    def test_can_restore_concurrency_true(
        self, runtime_state_cooldown_expired: RuntimeConcurrencyState
    ) -> None:
        assert runtime_state_cooldown_expired.can_restore_concurrency() is True

    def test_can_restore_concurrency_false_still_cooling(
        self, runtime_state_cooling_down: RuntimeConcurrencyState
    ) -> None:
        assert runtime_state_cooling_down.can_restore_concurrency() is False

    def test_can_restore_concurrency_false_already_max(
        self, runtime_state_max_workers_5: RuntimeConcurrencyState
    ) -> None:
        state = runtime_state_max_workers_5
        state.cooldown_until = 100.0
        assert state.can_restore_concurrency() is False

    def test_default_values(self) -> None:
        state = RuntimeConcurrencyState()
        assert state.max_workers == 2
        assert state.runtime_max_workers == 2
        assert state.cooldown_until == 0.0


def test_drain_completed_futures_prefers_explicit_result_write_options(tmp_path) -> None:
    """Incremental writes should be able to honor normalized output paths over raw args."""
    future: Future[object] = Future()
    future.set_result(None)
    execution_state = ExecutionState.create(
        pending_futures={
            future: PendingFutureContext(
                field_id="field_1",
                field_name="field_1",
                field_type="MATRIX",
                template_name="tpl",
                expression="rank(field_1)",
                settings_fingerprint="variant-fp",
            )
        },
    )
    args = argparse.Namespace(
        dataset_id="fundamental6",
        output="raw-results.json",
        auto_update_blacklist=False,
        queue_busy_retry_limit=0,
        queue_busy_cooldown_seconds=0,
    )
    result_write_options = ResultWriteOptions(
        dataset_id="fundamental6",
        output_path=str(tmp_path / "normalized-results.json"),
        auto_update_blacklist=False,
    )

    with patch(
        "alpha.core.scheduler.apply_completed_result", return_value=({}, False, None)
    ) as mock_apply:
        drain_completed_futures(
            completed_futures=[future],
            execution_state=execution_state,
            args=args,
            result_write_options=result_write_options,
            settings_fingerprint="settings-fp",
            template_library_fingerprint="templates-fp",
            run_config={},
            runtime_state=RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1),
        )

    completion_ctx = mock_apply.call_args.kwargs["completion_ctx"]
    assert completion_ctx.result_write_options.output_path == str(
        tmp_path / "normalized-results.json"
    )


def test_drain_completed_futures_sets_stop_signal_and_cancels_unstarted_future(tmp_path) -> None:
    done_future: Future[object] = Future()
    done_future.set_result(None)

    with ThreadPoolExecutor(max_workers=1) as executor:
        blocker = executor.submit(time.sleep, 0.2)
        queued_future = executor.submit(time.sleep, 0.2)
        execution_state = ExecutionState.create(
            pending_futures={
                done_future: PendingFutureContext(
                    field_id="field_done",
                    field_name="field_done",
                    field_type="MATRIX",
                    template_name="tpl_done",
                    expression="rank(field_done)",
                    settings_fingerprint="done-fp",
                ),
                queued_future: PendingFutureContext(
                    field_id="field_queued",
                    field_name="field_queued",
                    field_type="MATRIX",
                    template_name="tpl_queued",
                    expression="rank(field_queued)",
                    settings_fingerprint="queued-fp",
                ),
            },
        )
        args = argparse.Namespace(
            dataset_id="fundamental6",
            output="raw-results.json",
            auto_update_blacklist=False,
            queue_busy_retry_limit=0,
            queue_busy_cooldown_seconds=0,
            stop_after_submittable=1,
        )
        result_write_options = ResultWriteOptions(
            dataset_id="fundamental6",
            output_path=str(tmp_path / "normalized-results.json"),
            auto_update_blacklist=False,
        )

        with patch(
            "alpha.core.scheduler.apply_completed_result",
            return_value=({}, False, None),
        ):
            execution_state.result_ledger.append(
                FieldTestResult(
                    field_id="field_done",
                    field_type="MATRIX",
                    field_name="field_done",
                    template_name="tpl_done",
                    status="simulated",
                    submittable=True,
                    expression="rank(field_done)",
                )
            )
            drain_completed_futures(
                completed_futures=[done_future],
                execution_state=execution_state,
                args=args,
                result_write_options=result_write_options,
                settings_fingerprint="settings-fp",
                template_library_fingerprint="templates-fp",
                run_config={},
                runtime_state=RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1),
            )

        assert execution_state.future_queue.scheduling_stop_signal.is_set() is True
        assert execution_state.future_queue.stop_signal.is_set() is False
        assert queued_future not in execution_state.future_queue.pending_futures
        blocker.cancel()


def test_drain_completed_futures_ignores_historical_submittable_baseline() -> None:
    done_future: Future[object] = Future()
    done_future.set_result(None)
    queued_future: Future[object] = Future()
    execution_state = ExecutionState.create(
        initial_results=[
            FieldTestResult(
                field_id="field_done",
                field_type="MATRIX",
                field_name="field_done",
                template_name="tpl_done",
                status="simulated",
                submittable=True,
                expression="rank(field_done)",
            )
        ],
        pending_futures={
            done_future: PendingFutureContext(
                field_id="field_done",
                field_name="field_done",
                field_type="MATRIX",
                template_name="tpl_done",
                expression="rank(field_done)",
                settings_fingerprint="done-fp",
            ),
            queued_future: PendingFutureContext(
                field_id="field_queued",
                field_name="field_queued",
                field_type="MATRIX",
                template_name="tpl_queued",
                expression="rank(field_queued)",
                settings_fingerprint="queued-fp",
            ),
        },
    )
    execution_state.result_ledger.submittable_baseline_count = 1
    args = argparse.Namespace(
        dataset_id="fundamental6",
        output="raw-results.json",
        auto_update_blacklist=False,
        queue_busy_retry_limit=0,
        queue_busy_cooldown_seconds=0,
        stop_after_submittable=1,
    )

    with patch(
        "alpha.core.scheduler.apply_completed_result",
        return_value=({}, False, None),
    ):
        drain_completed_futures(
            completed_futures=[done_future],
            execution_state=execution_state,
            args=args,
            settings_fingerprint="settings-fp",
            template_library_fingerprint="templates-fp",
            run_config={},
            runtime_state=RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1),
        )

    assert execution_state.future_queue.scheduling_stop_signal.is_set() is False
    assert execution_state.future_queue.stop_signal.is_set() is False
    assert queued_future in execution_state.future_queue.pending_futures
    assert queued_future.cancelled() is False
