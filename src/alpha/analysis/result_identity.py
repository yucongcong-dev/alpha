"""结果身份、续跑去重与有效反馈判断。

核心谓词已移至 models.result_predicates 以打破 policy ↔ analysis 循环依赖。
本模块保留旧导入路径兼容，并补充仅 analysis 内部使用的聚合函数。
"""

from __future__ import annotations

from collections.abc import Sequence

from ..models.domain import FieldTestResult
from ..models.result_predicates import (
    STATUS_PENDING_SELF_CORRELATION,
    is_informative_result,
    is_queue_timeout_result,
    is_self_correlation_pending_result,
)


def result_identity(result: FieldTestResult) -> tuple[str, str, str, str]:
    """返回单次字段-模板-settings 尝试的稳定去重键。"""
    return (
        result.field_id,
        result.template_name,
        result.expression,
        result.settings_fingerprint,
    )


def attempted_template_keys(results: Sequence[FieldTestResult]) -> set[tuple[str, str, str, str]]:
    """收集已经持久化记录过的模板尝试键集合。"""
    return {result_identity(result) for result in results if is_informative_result(result)}
