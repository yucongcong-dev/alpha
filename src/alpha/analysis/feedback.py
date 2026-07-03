"""
Feedback compatibility facade.

反馈兼容门面。

The historical feedback implementation now lives in focused modules:
``feedback_history`` for state/near-pass selection and ``feedback_filters`` for
template pruning policies. This module keeps the old import path stable.

历史反馈实现已拆到更聚焦的模块中：``feedback_history`` 负责状态和 near-pass
选择，``feedback_filters`` 负责模板剪枝策略。本文件保留旧导入路径兼容。

.. deprecated:: 1.0.0
    This module is a compatibility facade. Import from ``alpha.analysis.feedback_history``
    or ``alpha.analysis.feedback_filters`` instead.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "alpha.analysis.feedback is deprecated. Import from "
    "alpha.analysis.feedback_history or alpha.analysis.feedback_filters instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .feedback_filters import (
    is_legacy_family_disabled,
    is_template_disabled,
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)
from .feedback_history import (
    build_historical_run_state,
    choose_settings_variant_budget,
    select_nearpass_candidates,
    should_stop_after_submittable,
)

__all__ = [
    "build_historical_run_state",
    "choose_settings_variant_budget",
    "is_legacy_family_disabled",
    "is_template_disabled",
    "select_nearpass_candidates",
    "should_keep_template_for_feedback",
    "should_skip_field_template_family",
    "should_stop_after_submittable",
]
