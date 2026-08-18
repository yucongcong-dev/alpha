"""Alpha detail API mixin."""

from __future__ import annotations

import logging

from ..config.static_config import get_static_config
from .api_types import ApiPayload
from .payloads import safe_json_bytes

logger = logging.getLogger(__name__)


class BrainAlphasMixin:
    """Alpha detail helpers for BrainClient."""

    def get_alpha_detail(self, alpha_id: str) -> ApiPayload:
        """获取 Alpha 详情。"""
        _, _, content = self.request(  # type: ignore[attr-defined]
            "GET",
            f"{get_static_config().alphas_url}/{alpha_id}",
            headers=get_static_config().sim_accept_header,
            expected={200},
        )
        return safe_json_bytes(content)

    def check_alpha_submission(self, alpha_id: str) -> ApiPayload:
        """触发网页 Check Submission 并返回提交检查结果。"""
        _, _, content = self.request(  # type: ignore[attr-defined]
            "GET",
            f"{get_static_config().alphas_url}/{alpha_id}/check",
            headers=get_static_config().sim_accept_header,
            expected={200},
        )
        return safe_json_bytes(content)
