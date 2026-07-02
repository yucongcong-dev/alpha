"""Alpha detail and submit API mixin."""

from __future__ import annotations

import logging

from ..config.constants import ALPHAS_URL, SIM_ACCEPT_HEADER
from ..config.getters import get_polling_default_wait
from .api_types import ApiPayload
from .payloads import safe_json_bytes
from .timing import polling_retry_after, wait_seconds

logger = logging.getLogger(__name__)


class BrainAlphasMixin:
    """Alpha detail and submit helpers for BrainClient."""

    def get_alpha_detail(self, alpha_id: str) -> ApiPayload:
        """获取 Alpha 详情，包括可用时的 check-submit 结果。"""
        _, _, content = self.request(
            "GET",
            f"{ALPHAS_URL}/{alpha_id}",
            headers=SIM_ACCEPT_HEADER,
            expected={200},
        )
        return safe_json_bytes(content)

    def submit_alpha(self, alpha_id: str) -> ApiPayload:
        """提交可提交的 Alpha，并在需要时跟随异步 Retry-After 轮询。"""
        url = f"{ALPHAS_URL}/{alpha_id}/submit"
        method = "POST"

        while True:
            _, response_headers, content = self.request(
                method,
                url,
                headers=SIM_ACCEPT_HEADER,
                expected={200, 202},
            )
            retry_after = response_headers.get("Retry-After")
            if retry_after:
                logger.info(
                    "[submit] pending alpha_id=%s method=%s retry_after=%s",
                    alpha_id,
                    method,
                    retry_after,
                )
                wait_seconds(
                    polling_retry_after(response_headers, default=get_polling_default_wait()),
                    "submission pending",
                )
                method = "GET"
                continue
            return safe_json_bytes(content)
