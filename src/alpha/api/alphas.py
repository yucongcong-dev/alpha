"""Alpha detail API mixin."""

from __future__ import annotations

import logging

from ..config.constants import ALPHAS_URL, SIM_ACCEPT_HEADER
from .api_types import ApiPayload
from .payloads import safe_json_bytes

logger = logging.getLogger(__name__)


class BrainAlphasMixin:
    """Alpha detail helpers for BrainClient."""

    def get_alpha_detail(self, alpha_id: str) -> ApiPayload:
        """获取 Alpha 详情，包括可用时的 check-submit 结果。"""
        _, _, content = self.request(  # type: ignore[attr-defined]
            "GET",
            f"{ALPHAS_URL}/{alpha_id}",
            headers=SIM_ACCEPT_HEADER,
            expected={200},
        )
        return safe_json_bytes(content)
