"""Simulation create and poll API mixin."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
import time
from typing import cast

from ..config.runtime_values import resolve_http_runtime_config
from ..config.static_config import get_static_config
from ..exceptions import BrainAPIError, BrainQueueBusyError, BrainStopRequested
from ..utils.helpers import first_non_empty
from .api_types import SimulationPayload
from .http_backend import response_header
from .payloads import safe_json_bytes, simulation_payload_is_pending
from .timing import polling_retry_after, wait_seconds

logger = logging.getLogger(__name__)


class BrainSimulationsMixin:
    """Simulation creation and polling helpers for BrainClient."""

    def create_simulation(self, payload: SimulationPayload) -> str:
        """创建模拟任务并返回后续轮询使用的 Location 地址。"""
        _, response_headers, _ = self.request(  # type: ignore[attr-defined]
            "POST",
            get_static_config().simulations_url,
            data=json.dumps(payload),
            headers=get_static_config().sim_accept_header,
            expected={201},
        )
        location = cast(str, response_header(response_headers, "Location"))
        if not location:
            raise BrainAPIError("Simulation created but Location header is missing.")
        return location

    @staticmethod
    def _check_pending_limits(
        pending_cycles: int,
        max_pending_cycles: int,
        max_queue_seconds: float,
        pending_started_at: float | None,
        url: str,
    ) -> None:
        """检查 pending 状态是否超出排队/时间预算。"""
        if pending_cycles > max_pending_cycles:
            raise BrainQueueBusyError(
                f"Simulation stayed queued too long "
                f"({pending_cycles} pending cycles) for {url}; "
                f"skip current template."
            )
        if (
            max_queue_seconds > 0
            and pending_started_at is not None
            and time.monotonic() - pending_started_at > max_queue_seconds
        ):
            raise BrainQueueBusyError(
                f"Simulation exceeded queue budget "
                f"({max_queue_seconds:.0f}s) for {url}; skip current template."
            )

    @staticmethod
    def _check_polling_limits(
        *,
        url: str,
        poll_count: int,
        max_polls: int,
        started_at: float,
        max_wait_seconds: float,
        should_abort: Callable[[], bool] | None,
    ) -> None:
        if should_abort is not None and should_abort():
            raise BrainStopRequested(
                f"simulation polling aborted because stop was requested for {url}"
            )
        if poll_count > max_polls:
            raise BrainAPIError(
                f"Simulation polling exceeded max polls ({max_polls}) "
                f"for {url}; skip current template."
            )
        if time.monotonic() - started_at > max_wait_seconds:
            raise BrainAPIError(
                f"Simulation polling exceeded max wait "
                f"({max_wait_seconds:.1f}s) for {url}; skip current template."
            )

    @classmethod
    def _record_pending_cycle(
        cls,
        *,
        pending_cycles: int,
        pending_started_at: float | None,
        max_pending_cycles: int,
        max_queue_seconds: float,
        url: str,
    ) -> tuple[int, float]:
        started_at = pending_started_at
        if started_at is None:
            started_at = time.monotonic()
        cycles = pending_cycles + 1
        cls._check_pending_limits(
            cycles,
            max_pending_cycles,
            max_queue_seconds,
            started_at,
            url,
        )
        return cycles, started_at

    @staticmethod
    def _wait_for_pending_poll(
        response_headers: dict[str, str],
        *,
        retry_after: str | None,
        status: str,
        default_wait: float,
        no_retry_after_wait: float,
        retry_buffer: float,
        should_abort: Callable[[], bool] | None,
    ) -> None:
        if retry_after:
            seconds = polling_retry_after(
                response_headers,
                default=default_wait,
                buffer_seconds=retry_buffer,
            )
            reason = "simulation pending"
        else:
            seconds = no_retry_after_wait
            reason = f"simulation {status.lower()}"
        wait_seconds(
            seconds,
            reason,
            verbose=False,
            should_abort=should_abort,
        )

    @classmethod
    def _handle_retry_after_payload(
        cls,
        payload: SimulationPayload,
        response_headers: dict[str, str],
        *,
        url: str,
        retry_after: str,
        pending_cycles: int,
        pending_started_at: float | None,
        max_pending_cycles: int,
        max_queue_seconds: float,
        default_wait: float,
        no_retry_after_wait: float,
        retry_buffer: float,
        should_abort: Callable[[], bool] | None,
    ) -> tuple[bool, int, float | None]:
        body_status = str(first_non_empty(payload.get("status"), payload.get("state"), "")).upper()
        if body_status in get_static_config().sim_terminal_states:
            logger.info(
                "[simulation] terminal state detected body_status=%s ignoring Retry-After header",
                body_status,
            )
            return True, pending_cycles, pending_started_at
        if body_status in {"", "NONE"} and pending_cycles == 0:
            logger.info(
                "[simulation] status is null/empty, body_keys=%s body_preview=%.200s",
                sorted(payload.keys()),
                str(payload),
            )
        pending_cycles, pending_started_at = cls._record_pending_cycle(
            pending_cycles=pending_cycles,
            pending_started_at=pending_started_at,
            max_pending_cycles=max_pending_cycles,
            max_queue_seconds=max_queue_seconds,
            url=url,
        )
        logger.info(
            "[simulation] pending location=%s body_status=%s retry_after=%s",
            url,
            body_status or "unknown",
            retry_after,
        )
        cls._wait_for_pending_poll(
            response_headers,
            retry_after=retry_after,
            status=body_status or "unknown",
            default_wait=default_wait,
            no_retry_after_wait=no_retry_after_wait,
            retry_buffer=retry_buffer,
            should_abort=should_abort,
        )
        return False, pending_cycles, pending_started_at

    def poll_simulation(
        self,
        location: str,
        *,
        max_polls: int,
        max_wait_seconds: float,
        max_pending_cycles: int,
        max_queue_seconds: float,
        should_abort: Callable[[], bool] | None = None,
    ) -> SimulationPayload:
        """轮询单个模拟任务，直到完成或超出排队/等待预算。"""
        url = (
            location if location.startswith("http") else f"{get_static_config().api_base}{location}"
        )
        http_config = resolve_http_runtime_config(self)
        poll_count = 0
        pending_cycles = 0
        started_at = time.monotonic()
        pending_started_at: float | None = None
        while True:
            poll_count += 1
            self._check_polling_limits(
                url=url,
                poll_count=poll_count,
                max_polls=max_polls,
                started_at=started_at,
                max_wait_seconds=max_wait_seconds,
                should_abort=should_abort,
            )
            _, response_headers, content = self.request(  # type: ignore[attr-defined]
                "GET",
                url,
                headers=get_static_config().sim_accept_header,
                expected={200, 202},
            )
            payload = safe_json_bytes(content)
            is_pending, status, progress = simulation_payload_is_pending(payload)
            retry_after = response_header(response_headers, "Retry-After")
            if is_pending:
                pending_cycles, pending_started_at = self._record_pending_cycle(
                    pending_cycles=pending_cycles,
                    pending_started_at=pending_started_at,
                    max_pending_cycles=max_pending_cycles,
                    max_queue_seconds=max_queue_seconds,
                    url=url,
                )
                logger.debug(
                    "[simulation] pending location=%s status=%s progress=%s retry_after=%s",
                    url,
                    status,
                    progress,
                    retry_after,
                )
                self._wait_for_pending_poll(
                    response_headers,
                    retry_after=retry_after,
                    status=status,
                    default_wait=http_config.polling_default_wait,
                    no_retry_after_wait=http_config.polling_no_retry_after_wait,
                    retry_buffer=http_config.polling_retry_buffer,
                    should_abort=should_abort,
                )
                continue

            if not retry_after:
                return payload
            terminal, pending_cycles, pending_started_at = self._handle_retry_after_payload(
                payload,
                response_headers,
                url=url,
                retry_after=retry_after,
                pending_cycles=pending_cycles,
                pending_started_at=pending_started_at,
                max_pending_cycles=max_pending_cycles,
                max_queue_seconds=max_queue_seconds,
                default_wait=http_config.polling_default_wait,
                no_retry_after_wait=http_config.polling_no_retry_after_wait,
                retry_buffer=http_config.polling_retry_buffer,
                should_abort=should_abort,
            )
            if terminal:
                return payload
