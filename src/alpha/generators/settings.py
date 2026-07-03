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

from __future__ import annotations

import calendar
from datetime import date
import hashlib
import json
from typing import Any

from ..config.constants import (
    GROUP_NAME_SUBINDUSTRY,
    MONTHS_PER_YEAR,
    NEUTRALIZATION_INDUSTRY,
    NEUTRALIZATION_MARKET,
    NEUTRALIZATION_NONE,
    NEUTRALIZATION_SUBINDUSTRY,
    SETTINGS_VARIANT_DECAY_FAST,
    SETTINGS_VARIANT_DECAY_SLOW,
    STABLE_FINGERPRINT_HEX_LEN,
    TRUNCATION_TIGHTER_MAX,
    TRUNCATION_WEB_DEFAULT,
)
from ..config.getters import (
    get_simulation_default_end_date,
    get_simulation_default_start_date,
)
from ..config.yaml import (
    get_yaml_config,
)
from ..models.domain import NearPassCandidate, SettingsVariant
from ..models.runtime import SimulationSettingsArgs


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
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:STABLE_FINGERPRINT_HEX_LEN]


# ---------------------------------------------------------------------------
# 硬编码官网默认值 —— 合并 YAML 配置不可用时回退
# 与 Brain 官网 Settings 面板默认值严格一致:
#   LANGUAGE=Fast Expression, INSTRUMENT TYPE=Equity, REGION=USA,
#   UNIVERSE=TOP3000, DELAY=1, NEUTRALIZATION=Subindustry,
#   DECAY=4, TRUNCATION=0.08, PASTEURIZATION=On,
#   UNIT HANDLING=Verify, NAN HANDLING=Off, TEST PERIOD=1Y 0M
# ---------------------------------------------------------------------------
# key = Brain API 参数名 (camelCase)，与 config/settings.yaml 命名一致
_WEBSITE_DEFAULTS: dict[str, Any] = {
    "language": "FASTEXPR",
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "neutralization": NEUTRALIZATION_SUBINDUSTRY,
    "decay": 4,
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "OFF",
    "visualization": False,
}

# ---------------------------------------------------------------------------
# Brain API key (camelCase) → args attribute (snake_case) 映射
# 仅当 YAML/API key 与 args 属性名不同时需要
# ---------------------------------------------------------------------------
_API_TO_ARGS: dict[str, str] = {
    "instrumentType": "instrument_type",
    "unitHandling": "unit_handling",
    "nanHandling": "nan_handling",
    "startDate": "start_date",
    "endDate": "end_date",
}

# argparse CLI 默认值 —— 用于判断用户是否主动传参
_CLI_DEFAULTS: dict[str, Any] = {
    "instrument_type": "EQUITY", "region": "USA", "universe": "TOP3000",
    "delay": 1, "decay": 4, "neutralization": NEUTRALIZATION_SUBINDUSTRY, "truncation": 0.08,
    "pasteurization": "ON", "unit_handling": "VERIFY", "nan_handling": "OFF",
    "language": "FASTEXPR",
}

# TEST PERIOD 硬编码官网默认: 1Y 0M
_TEST_PERIOD_DEFAULTS = {"testPeriodYears": 1, "testPeriodMonths": 0}


def _read_simulation_from_yaml() -> dict[str, Any] | None:
    """从合并 YAML 配置读取 global.simulation 节点，不可用时返回 None。"""
    yaml_cfg = get_yaml_config()
    if not yaml_cfg:
        return None
    global_cfg = yaml_cfg.get("global")
    if not isinstance(global_cfg, dict):
        return None
    sim = global_cfg.get("simulation")
    return sim if isinstance(sim, dict) else None


def _resolve_setting(
    yaml_sim: dict[str, Any] | None,
    args: SimulationSettingsArgs,
    api_key: str,
) -> Any:
    """按 CLI > YAML > 官网默认 优先级解析单个设置参数。

    api_key 即为 YAML key 和 Brain API payload key (camelCase)。
    """
    arg_key = _API_TO_ARGS.get(api_key, api_key)
    cli_val = getattr(args, arg_key, None)
    # 若 CLI 值与 argparse 默认值不同，说明用户主动传参，CLI 优先
    if cli_val is not None and cli_val != _CLI_DEFAULTS.get(arg_key):
        return cli_val
    # YAML 次之
    if yaml_sim and api_key in yaml_sim:
        return yaml_sim[api_key]
    # 官网默认兜底
    return _WEBSITE_DEFAULTS.get(api_key, cli_val)


def build_simulation_payload(args: SimulationSettingsArgs, expression: str) -> dict[str, Any]:
    """
    从合并 YAML 配置读取设置，构建模拟请求体。

    优先级: CLI 参数 > config/settings.yaml > 硬编码官网默认值。
    YAML key 即为 Brain API payload key (camelCase)，无需翻译。

    Args:
        args: 满足 `SimulationSettingsArgs` 协议的设置输入对象。
        expression: Alpha 表达式字符串。

    Returns:
        Dict[str, Any]: 完整模拟请求体，包含 type、settings 和 regular 字段。
    """
    yaml_sim = _read_simulation_from_yaml()

    settings: dict[str, Any] = {}
    for api_key in _WEBSITE_DEFAULTS:
        settings[api_key] = _resolve_setting(yaml_sim, args, api_key)

    # --- startDate / endDate 解析: testPeriodYears/Months > startDate/endDate > CLI > 默认 ---
    start_date = None
    end_date = None

    # 1. CLI 主动传参优先
    cli_start = getattr(args, "start_date", None)
    cli_end = getattr(args, "end_date", None)
    cli_start_default = _CLI_DEFAULTS.get("start_date")
    cli_end_default = _CLI_DEFAULTS.get("end_date")

    if cli_start is not None and cli_start != cli_start_default:
        start_date = cli_start
    if cli_end is not None and cli_end != cli_end_default:
        end_date = cli_end

    # 2. YAML: testPeriodYears / testPeriodMonths (官网命名)
    if (start_date is None or end_date is None) and yaml_sim:
        years = yaml_sim.get("testPeriodYears")
        months = yaml_sim.get("testPeriodMonths")
        if not years:
            years = _TEST_PERIOD_DEFAULTS["testPeriodYears"]
        if not months:
            months = _TEST_PERIOD_DEFAULTS["testPeriodMonths"]
        total_months = (years or 0) * MONTHS_PER_YEAR + (months or 0)
        if total_months > 0:
            today = date.today()
            # 往前推 total_months 个月，日期不超过目标月末
            comp_months = today.year * MONTHS_PER_YEAR + today.month - 1  # 0-based
            comp_months -= total_months
            cy, cm = divmod(comp_months, MONTHS_PER_YEAR)
            cm += 1  # 1-based month
            max_day = calendar.monthrange(cy, cm)[1]
            computed = date(cy, cm, min(today.day, max_day))
            if start_date is None:
                start_date = computed.isoformat()
            if end_date is None:
                end_date = today.isoformat()

    # 3. YAML: 固定 startDate / endDate (兼容手动指定历史区间)
    if yaml_sim:
        if start_date is None:
            start_date = yaml_sim.get("startDate")
        if end_date is None:
            end_date = yaml_sim.get("endDate")

    # 4. 兜底 config 默认值
    if not start_date:
        start_date = get_simulation_default_start_date()
    if not end_date:
        end_date = get_simulation_default_end_date()

    settings["startDate"] = start_date
    settings["endDate"] = end_date

    return {
        "type": "REGULAR",
        "settings": settings,
        "regular": expression,
    }


def build_settings_fingerprint(args: SimulationSettingsArgs) -> str:
    """
    为当前模拟配置生成指纹，便于安全续跑与去重。

    通过对模拟设置进行哈希，生成唯一的指纹标识，
    用于验证配置一致性。

    Args:
        args: 满足 `SimulationSettingsArgs` 协议的设置输入对象。

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


def build_setting_variants(
    args: SimulationSettingsArgs,
    template_name: str,
    expression: str,
    *,
    field_feedback: dict[str, Any] | None = None,
    refine_candidate: NearPassCandidate | None = None,
) -> list[SettingsVariant]:
    """
    基于统一基准配置生成少量高信号 settings 变体。

    默认返回 3 组以内的变体，围绕更严格的权重控制和更合适的中性化展开，
    让接近门槛的表达式优先获得“去集中化/去重复中性化”的第二次机会。
    优先级仍然是 CLI > YAML > 硬编码官网默认值，然后在此基础上生成少量派生配置。

    Args:
        args: 满足 `SimulationSettingsArgs` 协议的设置输入对象。
        template_name: 模板名称（保留兼容，未使用）。
        expression: Alpha 表达式字符串。
        field_feedback: 保留兼容，未使用。

    Returns:
        List[SettingsVariant]: 去重后的 settings 变体列表。
    """
    base_settings = build_simulation_payload(args, expression)["settings"]
    variants: list[SettingsVariant] = [dict(base_settings)]
    lower_expr = expression.lower()

    def add_variant(**updates: Any) -> None:
        candidate = dict(base_settings)
        candidate.update(updates)
        if candidate not in variants:
            variants.append(candidate)

    nearpass_failed_names = {
        str(check.get("name", "")).strip()
        for check in (refine_candidate.failed_checks if refine_candidate else [])
    }
    tighter_truncation = min(float(base_settings.get("truncation", TRUNCATION_WEB_DEFAULT)), TRUNCATION_TIGHTER_MAX)

    # 对容易集中持仓的表达式优先尝试更严格的 truncation。
    add_variant(truncation=tighter_truncation)

    # 如果表达式已经在公式里显式做了 group_neutralize，避免再用 settings 重复中性化。
    if "group_neutralize(" in lower_expr:
        add_variant(neutralization=NEUTRALIZATION_NONE, truncation=tighter_truncation)
    elif GROUP_NAME_SUBINDUSTRY in lower_expr or "group_rank(" in lower_expr:
        # 对强 subindustry 模板给一个更大颗粒度的 neutralization 备选，
        # 有助于缓解 weight concentration / subuniverse fail。
        add_variant(neutralization=NEUTRALIZATION_INDUSTRY, truncation=tighter_truncation)
    else:
        add_variant(neutralization=NEUTRALIZATION_MARKET)

    if refine_candidate is not None:
        if {"CONCENTRATED_WEIGHT", "LOW_SUB_UNIVERSE_SHARPE"} & nearpass_failed_names:
            add_variant(neutralization=NEUTRALIZATION_INDUSTRY, truncation=tighter_truncation)
            add_variant(neutralization=NEUTRALIZATION_MARKET, truncation=tighter_truncation)
        if "LOW_TURNOVER" in nearpass_failed_names:
            add_variant(decay=SETTINGS_VARIANT_DECAY_FAST, truncation=tighter_truncation)
        elif "HIGH_TURNOVER" in nearpass_failed_names:
            add_variant(decay=SETTINGS_VARIANT_DECAY_SLOW, truncation=tighter_truncation)
        else:
            add_variant(decay=SETTINGS_VARIANT_DECAY_FAST)
            add_variant(decay=SETTINGS_VARIANT_DECAY_SLOW, truncation=tighter_truncation)

    return variants
