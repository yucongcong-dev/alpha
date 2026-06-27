
from __future__ import annotations
"""
参数变体模块

本模块负责构建和管理 Alpha 模拟的参数设置，包括模拟请求体的构建、
参数指纹生成和设置变体的生成等功能。通过多样化的参数配置，
提高 Alpha 发现的成功率。

模块内容：
    - build_simulation_payload(): 构建模拟请求体
    - build_settings_fingerprint(): 生成设置指纹
    - build_settings_fingerprint_from_payload(): 从 payload 生成指纹
    - build_setting_variants(): 构建设置变体列表
"""

import hashlib
import json
from typing import Any

from ..config import (
    SETTINGS_CLOSE_THRESHOLD,
    SETTINGS_NEARPASS_THRESHOLD,
    SIMULATION_DEFAULT_END_DATE,
    SIMULATION_DEFAULT_START_DATE,
    STATS_DEFAULT_SCORE,
)
from ..models.base import SettingsVariant
from .expressions import classify_expression_family


def stable_fingerprint(payload: Any) -> str:
    """
    为配置、模板或结果标识生成稳定的短哈希。

    通过对 JSON 数据进行排序和规范化，生成稳定的 SHA-256 哈希值，
    用于标识和去重。

    Args:
        payload (Any): 要哈希的数据对象。

    Returns:
        str: 16 位十六进制哈希字符串。

    Example:
        >>> fingerprint = stable_fingerprint({"key": "value"})
        >>> print(len(fingerprint))
        16

        >>> fp1 = stable_fingerprint({"a": 1, "b": 2})
        >>> fp2 = stable_fingerprint({"b": 2, "a": 1})
        >>> print(fp1 == fp2)
        True  # 字典顺序不影响哈希结果
    """
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_simulation_payload(args: Any, expression: str) -> dict[str, Any]:
    """
    为单个表达式构建完整的模拟请求体。

    创建符合 Brain API 规范的模拟请求体，包含所有必要的设置参数。
    集中化的设置确保所有字段测试具有可比性。

    Args:
        args: 命令行参数对象，包含以下属性：
            - instrument_type: 工具类型（如 "EQUITY"）
            - region: 地区代码（如 "USA"）
            - universe: 宇宙代码（如 "TOP3000"）
            - delay: 延迟天数
            - decay: 衰减天数
            - neutralization: 中性化类型
            - truncation: 截断阈值
            - nan_handling: NaN 处理方式
        expression (str): Alpha 表达式字符串。

    Returns:
        Dict[str, Any]: 完整的模拟请求体，包含 type、settings 和 regular 字段。

    Example:
        >>> payload = build_simulation_payload(args, "rank(close)")
        >>> print(payload["type"])
        'REGULAR'
        >>> print(payload["regular"])
        'rank(close)'
        >>> print(payload["settings"]["region"])
        'USA'

    Note:
        默认配置包括：
            - type: "REGULAR"（常规模拟）
            - pasteurization: "ON"（启用 Pasteurization）
            - unitHandling: "VERIFY"（单位验证）
            - maxTrade: "OFF"（最大交易限制关闭）
            - maxPosition: "OFF"（最大持仓限制关闭）
            - language: "FASTEXPR"（使用 FastExpr 语言）
            - visualization: False（不生成可视化）
            - startDate: "2019-01-01"（开始日期）
            - endDate: "2023-12-31"（结束日期）
    """
    # Keep simulation settings centralized so all field tests are comparable.
    return {
        "type": "REGULAR",
        "settings": {
            "instrumentType": args.instrument_type,
            "region": args.region,
            "universe": args.universe,
            "delay": args.delay,
            "decay": args.decay,
            "neutralization": args.neutralization,
            "truncation": args.truncation,
            "pasteurization": "ON",
            "unitHandling": "VERIFY",
            "nanHandling": args.nan_handling,
            "maxTrade": "OFF",
            "maxPosition": "OFF",
            "language": "FASTEXPR",
            "visualization": False,
            "startDate": getattr(args, "start_date", None) or SIMULATION_DEFAULT_START_DATE,
            "endDate": getattr(args, "end_date", None) or SIMULATION_DEFAULT_END_DATE,
        },
        "regular": expression,
    }


def build_settings_fingerprint(args: Any) -> str:
    """
    为当前模拟配置生成指纹，便于安全续跑与去重。

    通过对模拟设置进行哈希，生成唯一的指纹标识，
    用于验证配置一致性。

    Args:
        args: 命令行参数对象。

    Returns:
        str: 16 位十六进制指纹字符串。

    Example:
        >>> fp1 = build_settings_fingerprint(args1)
        >>> fp2 = build_settings_fingerprint(args2)
        >>> if fp1 == fp2:
        ...     print("配置相同")
        ... else:
        ...     print("配置不同")
    """
    payload = build_simulation_payload(args, "placeholder")
    return stable_fingerprint(payload["settings"])


def build_settings_fingerprint_from_payload(payload: dict[str, Any]) -> str:
    """
    为单个具体 settings 变体生成配置指纹。

    对具体的设置字典进行哈希，用于识别和去重不同的设置变体。

    Args:
        payload (Dict[str, Any]): 设置参数字典。

    Returns:
        str: 16 位十六进制指纹字符串。

    Example:
        >>> settings = {"decay": 5, "truncation": 0.08}
        >>> fingerprint = build_settings_fingerprint_from_payload(settings)
        >>> print(len(fingerprint))
        16
    """
    return stable_fingerprint(payload)


# ---------------------------------------------------------------------------
# 设置变体规则表
# ---------------------------------------------------------------------------
# 每条规则: (families, condition, overrides_dict)
#   families: 适用的家族元组
#   condition: "always" | "near_pass" | "close"
#   overrides: 覆盖 base settings 的参数字典

_VARIANT_SPECS: list[tuple[tuple[str, ...], str, dict[str, Any]]] = [
    # --- group_vol_scaled_delta / group_mean_spread / group_zscore ---
    (("group_vol_scaled_delta", "group_mean_spread", "group_zscore"), "always",
     {"decay": 0, "truncation": 0.05, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("group_vol_scaled_delta", "group_mean_spread", "group_zscore"), "always",
     {"decay": 3, "truncation": 0.08, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("group_vol_scaled_delta", "group_mean_spread", "group_zscore"), "always",
     {"decay": 0, "truncation": 0.12, "nanHandling": "ON", "neutralization": "INDUSTRY"}),
    (("group_vol_scaled_delta", "group_mean_spread", "group_zscore"), "near_pass",
     {"decay": 3, "truncation": 0.05, "nanHandling": "ON", "neutralization": "MARKET"}),
    (("group_vol_scaled_delta", "group_mean_spread", "group_zscore"), "near_pass",
     {"decay": 0, "truncation": 0.08, "nanHandling": "ON", "neutralization": "MARKET"}),
    (("group_vol_scaled_delta", "group_mean_spread", "group_zscore"), "close",
     {"decay": 7, "truncation": 0.05, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("group_vol_scaled_delta", "group_mean_spread", "group_zscore"), "close",
     {"decay": 3, "truncation": 0.05, "nanHandling": "ON", "neutralization": "INDUSTRY"}),

    # --- group_vol_scaled_delta 额外变体（best performing family） ---
    (("group_vol_scaled_delta",), "always",
     {"decay": 2, "truncation": 0.03, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("group_vol_scaled_delta",), "always",
     {"decay": 5, "truncation": 0.05, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("group_vol_scaled_delta",), "always",
     {"decay": 0, "truncation": 0.05, "nanHandling": "OFF", "neutralization": "SUBINDUSTRY"}),
    (("group_vol_scaled_delta",), "always",
     {"decay": 3, "truncation": 0.05, "nanHandling": "ON", "neutralization": "INDUSTRY"}),
    (("group_vol_scaled_delta",), "near_pass",
     {"decay": 2, "truncation": 0.03, "nanHandling": "ON", "neutralization": "MARKET"}),
    (("group_vol_scaled_delta",), "near_pass",
     {"decay": 5, "truncation": 0.03, "nanHandling": "ON", "neutralization": "MARKET"}),
    (("group_vol_scaled_delta",), "near_pass",
     {"decay": 0, "truncation": 0.03, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("group_vol_scaled_delta",), "near_pass",
     {"decay": 7, "truncation": 0.05, "nanHandling": "ON", "neutralization": "MARKET"}),
    (("group_vol_scaled_delta",), "close",
     {"decay": 2, "truncation": 0.02, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("group_vol_scaled_delta",), "close",
     {"decay": 3, "truncation": 0.02, "nanHandling": "ON", "neutralization": "MARKET"}),
    (("group_vol_scaled_delta",), "close",
     {"decay": 5, "truncation": 0.02, "nanHandling": "ON", "neutralization": "INDUSTRY"}),

    # --- vol_scaled_delta / mean_spread / zscore_time / rank_delta / decayed_delta ---
    (("vol_scaled_delta", "mean_spread", "zscore_time", "rank_delta", "decayed_delta"), "always",
     {"decay": 0, "truncation": 0.05, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("vol_scaled_delta", "mean_spread", "zscore_time", "rank_delta", "decayed_delta"), "always",
     {"decay": 5, "truncation": 0.08, "nanHandling": "OFF", "neutralization": "SUBINDUSTRY"}),
    (("vol_scaled_delta", "mean_spread", "zscore_time", "rank_delta", "decayed_delta"), "always",
     {"decay": 0, "truncation": 0.12, "nanHandling": "ON", "neutralization": "INDUSTRY"}),
    (("vol_scaled_delta", "mean_spread", "zscore_time", "rank_delta", "decayed_delta"), "near_pass",
     {"decay": 3, "truncation": 0.05, "nanHandling": "ON", "neutralization": "MARKET"}),
    (("vol_scaled_delta", "mean_spread", "zscore_time", "rank_delta", "decayed_delta"), "near_pass",
     {"decay": 0, "truncation": 0.08, "nanHandling": "ON", "neutralization": "MARKET"}),
    (("vol_scaled_delta", "mean_spread", "zscore_time", "rank_delta", "decayed_delta"), "close",
     {"decay": 7, "truncation": 0.05, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),

    # --- vol_scaled_delta 额外变体 ---
    (("vol_scaled_delta",), "always",
     {"decay": 2, "truncation": 0.03, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("vol_scaled_delta",), "always",
     {"decay": 3, "truncation": 0.05, "nanHandling": "ON", "neutralization": "INDUSTRY"}),
    (("vol_scaled_delta",), "near_pass",
     {"decay": 2, "truncation": 0.03, "nanHandling": "ON", "neutralization": "MARKET"}),
    (("vol_scaled_delta",), "near_pass",
     {"decay": 0, "truncation": 0.03, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),

    # --- group_ratio_level / legacy_ratio ---
    (("group_ratio_level", "legacy_ratio"), "always",
     {"decay": 5, "truncation": 0.08, "nanHandling": "OFF", "neutralization": "SUBINDUSTRY"}),
    (("group_ratio_level", "legacy_ratio"), "always",
     {"decay": 7, "truncation": 0.08, "nanHandling": "OFF", "neutralization": "SUBINDUSTRY"}),
    (("group_ratio_level", "legacy_ratio"), "always",
     {"decay": 0, "truncation": 0.05, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),

    # --- legacy_level / legacy_group_level ---
    (("legacy_level", "legacy_group_level"), "always",
     {"decay": 0, "truncation": 0.05, "nanHandling": "ON", "neutralization": "SUBINDUSTRY"}),
    (("legacy_level", "legacy_group_level"), "always",
     {"decay": 5, "truncation": 0.08, "nanHandling": "OFF", "neutralization": "SUBINDUSTRY"}),
    (("legacy_level", "legacy_group_level"), "always",
     {"decay": 0, "truncation": 0.12, "nanHandling": "ON", "neutralization": "INDUSTRY"}),
]


def build_setting_variants(
    args: Any,
    template_name: str,
    expression: str,
    *,
    field_feedback: dict[str, Any] | None = None,
) -> list[SettingsVariant]:
    """
    为一个表达式生成少量且多样化的 settings 变体（声明式规则表驱动）。

    根据表达式家族类型和历史反馈，通过 _VARIANT_SPECS 规则表生成参数变体组合。

    Args:
        args: 命令行参数对象。
        template_name (str): 模板名称。
        expression (str): 表达式字符串。
        field_feedback: 可选，字段历史反馈。

    Returns:
        List[SettingsVariant]: 去重后的设置变体列表。
    """
    base = build_simulation_payload(args, expression)["settings"]
    variants: list[SettingsVariant] = []
    family = classify_expression_family(template_name, expression)

    best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE)) if field_feedback else STATS_DEFAULT_SCORE
    is_near_pass = best_score >= SETTINGS_NEARPASS_THRESHOLD
    is_close = best_score >= SETTINGS_CLOSE_THRESHOLD

    for families, condition, overrides in _VARIANT_SPECS:
        if family not in families:
            continue
        if condition == "near_pass" and not is_near_pass:
            continue
        if condition == "close" and not is_close:
            continue
        merged = dict(base)
        merged.update(overrides)
        variants.append(merged)

    # 兜底：无匹配规则时使用基础设置
    if not variants:
        variants.append(dict(base))

    # 去重
    deduped: list[SettingsVariant] = []
    seen: set = set()
    for variant in variants:
        fingerprint = build_settings_fingerprint_from_payload(variant)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(variant)
    return deduped
