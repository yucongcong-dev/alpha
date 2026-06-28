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

import hashlib
import json
from typing import Any

import calendar
from datetime import date

from ..config import (
    get_simulation_default_end_date,
    get_simulation_default_start_date,
    get_yaml_config,
)
from ..models.base import SettingsVariant


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


# ---------------------------------------------------------------------------
# 硬编码官网默认值 —— settings.yaml 不可用时回退
# 与 Brain 官网 Settings 面板默认值严格一致:
#   LANGUAGE=Fast Expression, INSTRUMENT TYPE=Equity, REGION=USA,
#   UNIVERSE=TOP3000, DELAY=1, NEUTRALIZATION=Subindustry,
#   DECAY=4, TRUNCATION=0.08, PASTEURIZATION=On,
#   UNIT HANDLING=Verify, NAN HANDLING=Off, TEST PERIOD=1Y 0M
# ---------------------------------------------------------------------------
# key = Brain API 参数名 (camelCase)，与 settings.yaml 命名一致
_WEBSITE_DEFAULTS: dict[str, Any] = {
    "language": "FASTEXPR",
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "neutralization": "SUBINDUSTRY",
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
    "delay": 1, "decay": 4, "neutralization": "SUBINDUSTRY", "truncation": 0.08,
    "pasteurization": "ON", "unit_handling": "VERIFY", "nan_handling": "OFF",
    "language": "FASTEXPR",
}

# TEST PERIOD 硬编码官网默认: 1Y 0M
_TEST_PERIOD_DEFAULTS = {"testPeriodYears": 1, "testPeriodMonths": 0}


def _read_simulation_from_yaml() -> dict[str, Any] | None:
    """从 settings.yaml 读取 global.simulation 节点，不可用时返回 None。"""
    yaml_cfg = get_yaml_config()
    if not yaml_cfg:
        return None
    global_cfg = yaml_cfg.get("global")
    if not isinstance(global_cfg, dict):
        return None
    sim = global_cfg.get("simulation")
    return sim if isinstance(sim, dict) else None


def _resolve_setting(yaml_sim: dict[str, Any] | None, args: Any, api_key: str) -> Any:
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


def build_simulation_payload(args: Any, expression: str) -> dict[str, Any]:
    """
    从 settings.yaml 读取配置，构建模拟请求体。

    优先级: CLI 参数 > settings.yaml > 硬编码官网默认值。
    YAML key 即为 Brain API payload key (camelCase)，无需翻译。

    Args:
        args: 命令行参数对象 (argparse.Namespace)。
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
        total_months = (years or 0) * 12 + (months or 0)
        if total_months > 0:
            today = date.today()
            # 往前推 total_months 个月，日期不超过目标月末
            comp_months = today.year * 12 + today.month - 1  # 0-based
            comp_months -= total_months
            cy, cm = divmod(comp_months, 12)
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


def build_setting_variants(
    args: Any,
    template_name: str,
    expression: str,
    *,
    field_feedback: dict[str, Any] | None = None,
) -> list[SettingsVariant]:
    """
    从 settings.yaml 读取单一配置，返回仅含一组 settings 的列表。

    不再生成多参数变体：所有表达式共享 settings.yaml 中定义的统一配置。
    优先级: CLI > YAML > 硬编码官网默认值。

    Args:
        args: 命令行参数对象。
        template_name: 模板名称（保留兼容，未使用）。
        expression: Alpha 表达式字符串。
        field_feedback: 保留兼容，未使用。

    Returns:
        List[SettingsVariant]: 包含唯一一组 settings 的列表。
    """
    settings = build_simulation_payload(args, expression)["settings"]
    return [settings]
