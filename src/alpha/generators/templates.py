"""
模板库管理模块

本模块负责管理和加载 Alpha 表达式模板库，包括默认模板库和
外部 JSON 文件模板库。模板库用于为不同类型的字段生成候选
Alpha 表达式。

模块内容：
    - default_template_library() -> TemplateLibrary: 返回内置默认模板库
    - load_template_library(path) -> TemplateLibrary: 从 JSON 文件加载模板库
"""

from __future__ import annotations

import json
import os

from ..config import BACKFILL_WINDOW
from ..exceptions import BrainAPIError
from ..models.base import TemplateLibrary


def default_template_library() -> TemplateLibrary:
    """
    返回内置默认模板库。

    当未提供外部模板库 JSON 文件时，使用此函数返回的默认模板集合。
    默认模板库包含约 45 个不同类型的模板，覆盖了常见的时间序列
    操作、向量聚合、分组统计等场景。

    模板表达式使用 {field} 占位符，在运行时根据具体字段名称进行展开。

    Returns:
        TemplateLibrary: 包含多个模板分类的字典，键为字段类型名称，
            值为该类型下的模板列表。

    模板分类包括：
        - default: 默认模板，适用于大多数 MATRIX 类型字段
        - VECTOR: 向量类型字段专用模板
        - GROUP: 分组类型字段专用模板
        - SET: 集合类型字段专用模板
        - STRING: 字符串类型字段专用模板
        - TEXT: 文本类型字段专用模板
        - BOOL: 布尔类型字段专用模板
        - BOOLEAN: 布尔类型字段专用模板（别名）

    Example:
        >>> library = default_template_library()
        >>> print(len(library["default"]))
        18
        >>> template = library["default"][0]
        >>> print(template["name"])
        ts_mean_20
        >>> print(template["expression"])
        rank(ts_mean({field}, 20))

    Note:
        每个模板字典包含以下字段：
            - name: 模板名称，用于识别和调试
            - expression: 模板表达式，包含 {field} 占位符
            - priority: 可选字段，表示模板的优先级（默认为 0）
    """
    bw = BACKFILL_WINDOW
    return {
        "default": [
            {"name": "ts_mean_20", "expression": "rank(ts_mean({field}, 20))", "priority": 122},
            {"name": "ts_mean_60", "expression": "rank(ts_mean({field}, 60))", "priority": 120},
            {"name": "ts_mean_120", "expression": "rank(ts_mean({field}, 120))", "priority": 118},
            {
                "name": f"backfill_{bw}",
                "expression": f"rank(ts_backfill({{field}}, {bw}))",
                "priority": 130,
            },
            {
                "name": "backfill_mean_60",
                "expression": f"rank(ts_mean(ts_backfill({{field}}, {bw}), 60))",
                "priority": 128,
            },
            {"name": "ts_rank_60", "expression": "rank(ts_rank({field}, 60))", "priority": 115},
            {"name": "ts_rank_120", "expression": "rank(ts_rank({field}, 120))", "priority": 113},
            {"name": "ts_zscore_60", "expression": "rank(ts_zscore({field}, 60))", "priority": 128},
            {
                "name": f"ts_zscore_{bw}",
                "expression": f"rank(ts_zscore(ts_backfill({{field}}, {bw}), {bw}))",
                "priority": 132,
            },
            {"name": "zscore", "expression": "rank(zscore({field}))", "priority": 124},
            {"name": "scale", "expression": "rank(scale({field}))", "priority": 120},
            {"name": "delta_20", "expression": "rank(ts_delta({field}, 20))", "priority": 135},
            {"name": "delta_60", "expression": "rank(ts_delta({field}, 60))", "priority": 132},
            # decay_linear 窗口变体 — decay_20 在 pv1 adjfactor 上 Sharpe=1.22（阈值 1.25，仅差 2.4%）
            {
                "name": "decay_10",
                "expression": f"rank(ts_decay_linear(ts_backfill({{field}}, {bw}), 10))",
                "priority": 126,
            },
            {
                "name": "decay_20",
                "expression": f"rank(ts_decay_linear(ts_backfill({{field}}, {bw}), 20))",
                "priority": 130,
            },
            {
                "name": "decay_30",
                "expression": f"rank(ts_decay_linear(ts_backfill({{field}}, {bw}), 30))",
                "priority": 128,
            },
            {
                "name": "decay_40",
                "expression": f"rank(ts_decay_linear(ts_backfill({{field}}, {bw}), 40))",
                "priority": 124,
            },
            # group_decay_20: 中性化版，针对 LOW_SHARPE 检查
            {
                "name": "group_decay_20",
                "expression": f"group_rank(ts_decay_linear(ts_backfill({{field}}, {bw}), 20), subindustry)",
                "priority": 132,
            },
            {"name": "stddev_60", "expression": "rank(ts_std_dev({field}, 60))", "priority": 118},
            {"name": "sum_20", "expression": "rank(ts_sum({field}, 20))", "priority": 110},
            {"name": "argmax_60", "expression": "rank(ts_arg_max({field}, 60))", "priority": 108},
            {"name": "argmin_60", "expression": "rank(ts_arg_min({field}, 60))", "priority": 105},
        ],
        "VECTOR": [
            {"name": "vec_avg_rank", "expression": "rank(vec_avg({field}))", "priority": 115},
            {
                "name": "vec_avg_ts_mean_20",
                "expression": "rank(ts_mean(vec_avg({field}), 20))",
                "priority": 112,
            },
            {
                "name": "vec_avg_ts_mean_60",
                "expression": "rank(ts_mean(vec_avg({field}), 60))",
                "priority": 110,
            },
            {
                "name": f"vec_avg_backfill_{bw}",
                "expression": f"rank(ts_backfill(vec_avg({{field}}), {bw}))",
                "priority": 116,
            },
            {
                "name": "vec_avg_ts_rank_60",
                "expression": "rank(ts_rank(vec_avg({field}), 60))",
                "priority": 108,
            },
            {
                "name": "vec_avg_ts_zscore_60",
                "expression": "rank(ts_zscore(vec_avg({field}), 60))",
                "priority": 114,
            },
            {
                "name": "vec_avg_zscore",
                "expression": "rank(zscore(vec_avg({field})))",
                "priority": 112,
            },
            {
                "name": "vec_avg_scale",
                "expression": "rank(scale(vec_avg({field})))",
                "priority": 108,
            },
            {
                "name": "vec_avg_delta_20",
                "expression": "rank(ts_delta(vec_avg({field}), 20))",
                "priority": 122,
            },
            {
                "name": "vec_avg_decay_10",
                "expression": f"rank(ts_decay_linear(ts_backfill(vec_avg({{field}}), {bw}), 10))",
                "priority": 120,
            },
            {
                "name": "vec_avg_decay_20",
                "expression": f"rank(ts_decay_linear(ts_backfill(vec_avg({{field}}), {bw}), 20))",
                "priority": 124,
            },
            {
                "name": "vec_avg_decay_30",
                "expression": f"rank(ts_decay_linear(ts_backfill(vec_avg({{field}}), {bw}), 30))",
                "priority": 122,
            },
            {
                "name": "vec_avg_decay_40",
                "expression": f"rank(ts_decay_linear(ts_backfill(vec_avg({{field}}), {bw}), 40))",
                "priority": 118,
            },
        ],
        "GROUP": [
            {"name": "vec_avg_rank", "expression": "rank(vec_avg({field}))", "priority": 115},
            {
                "name": "vec_avg_ts_mean_20",
                "expression": "rank(ts_mean(vec_avg({field}), 20))",
                "priority": 112,
            },
            {
                "name": "vec_avg_ts_rank_60",
                "expression": "rank(ts_rank(vec_avg({field}), 60))",
                "priority": 108,
            },
            {
                "name": "vec_avg_ts_zscore_60",
                "expression": "rank(ts_zscore(vec_avg({field}), 60))",
                "priority": 114,
            },
        ],
        "SET": [
            {"name": "vec_avg_rank", "expression": "rank(vec_avg({field}))", "priority": 115},
            {
                "name": "vec_avg_ts_mean_20",
                "expression": "rank(ts_mean(vec_avg({field}), 20))",
                "priority": 112,
            },
            {
                "name": "vec_avg_ts_rank_60",
                "expression": "rank(ts_rank(vec_avg({field}), 60))",
                "priority": 108,
            },
            {
                "name": "vec_avg_ts_zscore_60",
                "expression": "rank(ts_zscore(vec_avg({field}), 60))",
                "priority": 114,
            },
        ],
        "STRING": [
            {"name": "raw_field", "expression": "{field}", "priority": 105},
            {"name": "rank_raw_field", "expression": "rank({field})", "priority": 100},
        ],
        "TEXT": [
            {"name": "raw_field", "expression": "{field}", "priority": 105},
            {"name": "rank_raw_field", "expression": "rank({field})", "priority": 100},
        ],
        "BOOL": [
            {"name": "raw_field", "expression": "{field}", "priority": 105},
            {"name": "rank_raw_field", "expression": "rank({field})", "priority": 100},
        ],
        "BOOLEAN": [
            {"name": "raw_field", "expression": "{field}", "priority": 105},
            {"name": "rank_raw_field", "expression": "rank({field})", "priority": 100},
        ],
    }


def load_template_library(path: str) -> TemplateLibrary:
    """
    从 JSON 文件加载并校验模板库。

    将模板库外部化到 JSON 文件，可以方便地扩展或缩小搜索覆盖范围，
    而无需修改 Python 代码。如果文件路径无效或加载失败，将返回
    默认模板库。

    Args:
        path (str): 模板库 JSON 文件的路径。如果为空字符串或文件不存在，
            将返回默认模板库。

    Returns:
        TemplateLibrary: 加载并校验后的模板库字典。

    Raises:
        BrainAPIError: 当 JSON 文件格式错误或不符合模板库结构要求时抛出。

    JSON 文件格式要求：
        - 文件必须包含一个 JSON 对象（字典）
        - 键必须是字符串，表示字段类型（如 "default", "VECTOR" 等）
        - 值必须是列表，包含该类型的模板对象
        - 每个模板对象必须包含：
            - name: 非空字符串，模板名称
            - expression: 非空字符串，模板表达式
            - priority: 可选整数，模板优先级（默认为 0）

    Example:
        >>> # 加载外部模板库文件
        >>> library = load_template_library("templates.json")
        >>> print(library.keys())
        dict_keys(['default', 'MATRIX'])

        >>> # 文件不存在时返回默认模板库
        >>> library = load_template_library("")
        >>> print(len(library))
        8

        >>> # JSON 文件示例
        >>> # {
        >>> #     "default": [
        >>> #         {"name": "simple_rank", "expression": "rank({field})", "priority": 100}
        >>> #     ]
        >>> # }

    Note:
        模板表达式中的 {field} 占位符将在运行时替换为实际的字段名称。
        优先级越高的模板在候选排序时越靠前。
    """
    # Externalizing the template library makes it easy to expand/shrink
    # search coverage without touching the Python code.
    if not path or not os.path.exists(path):
        return default_template_library()

    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        raise BrainAPIError(f"读取模板库文件失败 {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise BrainAPIError(f"模板库文件 {path} 必须包含一个 JSON 对象。")

    validated: TemplateLibrary = {}
    for field_type, templates in payload.items():
        if not isinstance(field_type, str):
            raise BrainAPIError("模板库的键必须是字符串。")
        if not isinstance(templates, list):
            raise BrainAPIError(f"模板库条目 '{field_type}' 必须是一个列表。")
        validated[field_type] = []
        for index, item in enumerate(templates):
            if not isinstance(item, dict):
                raise BrainAPIError(f"模板 '{field_type}[{index}]' 必须是一个对象。")
            if "name" not in item or "expression" not in item:
                raise BrainAPIError(
                    f"模板 '{field_type}[{index}]' 必须包含 name 和 expression 字段。"
                )
            if not isinstance(item["name"], str) or not item["name"].strip():
                raise BrainAPIError(f"模板 '{field_type}[{index}]' 的 name 必须是非空字符串。")
            if not isinstance(item["expression"], str) or not item["expression"].strip():
                raise BrainAPIError(
                    f"模板 '{field_type}[{index}]' 的 expression 必须是非空字符串。"
                )
            priority = item.get("priority", 0)
            if not isinstance(priority, int):
                raise BrainAPIError(f"模板 '{field_type}[{index}]' 的 priority 必须是整数。")
            validated[field_type].append(
                {
                    "name": item["name"].strip(),
                    "expression": item["expression"].strip(),
                    "priority": priority,
                }
            )
    return validated
