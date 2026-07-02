"""Simulation create and poll API mixin."""

from __future__ import annotations

import json
import logging
import time

from ..config.constants import (
    API_BASE,
    SIM_ACCEPT_HEADER,
    SIMULATIONS_URL,
)
from ..config.getters import (
    get_polling_default_wait,
    get_polling_no_retry_after_wait,
)
from ..exceptions import BrainAPIError, BrainQueueBusyError
from ..utils.helpers import first_non_empty
from .api_types import SimulationPayload
from .payloads import safe_json_bytes, simulation_payload_is_pending
from .timing import polling_retry_after, wait_seconds

logger = logging.getLogger(__name__)


class BrainSimulationsMixin:
    """Simulation creation and polling helpers for BrainClient."""

    def create_simulation(self, payload: SimulationPayload) -> str:
        """创建模拟任务并返回后续轮询使用的 Location 地址。"""
        _, response_headers, _ = self.request(
            "POST",
            SIMULATIONS_URL,
            data=json.dumps(payload),
            headers=SIM_ACCEPT_HEADER,
            expected={201},
        )
        location = response_headers.get("Location")
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

    def poll_simulation(
        self,
        location: str,
        *,
        max_polls: int,
        max_wait_seconds: float,
        max_pending_cycles: int,
        max_queue_seconds: float,
    ) -> SimulationPayload:
        """轮询单个模拟任务，直到完成或超出排队/等待预算。"""
        url = location if location.startswith("http") else f"{API_BASE}{location}"
        poll_count = 0
        pending_cycles = 0
        started_at = time.monotonic()
        pending_started_at: float | None = None
        while True:
            poll_count += 1
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
            _, response_headers, content = self.request(
                "GET",
                url,
                headers=SIM_ACCEPT_HEADER,
                expected={200, 202},
            )
            payload = safe_json_bytes(content)
            is_pending, status, progress = simulation_payload_is_pending(payload)
            if is_pending:
                if pending_started_at is None:
                    pending_started_at = time.monotonic()
                pending_cycles += 1
                self._check_pending_limits(
                    pending_cycles,
                    max_pending_cycles,
                    max_queue_seconds,
                    pending_started_at,
                    url,
                )
                logger.debug(
                    "[simulation] pending location=%s status=%s progress=%s retry_after=%s",
                    url,
                    status,
                    progress,
                    response_headers.get("Retry-After"),
                )
                if response_headers.get("Retry-After"):
                    wait_seconds(
                        polling_retry_after(response_headers, default=get_polling_default_wait()),
                        "simulation pending",
                        verbose=False,
                    )
                else:
                    wait_seconds(
                        get_polling_no_retry_after_wait(),
                        f"simulation {status.lower()}",
                        verbose=False,
                    )
                continue

            if response_headers.get("Retry-After"):
                body_status = str(
                    first_non_empty(payload.get("status"), payload.get("state"), "")
                ).upper()
                if body_status in {"COMPLETED", "FAILED", "ERROR", "CANCELLED"}:
                    logger.info(
                        "[simulation] terminal state detected body_status=%s ignoring Retry-After header",
                        body_status,
                    )
                    return payload
                if body_status in {"", "NONE"} and pending_cycles == 0:
                    logger.info(
                        "[simulation] status is null/empty, body_keys=%s body_preview=%.200s",
                        sorted(payload.keys()),
                        str(payload),
                    )
                if pending_started_at is None:
                    pending_started_at = time.monotonic()
                pending_cycles += 1
                self._check_pending_limits(
                    pending_cycles,
                    max_pending_cycles,
                    max_queue_seconds,
                    pending_started_at,
                    url,
                )
                logger.info(
                    "[simulation] pending location=%s body_status=%s retry_after=%s",
                    url,
                    body_status or "unknown",
                    response_headers.get("Retry-After"),
                )
                wait_seconds(
                    polling_retry_after(response_headers, default=get_polling_default_wait()),
                    "simulation pending",
                    verbose=False,
                )
                continue
            return payload
