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
from typing import Any, Dict, List, Optional

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


def build_simulation_payload(args: Any, expression: str) -> Dict[str, Any]:
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


def build_settings_fingerprint_from_payload(payload: Dict[str, Any]) -> str:
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


def build_setting_variants(
    args: Any,
    template_name: str,
    expression: str,
    *,
    field_feedback: Optional[Dict[str, Any]] = None,
) -> List[SettingsVariant]:
    """
    为一个表达式生成少量且多样化的 settings 变体。

    根据表达式家族类型和历史反馈，生成适合的参数变体组合，
    提高发现高质量 Alpha 的概率。

    Args:
        args: 命令行参数对象。
        template_name (str): 模板名称。
        expression (str): 表达式字符串。
        field_feedback: 可选，字段历史反馈，用于判断是否加大变体探索力度。

    Returns:
        List[SettingsVariant]: 设置变体列表，每个变体是一个字典。

    变体策略：
        对于不同的表达式家族，使用不同的参数组合：
        - group_vol_scaled_delta, group_mean_spread, group_zscore:
            低 decay、低 truncation、SUBINDUSTRY/MARKET 中性化
        - vol_scaled_delta, mean_spread, zscore_time, rank_delta, decayed_delta:
            中等 decay、中等 truncation、SUBINDUSTRY 中性化
        - group_ratio_level, legacy_ratio:
            中等 decay、中等 truncation、SUBINDUSTRY 中性化
        - legacy_level, legacy_group_level:
            低到中等 decay、低到中等 truncation、SUBINDUSTRY/INDUSTRY 中性化
        - 其他:
            使用基础设置

    Example:
        >>> variants = build_setting_variants(
        ...     args,
        ...     "group_zscore_subindustry_60",
        ...     "group_rank(ts_zscore(close, 60), subindustry)"
        ... )
        >>> print(len(variants))
        4
        >>> print(variants[0]["decay"])
        0

    Note:
        多样化的模板通常更适合较低的截断阈值和时间标准化输入，
        而简单的原始/比率型表达式需要不同的参数配置。
        存在近通反馈时，增加 MARKET 中性化变体以改善子宇宙 Sharpe。
        每个变体都经过去重处理，避免重复测试相同的配置。
    """
    # Keep only a few settings variants per expression family.
    # The diversified templates below often work better with lower truncation
    # and time-normalized inputs than plain raw/ratio shapes do.
    # When field feedback shows near-pass results, add MARKET neutralization
    # variants to improve sub-universe Sharpe.
    base = build_simulation_payload(args, expression)["settings"]
    variants: List[SettingsVariant] = []

    def push_variant(**overrides: Any) -> None:
        """
        添加一个新的设置变体。

        将基础设置与覆盖参数合并，添加到变体列表。

        Args:
            **overrides: 要覆盖的参数键值对。
        """
        merged = dict(base)
        merged.update(overrides)
        variants.append(merged)

    family = classify_expression_family(template_name, expression)

    # Determine if this field has near-pass feedback deserving extra variants
    best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE)) if field_feedback else STATS_DEFAULT_SCORE
    is_near_pass = best_score >= SETTINGS_NEARPASS_THRESHOLD
    is_close = best_score >= SETTINGS_CLOSE_THRESHOLD

    if family in {"group_vol_scaled_delta", "group_mean_spread", "group_zscore"}:
        push_variant(decay=0, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=3, truncation=0.08, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=0, truncation=0.12, nanHandling="ON", neutralization="INDUSTRY")
        if is_near_pass:
            push_variant(decay=3, truncation=0.05, nanHandling="ON", neutralization="MARKET")
            push_variant(decay=0, truncation=0.08, nanHandling="ON", neutralization="MARKET")
        if is_close:
            push_variant(decay=7, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
            push_variant(decay=3, truncation=0.05, nanHandling="ON", neutralization="INDUSTRY")

    # Extra variants for vol-scaled delta — best performing family on fundamental6
    if family == "group_vol_scaled_delta":
        push_variant(decay=2, truncation=0.03, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=5, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=0, truncation=0.05, nanHandling="OFF", neutralization="SUBINDUSTRY")
        push_variant(decay=3, truncation=0.05, nanHandling="ON", neutralization="INDUSTRY")
        if is_near_pass:
            push_variant(decay=2, truncation=0.03, nanHandling="ON", neutralization="MARKET")
            push_variant(decay=5, truncation=0.03, nanHandling="ON", neutralization="MARKET")
            push_variant(decay=0, truncation=0.03, nanHandling="ON", neutralization="SUBINDUSTRY")
            push_variant(decay=7, truncation=0.05, nanHandling="ON", neutralization="MARKET")
        if is_close:
            push_variant(decay=2, truncation=0.02, nanHandling="ON", neutralization="SUBINDUSTRY")
            push_variant(decay=3, truncation=0.02, nanHandling="ON", neutralization="MARKET")
            push_variant(decay=5, truncation=0.02, nanHandling="ON", neutralization="INDUSTRY")
    elif family in {"vol_scaled_delta", "mean_spread", "zscore_time", "rank_delta", "decayed_delta"}:
        push_variant(decay=0, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=5, truncation=0.08, nanHandling="OFF", neutralization="SUBINDUSTRY")
        push_variant(decay=0, truncation=0.12, nanHandling="ON", neutralization="INDUSTRY")
        if is_near_pass:
            push_variant(decay=3, truncation=0.05, nanHandling="ON", neutralization="MARKET")
            push_variant(decay=0, truncation=0.08, nanHandling="ON", neutralization="MARKET")
        if is_close:
            push_variant(decay=7, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")

    # Extra variants for standalone vol-scaled delta
    if family == "vol_scaled_delta":
        push_variant(decay=2, truncation=0.03, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=3, truncation=0.05, nanHandling="ON", neutralization="INDUSTRY")
        if is_near_pass:
            push_variant(decay=2, truncation=0.03, nanHandling="ON", neutralization="MARKET")
            push_variant(decay=0, truncation=0.03, nanHandling="ON", neutralization="SUBINDUSTRY")
    elif family in {"group_ratio_level", "legacy_ratio"}:
        push_variant(decay=5, truncation=0.08, nanHandling="OFF", neutralization="SUBINDUSTRY")
        push_variant(decay=7, truncation=0.08, nanHandling="OFF", neutralization="SUBINDUSTRY")
        push_variant(decay=0, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
    elif family in {"legacy_level", "legacy_group_level"}:
        push_variant(decay=0, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=5, truncation=0.08, nanHandling="OFF", neutralization="SUBINDUSTRY")
        push_variant(decay=0, truncation=0.12, nanHandling="ON", neutralization="INDUSTRY")
    else:
        push_variant()

    deduped: List[SettingsVariant] = []
    seen: set = set()
    for variant in variants:
        fingerprint = build_settings_fingerprint_from_payload(variant)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(variant)
    return deduped
