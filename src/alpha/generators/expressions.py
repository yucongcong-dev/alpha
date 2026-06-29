"""
表达式构建模块

本模块负责构建、排序和管理 Alpha 表达式候选，包括字段配对发现、
模板优先级调整、表达式家族分类等功能。通过智能的表达式生成策略，
提高 Alpha 发现的效率和质量。

模块内容：
    - tokenize_field_name(): 将字段名拆分为 token
    - score_partner_candidate(): 评估字段配对得分
    - discover_partner_fields(): 发现配对字段
    - sort_templates_by_priority(): 按优先级排序模板
    - limit_templates(): 限制模板数量
    - classify_expression_family(): 分类表达式家族
    - is_legacy_family(): 判断是否为 legacy 家族
    - apply_similarity_penalty(): 应用相似度惩罚
    - adaptive_template_priority_adjustment(): 自适应优先级调整
    - apply_adaptive_priority(): 应用自适应优先级
    - cap_templates_per_family(): 限制家族模板数量
    - build_expression_candidates(): 构建表达式候选
"""

from __future__ import annotations

from collections.abc import Sequence
import json
import os
import re
from typing import Any

from ..config import (
    ALLOWED_EXTERNAL_RATIO_PARTNERS,
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    CHECK_LOW_TURNOVER,
    DELTA_STD_PRIORITY_BOOST,
    EXPR_ITER_BOOST_THRESHOLD,
    EXPR_MUTATION_EXTEND_THRESHOLD,
    EXPR_NEARPASS_BOOST_THRESHOLD,
    EXPR_RATIO_PENALTY_THRESHOLD,
    FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
    FUNDAMENTAL6_ACCOUNT_TEMPLATE_BOOST,
    FUNDAMENTAL6_DISABLED_TEMPLATES,
    FUNDAMENTAL6_HIGH_CONVICTION_RATIO_PAIRS,
    FUNDAMENTAL6_PROTECTED_TEMPLATES,
    FUNDAMENTAL6_TEMPLATE_PREFIX_PENALTIES,
    FUNDAMENTAL6_TEMPLATE_PRIORITY_PENALTIES,
    NEGATIVE_RAW_FIELDS,
    POSITIVE_RAW_FIELDS,
    RATIO_KEYWORDS,
    RATIO_PARTNER_CANDIDATES,
    STATS_DEFAULT_SCORE,
    UNKNOWN_FAMILY,
    get_backfill_window,
)
from ..models.base import TemplateLibrary
from ..utils.helpers import choose_field_name, choose_field_type

# 预编译正则表达式（性能优化）
_TOKENIZE_REGEX: re.Pattern = re.compile(r"[^a-z0-9]+")
"""字段名分词正则模式（预编译）"""

# ---- 模板黑名单（按 dataset_id 分层） ----
_BLACKLIST_CACHE: dict[str, dict[str, Any]] = {}
"""按 dataset_id 缓存的黑名单数据（懒加载）。每个值为 {"names": set, "patterns": list}"""
_DEFAULT_AVOID_RULES_CACHE: list[dict[str, str]] | None = None
"""跨数据集默认规避规则缓存（一次加载）。"""
def _fundamental6_template_priority_adjustment(template_name: str) -> int:
    """压低 generic library 模板，给 account / ratio / long-window 方向让路。"""
    lower_name = template_name.lower()
    if lower_name in FUNDAMENTAL6_TEMPLATE_PRIORITY_PENALTIES:
        return FUNDAMENTAL6_TEMPLATE_PRIORITY_PENALTIES[lower_name]
    for prefixes, penalty in FUNDAMENTAL6_TEMPLATE_PREFIX_PENALTIES.items():
        if lower_name.startswith(prefixes):
            return penalty
    return 0


def _resolve_blacklist_project_root() -> str:
    """查找项目根目录（与 data 目录同级的 src 目录所在路径）。"""
    current = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(current, "..", "..", ".."))


def _load_default_avoid_rules() -> list[dict[str, str]]:
    """加载跨数据集默认规避规则 template_blacklist.json。"""
    global _DEFAULT_AVOID_RULES_CACHE
    if _DEFAULT_AVOID_RULES_CACHE is not None:
        return _DEFAULT_AVOID_RULES_CACHE
    candidates = [
        os.path.join(_resolve_blacklist_project_root(), "data", "template_blacklist.json"),
        os.path.join(os.getcwd(), "data", "template_blacklist.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                _DEFAULT_AVOID_RULES_CACHE = raw.get("_default_auto_avoid_rules", [])
                return _DEFAULT_AVOID_RULES_CACHE
            except (json.JSONDecodeError, OSError):
                pass
    _DEFAULT_AVOID_RULES_CACHE = []
    return _DEFAULT_AVOID_RULES_CACHE


def _load_blacklist(dataset_id: str) -> None:
    """按 dataset_id 加载专属黑名单文件 template_blacklist_{dataset_id}.json。"""
    global _BLACKLIST_CACHE
    if dataset_id in _BLACKLIST_CACHE:
        return  # 已缓存

    names: set[str] = set()
    patterns: list[str] = []

    # 1. 加载数据集专属黑名单文件
    project_root = _resolve_blacklist_project_root()
    filename = f"template_blacklist_{dataset_id}.json"
    candidates = [
        os.path.join(project_root, "data", filename),
        os.path.join(os.getcwd(), "data", filename),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    ds_raw = json.load(fh)
                if isinstance(ds_raw, dict):
                    for item in ds_raw.get("blacklisted_templates", []):
                        if isinstance(item, dict) and item.get("name"):
                            names.add(item["name"])
                    for rule in ds_raw.get("auto_avoid_rules", []):
                        if isinstance(rule, dict) and rule.get("pattern"):
                            patterns.append(rule["pattern"])
            except (json.JSONDecodeError, OSError):
                pass
            break  # 找到文件即停

    # 2. 加载跨数据集默认规避规则（对所有数据集生效）
    for rule in _load_default_avoid_rules():
        if isinstance(rule, dict) and rule.get("pattern"):
            if rule["pattern"] not in patterns:
                patterns.append(rule["pattern"])

    _BLACKLIST_CACHE[dataset_id] = {"names": names, "patterns": patterns}


def _is_blacklisted_template(template_name: str, expression: str = "", *, dataset_id: str = "") -> bool:
    """检查模板名称或表达式是否在指定数据集的黑名单中。

    Args:
        template_name: 模板名称。
        expression: 表达式文本（用于模式匹配）。
        dataset_id: 数据集 ID。为空时仅检查跨数据集默认规则。

    Returns:
        bool: 在黑名单中返回 True。
    """
    if dataset_id == "fundamental6" and template_name in FUNDAMENTAL6_PROTECTED_TEMPLATES:
        return False
    if dataset_id:
        _load_blacklist(dataset_id)
        cached = _BLACKLIST_CACHE.get(dataset_id, {})
        if template_name in cached.get("names", set()):
            return True
        for pattern in cached.get("patterns", []):
            if pattern in expression:
                return True
        # fundamental6 特例：group_ratio_delta_rank 全系列黑名单
        if dataset_id == "fundamental6" and "group_ratio_delta_rank" in template_name:
            return True
    else:
        # 无 dataset_id：仅检查跨数据集默认规则
        for rule in _load_default_avoid_rules():
            if isinstance(rule, dict) and rule.get("pattern", "") in expression:
                return True
    return False


def tokenize_field_name(field_name: str) -> list[str]:
    """
    将字段名拆分为小写字母数字 token。

    通过正则表达式将字段名分解为独立的字母数字单元，
    用于字段名称的相似性比较和配对打分。

    Args:
        field_name (str): 要拆分的字段名称。

    Returns:
        list[str]: 拆分后的小写 token 列表，去除空 token。

    Example:
        >>> tokens = tokenize_field_name("sales_per_share")
        >>> print(tokens)
        ['sales', 'per', 'share']

        >>> tokens = tokenize_field_name("EBITDA-2024")
        >>> print(tokens)
        ['ebitda', '2024']
    """
    return [token for token in _TOKENIZE_REGEX.split(field_name.lower()) if token]


def score_partner_candidate(field_name: str, partner_name: str) -> int:
    """
    启发式打分两个字段是否适合作为比值配对。

    通过多种启发式规则评估两个字段是否适合构建比率型 Alpha 表达式。
    得分越高表示配对越合适。

    Args:
        field_name (str): 主字段名称。
        partner_name (str): 配对字段名称。

    Returns:
        int: 配对得分。负值表示不适合配对，正值越大表示越适合。

    打分规则：
        - 如果两个字段相同，返回极低分数（-10000）
        - 如果配对字段在推荐列表中，加分 180+额外排名加分
        - 如果字段名包含关键词关联，加分 100 或 80
        - 如果有共同 token，每个 token 加分 10
        - 如果 token 出现在配对字段名中，每个加分 5
        - 特定字段名加分（assets, equity 等）

    Example:
        >>> score = score_partner_candidate("debt", "cap")
        >>> print(score)
        210  # debt 的推荐配对包含 cap

        >>> score = score_partner_candidate("sales", "sales")
        >>> print(score)
        -10000  # 相同字段不适合配对
    """
    if field_name == partner_name:
        return -10_000
    field_tokens = set(tokenize_field_name(field_name))
    partner_tokens = set(tokenize_field_name(partner_name))
    score = 0
    # Hard-code a few high-conviction ratio pairings so the search prefers
    # combinations already hinted by this account's submitted alpha history.
    preferred_partners = RATIO_PARTNER_CANDIDATES.get(field_name, ())
    if partner_name in preferred_partners:
        score += 180
        preferred_rank = preferred_partners.index(partner_name)
        score += max(0, 30 - preferred_rank * 5)
    if partner_name in RATIO_KEYWORDS.get(field_name, ()):
        score += 100
    if field_name in RATIO_KEYWORDS.get(partner_name, ()):
        score += 80
    if field_tokens & partner_tokens:
        score += 10 * len(field_tokens & partner_tokens)
    for token in field_tokens:
        if token and token in partner_name:
            score += 5
    if partner_name in {
        "assets",
        "equity",
        "debt",
        "liabilities",
        "cash",
        "enterprise_value",
        "cap",
    }:
        score += 15
    if partner_name in {"fnd6_mkvalt", "fnd6_mkvaltq", "liabilities_curr"}:
        score += 25
    return score


def discover_partner_fields(
    field_name: str,
    all_fields: Sequence[dict[str, Any]],
    *,
    limit: int = 4,
    use_curated_heuristics: bool = True,
) -> list[str]:
    """
    为比值类模板扩展寻找可能合适的配对字段。

    根据启发式规则和推荐配置，从所有字段中筛选出最合适的
    配对字段，用于构建比率型 Alpha 表达式。

    Args:
        field_name (str): 主字段名称。
        all_fields (Sequence[dict[str, Any]]): 所有可用字段的列表。
        limit (int): 返回的配对字段数量上限。默认为 4。
        use_curated_heuristics (bool): 是否使用精选启发式规则。默认为 True。

    Returns:
        list[str]: 配对字段名称列表，按得分排序。

    Example:
        >>> fields = [
        ...     {"name": "cap", "type": "MATRIX"},
        ...     {"name": "assets", "type": "MATRIX"},
        ...     {"name": "sales", "type": "MATRIX"},
        ... ]
        >>> partners = discover_partner_fields("debt", fields, limit=2)
        >>> print(partners)
        ['cap', 'assets']
    """
    if not use_curated_heuristics:
        return []

    candidates: list[tuple[int, str]] = []
    available_by_name = {
        choose_field_name(item): item for item in all_fields if choose_field_type(item) == "MATRIX"
    }

    # Seed the candidate list with curated pairings first so extremely
    # important ratios like debt/cap are never crowded out by weaker matches.
    for partner_name in RATIO_PARTNER_CANDIDATES.get(field_name, ()):
        if partner_name == field_name:
            continue
        if partner_name not in available_by_name and partner_name not in ALLOWED_EXTERNAL_RATIO_PARTNERS:
            continue
        candidates.append((10_000 - len(candidates), partner_name))

    for item in all_fields:
        partner_name = choose_field_name(item)
        partner_type = choose_field_type(item)
        if partner_name == field_name or partner_type != "MATRIX":
            continue
        score = score_partner_candidate(field_name, partner_name)
        if score <= 0:
            continue
        candidates.append((score, partner_name))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    seen: set = set()
    result: list[str] = []
    for _, partner_name in candidates:
        if partner_name in seen:
            continue
        seen.add(partner_name)
        result.append(partner_name)
        if len(result) >= limit:
            break
    return result


def sort_templates_by_priority(
    templates: Sequence[tuple[str, str, int]],
) -> list[tuple[str, str, int]]:
    """
    按有效优先级从高到低排序候选模板。

    优先级越高（数值越大）的模板排序越靠前，优先被测试。
    这样可以让最可能成功的模板先运行，提高整体效率。

    Args:
        templates (Sequence[tuple[str, str, int]]): 模板列表，
            每个元素为 (name, expression, priority) 元组。

    Returns:
        list[tuple[str, str, int]]: 排序后的模板列表。

    Example:
        >>> templates = [("low", "expr1", 10), ("high", "expr2", 100), ("mid", "expr3", 50)]
        >>> sorted_templates = sort_templates_by_priority(templates)
        >>> print(sorted_templates[0][0])
        'high'
    """
    # Higher-priority templates run first so likely winners are tested earlier.
    return sorted(templates, key=lambda item: (-item[2], item[0], item[1]))


def limit_templates(
    templates: list[tuple[str, str, int]],
    max_templates_per_field: int,
) -> list[tuple[str, str, int]]:
    """
    在排序与多样化之后应用字段级模板数量上限。

    通过硬性限制每个字段最多测试的模板数量，控制测试规模
    和资源消耗。

    Args:
        templates (list[tuple[str, str, int]]): 已排序的模板列表。
        max_templates_per_field (int): 每个字段的模板数量上限。
            如果为 0 或负数，不限制数量。

    Returns:
        list[tuple[str, str, int]]: 限制后的模板列表。

    Example:
        >>> templates = [("t1", "e1", 10), ("t2", "e2", 20), ("t3", "e3", 30)]
        >>> limited = limit_templates(templates, max_templates_per_field=2)
        >>> print(len(limited))
        2
    """
    if max_templates_per_field <= 0:
        return templates
    return templates[:max_templates_per_field]


def classify_expression_family(template_name: str, expression: str) -> str:
    """
    将表达式归类到粗粒度家族，用于剪枝与排序。

    通过分析模板名称和表达式结构，将表达式分类到不同的家族。
    家族分类用于应用相似的惩罚、优先级调整和数量限制。

    Args:
        template_name (str): 模板名称。
        expression (str): 表达式字符串。

    Returns:
        str: 家族名称。

    家族分类包括：
        - group_rank_delta: 分组排名变化型
        - rank_delta: 排名变化型
        - legacy_level: 传统层级型（原始字段、排名等）
        - legacy_ratio: 传统比率型
        - legacy_neg_ratio: 传统负比率型
        - group_ratio_level: 分组比率层级型
        - group_zscore: 分组 Z-score 型
        - group_vol_scaled_delta: 分组波动标准化变化型
        - group_mean_spread: 分组均值差型
        - legacy_group_level: 传统分组层级型
        - vol_scaled_delta: 波动标准化变化型
        - mean_spread: 均值差型
        - rank_spread: 排名差型
        - zscore_time: 时间序列 Z-score 型
        - decayed_delta: 衰减变化型
        - decayed_ratio: 衰减比率型
        - mean_ratio: 均值比率型
        - 其他: 使用模板名称的前缀作为家族名

    Example:
        >>> family = classify_expression_family(
        ...     "group_rank_delta", "group_rank(ts_delta(rank(close), 20), subindustry)"
        ... )
        >>> print(family)
        'group_rank_delta'
    """
    lower_name = template_name.lower()
    lower_expr = expression.lower()
    if "group_rank(ts_delta(rank(" in lower_expr:
        return "group_rank_delta"
    if "rank(ts_delta(rank(" in lower_expr:
        return "rank_delta"
    if lower_name in {"raw_field", "neg_raw_field", "rank_raw_field"}:
        return "legacy_level"
    if lower_name.startswith(("raw_ratio_", "ratio_", "rank_ratio_")):
        return "legacy_ratio"
    if lower_name.startswith("neg_ratio_"):
        return "legacy_neg_ratio"
    if lower_name.startswith("group_rank_ratio_"):
        return "group_ratio_level"
    if lower_name.startswith("group_rank_") or "group_rank(" in lower_expr:
        if "ts_zscore" in lower_expr:
            return "group_zscore"
        if "ts_delta" in lower_expr and "ts_std_dev" in lower_expr:
            return "group_vol_scaled_delta"
        if "ts_mean" in lower_expr and "-" in lower_expr:
            return "group_mean_spread"
        return "legacy_group_level"
    if "group_neutralize" in lower_expr and "ts_decay_linear" in lower_expr:
        return "neutralize_decay"
    if "ts_decay_linear" in lower_expr and "ts_delta" not in lower_expr and "/" not in lower_expr:
        return "decay_level"
    if "ts_rank" in lower_expr:
        return "ts_rank"
    if "ts_delta" in lower_expr and "ts_std_dev" in lower_expr:
        return "vol_scaled_delta"
    if "ts_mean" in lower_expr and "-" in lower_expr:
        return "mean_spread"
    if "ts_rank" in lower_expr and "-" in lower_expr:
        return "rank_spread"
    if "ts_zscore" in lower_expr:
        return "zscore_time"
    if "ts_decay_linear" in lower_expr and "ts_delta" in lower_expr:
        return "decayed_delta"
    if "/" in lower_expr and "ts_decay_linear" in lower_expr:
        return "decayed_ratio"
    if "ts_mean" in lower_expr and "/" in lower_expr:
        return "mean_ratio"
    prefix = lower_name.split("_", 1)[0]
    return prefix or UNKNOWN_FAMILY


def is_legacy_family(template_name: str, expression: str) -> bool:
    """
    判断模板是否属于历史上较易过度使用的 legacy 家族。

    Legacy 家族的表达式形式较为简单，历史上容易被过度使用，
    需要通过惩罚降低其优先级，让多样化的候选优先运行。

    Args:
        template_name (str): 模板名称。
        expression (str): 表达式字符串。

    Returns:
        bool: 如果属于 legacy 家族返回 True，否则返回 False。

    Legacy 家族包括：
        - legacy_level: 传统层级型
        - legacy_group_level: 传统分组层级型
        - legacy_ratio: 传统比率型
        - legacy_neg_ratio: 传统负比率型
        - group_ratio_level: 分组比率层级型

    Example:
        >>> is_legacy = is_legacy_family("raw_field", "close")
        >>> print(is_legacy)
        True

        >>> is_legacy = is_legacy_family(
        ...     "group_zscore", "group_rank(ts_zscore(close, 60), subindustry)"
        ... )
        >>> print(is_legacy)
        False
    """
    return classify_expression_family(template_name, expression) in {
        "legacy_level",
        "legacy_group_level",
        "legacy_ratio",
        "legacy_neg_ratio",
        "group_ratio_level",
    }


# 相似度惩罚偏移量：家族名 -> 惩罚减免值
_SIMILARITY_PENALTY_OFFSETS: dict[str, int] = {
    "legacy_level": 0,
    "legacy_group_level": 6,
    "legacy_ratio": 10,
    "legacy_neg_ratio": 8,
    "group_ratio_level": 14,
}


def apply_similarity_penalty(
    templates: Sequence[tuple[str, str, int]],
    legacy_similarity_penalty: int,
) -> list[tuple[str, str, int]]:
    """
    对 legacy 形态模板施加相似度惩罚，让多样化候选优先运行。

    通过降低 legacy 家族模板的优先级，鼓励多样化的表达式形式，
    避免 Alpha 过度集中在传统模式上。

    Args:
        templates (Sequence[tuple[str, str, int]]): 模板列表。
        legacy_similarity_penalty (int): legacy 家族的惩罚分数。

    Returns:
        list[tuple[str, str, int]]: 应用惩罚后的模板列表。

    惩罚规则（通过 _SIMILARITY_PENALTY_OFFSETS 表驱动）：
        - legacy_level: 全额惩罚
        - legacy_group_level: 惩罚减 6
        - legacy_ratio: 惩罚减 10
        - legacy_neg_ratio: 惩罚减 8
        - group_ratio_level: 惩罚减 14

    Example:
        >>> templates = [("raw", "close", 100), ("group_zscore", "expr", 100)]
        >>> penalized = apply_similarity_penalty(templates, legacy_similarity_penalty=30)
        >>> print(penalized[0][2])  # raw 字段优先级降低
        70
    """
    penalized: list[tuple[str, str, int]] = []
    for name, expression, priority in templates:
        family = classify_expression_family(name, expression)
        offset = _SIMILARITY_PENALTY_OFFSETS.get(family)
        penalty = max(legacy_similarity_penalty - offset, 0) if offset is not None else 0
        penalized.append((name, expression, priority - penalty))
    return penalized


def dominant_failed_check_names(counts: dict[str, int], limit: int = 4) -> set:
    """
    返回失败检查计数最高的若干名称。

    从失败检查计数字典中提取出现次数最多的失败类型，
    用于指导模板优先级的自适应调整。

    Args:
        counts (dict[str, int]): 失败检查计数字典。
        limit (int): 返回的名称数量上限。默认为 4。

    Returns:
        set: 失败检查名称集合。

    Example:
        >>> counts = {"LOW_SHARPE": 10, "LOW_TURNOVER": 5, "LOW_FITNESS": 8}
        >>> names = dominant_failed_check_names(counts, limit=2)
        >>> print(names)
        {'LOW_SHARPE', 'LOW_FITNESS'}
    """
    return {
        name
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        if count > 0
    }


def merge_failed_check_counts(*count_maps: dict[str, Any]) -> dict[str, int]:
    """
    合并多个失败检查计数字典。

    将多个来源的失败检查计数合并为一个字典，
    用于综合分析失败模式。

    Args:
        *count_maps: 可变数量的失败检查计数字典。

    Returns:
        dict[str, int]: 合并后的计数字典。

    Example:
        >>> counts1 = {"LOW_SHARPE": 10}
        >>> counts2 = {"LOW_TURNOVER": 5, "LOW_SHARPE": 3}
        >>> merged = merge_failed_check_counts(counts1, counts2)
        >>> print(merged["LOW_SHARPE"])
        13
    """
    merged: dict[str, int] = {}
    for count_map in count_maps:
        for name, count in count_map.items():
            if not isinstance(count, int):
                continue
            merged[str(name)] = merged.get(str(name), 0) + count
    return merged


# ---------------------------------------------------------------------------
# 自适应优先级调整 - 家族分类集合（表驱动辅助）
# ---------------------------------------------------------------------------

_GROUP_FAMILIES = {
    "group_rank_delta",
    "group_zscore",
    "group_mean_spread",
    "group_vol_scaled_delta",
}
_SIGNAL_FAMILIES = {
    "neutralize_decay",
    "zscore_time",
    "ts_rank",
    "decay_level",
    "rank_spread",
    "mean_spread",
    "vol_scaled_delta",
    "rank_delta",
    "decayed_delta",
}
_LEGACY_FAMILIES = {
    "legacy_level",
    "legacy_group_level",
    "legacy_ratio",
    "legacy_neg_ratio",
    "group_ratio_level",
}
_LEGACY_BASIC = {"legacy_level", "legacy_group_level"}

# (trigger_check_names, condition(family, lower_name) → bool, adjustment)
# 当任意 trigger 出现在 dominant_names 中且 condition 成立时应用 adjustment。
_PRIORITY_RULES: list[tuple[set[str], Any, int]] = [
    # --- LOW_SHARPE / LOW_SUB_UNIVERSE_SHARPE ---
    (
        {CHECK_LOW_SHARPE, CHECK_LOW_SUB_UNIVERSE_SHARPE},
        lambda f, n: f.startswith("group_") or f in _GROUP_FAMILIES,
        28,
    ),
    ({CHECK_LOW_SHARPE, CHECK_LOW_SUB_UNIVERSE_SHARPE}, lambda f, n: f in _SIGNAL_FAMILIES, 18),
    ({CHECK_LOW_SHARPE, CHECK_LOW_SUB_UNIVERSE_SHARPE}, lambda f, n: f in _LEGACY_FAMILIES, -35),
    # --- LOW_FITNESS ---
    ({CHECK_LOW_FITNESS}, lambda f, n: "delta" in f or "spread" in f or n.startswith("iter_"), 22),
    ({CHECK_LOW_FITNESS}, lambda f, n: f in _LEGACY_BASIC, -25),
    ({CHECK_LOW_FITNESS}, lambda f, n: f in {"group_vol_scaled_delta", "vol_scaled_delta"}, -18),
    # --- LOW_TURNOVER ---
    (
        {CHECK_LOW_TURNOVER},
        lambda f, n: "delta" in f or n.startswith(("iter_rank_delta", "iter_rank_then_delta")),
        30,
    ),
    (
        {CHECK_LOW_TURNOVER},
        lambda f, n: f in {"legacy_level", "legacy_group_level", "mean_spread"},
        -18,
    ),
    # --- HIGH_TURNOVER ---
    (
        {CHECK_HIGH_TURNOVER},
        lambda f, n: f in {"mean_spread", "decayed_delta", "decayed_ratio"},
        20,
    ),
    ({CHECK_HIGH_TURNOVER}, lambda f, n: "delta" in f, -20),
    # --- CONCENTRATED_WEIGHT ---
    (
        {CHECK_CONCENTRATED_WEIGHT},
        lambda f, n: f.startswith("group_") and f not in {"group_vol_scaled_delta", "vol_scaled_delta"},
        24,
    ),
    ({CHECK_CONCENTRATED_WEIGHT}, lambda f, n: f in {"group_vol_scaled_delta", "vol_scaled_delta"}, -30),
    (
        {CHECK_CONCENTRATED_WEIGHT},
        lambda f, n: f in {"legacy_ratio", "legacy_neg_ratio", "group_ratio_level"},
        -30,
    ),
]


def adaptive_template_priority_adjustment(
    template_name: str,
    expression: str,
    *,
    field_feedback: dict[str, Any] | None,
    global_failed_check_counts: dict[str, int],
) -> int:
    """
    根据字段与全局失败分布动态调整模板优先级（声明式规则表驱动）。

    通过分析历史失败检查模式，智能调整模板的优先级，
    让更可能通过检查的表达式形式优先测试。

    Args:
        template_name (str): 模板名称。
        expression (str): 表达式字符串。
        field_feedback (dict[str, Any] | None): 字段反馈数据。
        global_failed_check_counts (dict[str, int]): 全局失败检查计数。

    Returns:
        int: 优先级调整值（可正可负）。

    调整规则由 _PRIORITY_RULES 表驱动，外加字段反馈和组合惩罚两个特殊处理。
    """
    field_counts = field_feedback.get("failed_check_counts", {}) if field_feedback else {}
    dominant_names = dominant_failed_check_names(
        merge_failed_check_counts(global_failed_check_counts, field_counts)
    )
    family = classify_expression_family(template_name, expression)
    lower_name = template_name.lower()
    adjustment = 0

    # 核心调整规则：声明式表驱动
    for triggers, condition, adj in _PRIORITY_RULES:
        if triggers & dominant_names and condition(family, lower_name):
            adjustment += adj

    # 组合惩罚：HIGH_TURNOVER + CONCENTRATED_WEIGHT 同时出现时对 spread 模板强惩罚
    if {CHECK_HIGH_TURNOVER, CHECK_CONCENTRATED_WEIGHT} <= dominant_names:
        if family in {"rank_spread", "mean_spread"}:
            adjustment -= 50
        if "zscore" in lower_name and "spread" in lower_name:
            adjustment -= 45

    # 字段反馈调整：基于历史 best_score 做精细加减
    if field_feedback:
        best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE))
        if best_score >= EXPR_NEARPASS_BOOST_THRESHOLD and lower_name.startswith("iter_nearpass_"):
            adjustment += 40
        elif best_score >= EXPR_ITER_BOOST_THRESHOLD and lower_name.startswith("iter_"):
            adjustment += 18
        if best_score >= EXPR_RATIO_PENALTY_THRESHOLD and family in _LEGACY_FAMILIES:
            adjustment -= 40
        if (
            best_score >= EXPR_NEARPASS_BOOST_THRESHOLD
            and family == "group_rank_delta"
            and "nearpass" in lower_name
        ):
            adjustment += 20
        if family in {"group_vol_scaled_delta", "vol_scaled_delta"}:
            adjustment -= 28
            if CHECK_CONCENTRATED_WEIGHT in dominant_names:
                adjustment -= 18
            if "nearpass" in lower_name:
                adjustment -= 8
        if (
            lower_name.startswith("account_rank_backfill_")
            or lower_name == "account_ir_60"
            or lower_name.startswith("account_group_ir_60")
            or lower_name.startswith("account_group_backfill_")
        ):
            adjustment += 22

    return adjustment


def apply_adaptive_priority(
    templates: Sequence[tuple[str, str, int]],
    *,
    field_feedback: dict[str, Any] | None,
    global_failed_check_counts: dict[str, int],
) -> list[tuple[str, str, int]]:
    """
    对候选模板应用自适应优先级调整。

    批量应用自适应优先级调整，根据失败模式优化所有模板的优先级。

    Args:
        templates (Sequence[tuple[str, str, int]]): 模板列表。
        field_feedback (dict[str, Any] | None): 字段反馈数据。
        global_failed_check_counts (dict[str, int]): 全局失败检查计数。

    Returns:
        list[tuple[str, str, int]]: 调整后的模板列表。

    Example:
        >>> templates = [("group_zscore", "expr", 100)]
        >>> adjusted = apply_adaptive_priority(
        ...     templates,
        ...     field_feedback=None,
        ...     global_failed_check_counts={"LOW_SHARPE": 10},
        ... )
        >>> print(adjusted[0][2])
        128  # 加上调整值 28
    """
    return [
        (
            name,
            expression,
            priority
            + adaptive_template_priority_adjustment(
                name,
                expression,
                field_feedback=field_feedback,
                global_failed_check_counts=global_failed_check_counts,
            ),
        )
        for name, expression, priority in templates
    ]


def cap_templates_per_family(
    templates: Sequence[tuple[str, str, int]],
    max_templates_per_family: int,
) -> list[tuple[str, str, int]]:
    """
    限制每个结构家族仅保留前 N 个候选模板。

    通过限制每个家族的模板数量，确保表达式的多样性，
    避免 Alpha 过度集中在某一类型。

    Args:
        templates (Sequence[tuple[str, str, int]]): 已排序的模板列表。
        max_templates_per_family (int): 每个家族的模板数量上限。
            如果为 0 或负数，不限制数量。

    Returns:
        list[tuple[str, str, int]]: 限制后的模板列表。

    Example:
        >>> templates = [
        ...     ("group_zscore1", "expr1", 100),
        ...     ("group_zscore2", "expr2", 90),
        ...     ("group_zscore3", "expr3", 80),
        ...     ("rank_delta1", "expr4", 70),
        ... ]
        >>> capped = cap_templates_per_family(templates, max_templates_per_family=2)
        >>> print(len(capped))
        3  # group_zscore 家族保留 2 个，rank_delta 家族保留 1 个
    """
    if max_templates_per_family <= 0:
        return list(templates)
    kept: list[tuple[str, str, int]] = []
    family_counts: dict[str, int] = {}
    for name, expression, priority in templates:
        family = classify_expression_family(name, expression)
        used = family_counts.get(family, 0)
        if used >= max_templates_per_family:
            continue
        kept.append((name, expression, priority))
        family_counts[family] = used + 1
    return kept


def build_feedback_mutations(
    field_name: str,
    field_feedback: dict[str, Any] | None,
    *,
    dataset_id: str = "",
) -> list[tuple[str, str, int]]:
    """
    基于历史失败检查结果生成额外的表达式变异候选。

    通过分析历史失败模式，生成针对性的表达式变异，
    提高通过检查的概率。

    Args:
        field_name (str): 字段名称。
        field_feedback ( | Nonedict[str, Any]]): 字段反馈数据，
            包含 failed_check_counts、best_expression、best_score 等。
        dataset_id (str): 数据集 ID，用于按数据集过滤黑名单模板。

    Returns:
        list[tuple[str, str, int]]: 变异表达式列表。

    Example:
        >>> mutations = build_feedback_mutations(
        ...     "sales", {"failed_check_counts": {"LOW_TURNOVER": 5}},
        ...     dataset_id="model51"
        ... )
        >>> print(len(mutations))
        8  # 包含基础变异和 LOW_TURNOVER 针对性变异
    """
    # Use failed-check feedback to bias the search toward higher-turnover,
    # less-concentrated, better-neutralized variants.
    bw = get_backfill_window()

    # --- std-normalized delta templates (vol-scaled) ---
    # (delta, std, priority) 窗口配置
    # v5: 去掉短窗口 20/60 (已黑名单，Shapre均值 -0.013)，fundamental6用季度长窗口
    _vol_scaled_windows: list[tuple[int, int, int]] = [
        (63, 126, 192),
        (63, 252, 190),
        (126, 252, 188),
        (252, 504, 186),
    ]
    mutations: list[tuple[str, str, int]] = [
        (
            "iter_group_rank_delta_of_rank_63",
            f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 63), subindustry)",
            184,
        ),
        (
            "iter_group_rank_delta_of_rank_126",
            f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 126), subindustry)",
            182,
        ),
    ]
    # 动态生成 vol-scaled delta 变体
    for delta, std, pri in _vol_scaled_windows:
        name = f"iter_group_vol_scaled_delta_{delta}_{std}"
        expr = f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), {delta}) / ts_std_dev(ts_backfill({field_name}, {bw}), {std}), subindustry)"
        if not _is_blacklisted_template(name, expr, dataset_id=dataset_id):
            mutations.append((name, expr, pri))

    # backfill window variants for vol-scaled
    for bf_window, pri in [(180, 184), (260, 182)]:
        name = f"iter_group_vol_scaled_delta_63_126_bf{bf_window}"
        expr = f"group_rank(ts_delta(ts_backfill({field_name}, {bf_window}), 63) / ts_std_dev(ts_backfill({field_name}, {bf_window}), 126), subindustry)"
        if not _is_blacklisted_template(name, expr, dataset_id=dataset_id):
            mutations.append((name, expr, pri))

    # v5: 去掉 iter_group_mean_spread_over_std_5_20_20 和 iter_rank_mean_spread_over_std_5_20_20
    # (已黑名单，Sharpe全部为负 + CONCENTRATED_WEIGHT)
    # 替换为长窗口季度版本
    mutations.extend(
        [
            (
                "iter_group_mean_spread_over_std_63_240_126",
                f"group_rank((ts_mean(ts_backfill({field_name}, {bw}), 63) - ts_mean(ts_backfill({field_name}, {bw}), {bw})) / ts_std_dev(ts_backfill({field_name}, {bw}), 126), subindustry)",
                178,
            ),
            (
                "iter_rank_mean_spread_over_std_63_240_126",
                f"rank((ts_mean(ts_backfill({field_name}, {bw}), 63) - ts_mean(ts_backfill({field_name}, {bw}), {bw})) / ts_std_dev(ts_backfill({field_name}, {bw}), 126))",
                176,
            ),
        ]
    )

    if not field_feedback:
        return mutations

    failed_counts = field_feedback.get("failed_check_counts", {})
    dominant_names = dominant_failed_check_names(failed_counts, limit=3)
    best_expression = str(field_feedback.get("best_expression", "")).strip()
    best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE))

    if best_score >= EXPR_MUTATION_EXTEND_THRESHOLD:
        mutations.extend(
            [
                (
                    "iter_nearpass_group_rank_delta_of_rank_10",
                    f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 10), subindustry)",
                    194,
                ),
                (
                    "iter_nearpass_group_rank_delta_of_rank_20",
                    f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 20), subindustry)",
                    190,
                ),
                (
                    "iter_nearpass_group_delta_zscore_5_60",
                    f"group_rank(ts_delta(ts_zscore(ts_backfill({field_name}, {bw}), 60), 5), subindustry)",
                    188,
                ),
                (
                    "iter_nearpass_group_delta_zscore_10_60",
                    f"group_rank(ts_delta(ts_zscore(ts_backfill({field_name}, {bw}), 60), 10), subindustry)",
                    186,
                ),
            ]
        )

    best_template_name = str(field_feedback.get("best_template_name", "")).strip() if field_feedback else ""
    if best_template_name in {"account_rank_backfill_504", "account_ir_60"} or best_score >= 0.45:
        mutations.extend(
            [
                (
                    "iter_account_group_backfill_504_subindustry",
                    f"group_rank(ts_backfill({field_name}, {bw}), subindustry)",
                    201,
                ),
                (
                    "iter_account_backfill_zscore_decay_63_subindustry",
                    f"group_rank(ts_decay_linear(ts_zscore(ts_backfill({field_name}, {bw}), 63), 20), subindustry)",
                    199,
                ),
                (
                    "iter_account_ir_60_decay_20",
                    f"rank(ts_decay_linear(ts_mean({field_name}, 60) / ts_std_dev({field_name}, 60), 20))",
                    197,
                ),
                (
                    "iter_account_group_ir_60_subindustry",
                    f"group_rank(ts_mean({field_name}, 60) / ts_std_dev({field_name}, 60), subindustry)",
                    195,
                ),
            ]
        )

    # Near-pass on vol-scaled: generate fine-tuned backfill/delta window variants
    if best_score >= EXPR_NEARPASS_BOOST_THRESHOLD:
        # (delta, std, backfill_window | None, priority) — None = use default bw
        # v5: fundamental6 专用长窗口配置
        _nearpass_vol_scaled_configs: list[tuple[int, int, int | None, int]] = [
            (63, 126, 180, 198),
            (63, 252, 180, 196),
            (126, 252, None, 195),
            (63, 126, None, 194),
            (126, 504, None, 193),
            (252, 504, None, 192),
            (63, 126, 260, 191),
        ]
        for delta, std, bf, pri in _nearpass_vol_scaled_configs:
            bf_val = bf if bf is not None else bw
            bf_suffix = f"_bf{bf_val}" if bf is not None else ""
            name = f"iter_nearpass_vol_scaled_{delta}_{std}{bf_suffix}"
            expr = f"group_rank(ts_delta(ts_backfill({field_name}, {bf_val}), {delta}) / ts_std_dev(ts_backfill({field_name}, {bf_val}), {std}), subindustry)"
            if not _is_blacklisted_template(name, expr, dataset_id=dataset_id):
                mutations.append((name, expr, pri))

    if CHECK_LOW_TURNOVER in dominant_names:
        mutations.extend(
            [
                ("iter_rank_delta_3", f"rank(ts_delta(ts_backfill({field_name}, {bw}), 3))", 186),
                ("iter_rank_delta_5", f"rank(ts_delta(ts_backfill({field_name}, {bw}), 5))", 184),
                (
                    "iter_rank_then_delta_3",
                    f"rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 3))",
                    183,
                ),
            ]
        )

    if (
        CHECK_LOW_SUB_UNIVERSE_SHARPE in dominant_names
        or CHECK_CONCENTRATED_WEIGHT in dominant_names
    ):
        mutations.extend(
            [
                (
                    "iter_group_zscore_20",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, {bw}), 20), subindustry)",
                    185,
                ),
                (
                    "iter_group_zscore_spread_5_20",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, {bw}), 5) - ts_zscore(ts_backfill({field_name}, {bw}), 20), subindustry)",
                    183,
                ),
            ]
        )

    if best_expression:
        mutations.extend(
            [
                ("iter_flip_best", invert_expression(best_expression), 172),
                (
                    "iter_group_flip_best",
                    f"group_rank({invert_expression(best_expression)}, subindustry)",
                    174,
                ),
                (
                    "iter_group_decay_best_5",
                    f"group_rank(ts_decay_linear(ts_backfill({best_expression}, {bw}), 5), subindustry)",
                    170,
                ),
            ]
        )
        if best_score >= FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD:
            for window in (3, 5, 10):
                mutations.extend(
                    [
                        (
                            f"iter_nearpass_delta_best_{window}",
                            f"rank(ts_delta({best_expression}, {window}))",
                            188 - window,
                        ),
                        (
                            f"iter_nearpass_group_delta_best_{window}",
                            f"group_rank(ts_delta({best_expression}, {window}), subindustry)",
                            192 - window,
                        ),
                    ]
                )
            mutations.extend(
                [
                    (
                        f"iter_nearpass_decay_best_{decay}",
                        f"rank(ts_decay_linear({best_expression}, {decay}))",
                        184 - decay,
                    )
                    for decay in (3, 5, 8)
                ]
            )

    return mutations


def invert_expression(expression: str) -> str:
    """
    翻转表达式的符号。

    将正表达式转换为负表达式，或负表达式转换为正表达式。

    Args:
        expression (str): 原始表达式。

    Returns:
        str: 翻转后的表达式。

    Example:
        >>> inverted = invert_expression("rank(close)")
        >>> print(inverted)
        '-rank(close)'
    """
    if expression.startswith("-"):
        return expression[1:]
    return f"-{expression}"


def _build_matrix_templates(
    field_name: str,
    bw: int,
    all_fields: Sequence[dict[str, Any]],
    use_dataset_heuristics: bool,
    *,
    dataset_id: str = "",
) -> tuple[list[tuple[str, str, int]], list[tuple[str, str, int]]]:
    """为 MATRIX 类型字段构建多样化和 legacy 模板候选。

    Args:
        dataset_id: 数据集 ID，用于按数据集过滤黑名单模板。

    Returns:
        (diversified_templates, legacy_templates) 两个列表。
    """
    # delta_over_std 模板的窗口配置: (delta, std, priority)
    # fundamental6 用长窗口（季度更新数据），其他数据集用短窗口
    if use_dataset_heuristics:
        _delta_over_std_windows: list[tuple[int, int, int]] = [
            (21, 63, 148),
            (63, 126, 144),
            (63, 252, 146),
            (126, 252, 142),
            (252, 504, 140),
        ]
    else:
        _delta_over_std_windows: list[tuple[int, int, int]] = [
            (5, 20, 176),
            (15, 40, 172),
            (10, 60, 170),
            (20, 60, 174),
            (25, 90, 168),
            (30, 120, 166),
        ]

    diversified: list[tuple[str, str, int]] = []
    if use_dataset_heuristics:
        # Account feedback from /users/self/alphas shows these families are
        # materially stronger on fundamental6 than long-window delta/std.
        diversified.extend(
            [
                (
                    "account_neutralize_zscore_decay_63_industry",
                    f"ts_decay_linear(group_neutralize(ts_zscore(ts_backfill({field_name}, 240), 63), industry), 20)",
                    214,
                ),
                (
                    "account_group_backfill_504_subindustry",
                    f"group_rank(ts_backfill({field_name}, {bw}), subindustry)",
                    207,
                ),
                (
                    "account_group_zscore_60_subindustry",
                    f"group_rank(ts_zscore({field_name}, 60), subindustry)",
                    210,
                ),
                ("account_ts_rank_60", f"rank(ts_rank({field_name}, 60))", 208),
                ("account_ts_rank_200", f"rank(ts_rank({field_name}, 200))", 204),
                (
                    "account_rank_zscore_240",
                    f"rank(ts_zscore(ts_backfill({field_name}, 240), 240))",
                    202,
                ),
                (
                    "account_backfill_zscore_decay_63_subindustry",
                    f"group_rank(ts_decay_linear(ts_zscore(ts_backfill({field_name}, {bw}), 63), 20), subindustry)",
                    205,
                ),
                (
                    f"account_rank_backfill_{bw}",
                    f"rank(ts_backfill({field_name}, {bw}))",
                    200,
                ),
                (
                    "account_group_decay_63_subindustry",
                    f"group_rank(ts_decay_linear(ts_backfill({field_name}, {bw}), 63), subindustry)",
                    198,
                ),
                (
                    "account_ir_60",
                    f"rank(ts_mean({field_name}, 60) / ts_std_dev({field_name}, 60))",
                    196,
                ),
                (
                    "account_group_ir_60_subindustry",
                    f"group_rank(ts_mean({field_name}, 60) / ts_std_dev({field_name}, 60), subindustry)",
                    204,
                ),
                (
                    "account_ir_60_decay_20",
                    f"rank(ts_decay_linear(ts_mean({field_name}, 60) / ts_std_dev({field_name}, 60), 20))",
                    203,
                ),
            ]
        )

    for delta, std, pri in _delta_over_std_windows:
        diversified.append(
            (
                f"group_delta_over_std_subindustry_{delta}_{std}",
                f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), {delta}) / ts_std_dev(ts_backfill({field_name}, {bw}), {std}), subindustry)",
                pri + DELTA_STD_PRIORITY_BOOST,
            )
        )

    # 非比率单字段多样化模板 — fundamental6 用长窗口
    if use_dataset_heuristics:
        diversified.extend(
            [
                (
                    "group_delta_over_std_industry_63_126",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 63) / ts_std_dev(ts_backfill({field_name}, {bw}), 126), industry)",
                    138 + DELTA_STD_PRIORITY_BOOST,
                ),
                (
                    f"group_short_long_mean_spread_subindustry_63_{bw}",
                    f"group_rank(ts_mean(ts_backfill({field_name}, {bw}), 63) - ts_mean(ts_backfill({field_name}, {bw}), {bw}), subindustry)",
                    164,
                ),
                (
                    "group_zscore_subindustry_63",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, {bw}), 63), subindustry)",
                    161,
                ),
                (
                    f"rank_mean_spread_over_std_63_{bw}_126",
                    f"rank((ts_mean(ts_backfill({field_name}, {bw}), 63) - ts_mean(ts_backfill({field_name}, {bw}), {bw})) / ts_std_dev(ts_backfill({field_name}, {bw}), 126))",
                    158,
                ),
                (
                    f"rank_zscore_spread_63_{bw}",
                    f"rank(ts_zscore(ts_backfill({field_name}, {bw}), 63) - ts_zscore(ts_backfill({field_name}, {bw}), {bw}))",
                    154,
                ),
                (
                    "group_rank_delta_of_rank_63",
                    f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 63), subindustry)",
                    150,
                ),
            ]
        )
    else:
        diversified.extend(
            [
                (
                    "group_delta_over_std_industry_20_60",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 20) / ts_std_dev(ts_backfill({field_name}, {bw}), 60), industry)",
                    166 + DELTA_STD_PRIORITY_BOOST,
                ),
                (
                    f"group_short_long_mean_spread_subindustry_20_{bw}",
                    f"group_rank(ts_mean(ts_backfill({field_name}, {bw}), 20) - ts_mean(ts_backfill({field_name}, {bw}), {bw}), subindustry)",
                    164,
                ),
                (
                    "group_zscore_subindustry_60",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, {bw}), 60), subindustry)",
                    161,
                ),
                (
                    f"rank_mean_spread_over_std_20_{bw}_60",
                    f"rank((ts_mean(ts_backfill({field_name}, {bw}), 20) - ts_mean(ts_backfill({field_name}, {bw}), {bw})) / ts_std_dev(ts_backfill({field_name}, {bw}), 60))",
                    158,
                ),
                (
                    f"rank_zscore_spread_20_{bw}",
                    f"rank(ts_zscore(ts_backfill({field_name}, {bw}), 20) - ts_zscore(ts_backfill({field_name}, {bw}), {bw}))",
                    154,
                ),
                (
                    "group_rank_delta_of_rank_20",
                    f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 20), subindustry)",
                    150,
                ),
            ]
        )

    legacy: list[tuple[str, str, int]] = [
        ("raw_field", field_name, 145),
        ("group_rank_subindustry", f"group_rank({field_name}, subindustry)", 143),
        ("group_rank_industry", f"group_rank({field_name}, industry)", 141),
        ("rank_raw_field", f"rank({field_name})", 118),
    ]
    if use_dataset_heuristics and field_name in POSITIVE_RAW_FIELDS:
        legacy.append(("neg_raw_field", f"-{field_name}", 132))
    elif use_dataset_heuristics and field_name in NEGATIVE_RAW_FIELDS:
        legacy.append(("neg_raw_field", f"-{field_name}", 144))
    elif use_dataset_heuristics:
        legacy.append(("neg_raw_field", f"-{field_name}", 128))

    # 比率配对模板
    fields_by_name = {choose_field_name(item): item for item in all_fields}
    partner_names = discover_partner_fields(
        field_name,
        all_fields,
        limit=6 if use_dataset_heuristics else 4,
        use_curated_heuristics=use_dataset_heuristics,
    )

    # 比率配对模板窗口配置: (delta, std, priority)
    # fundamental6 用长窗口避免 quarterly 数据下短 delta 全为 0/NaN
    if use_dataset_heuristics:
        _ratio_delta_rank_windows: list[tuple[int, None, int]] = [
            (63, None, 186),
            (126, None, 180),
            (252, None, 172),
        ]
        _ratio_delta_over_std_windows: list[tuple[int, int, int]] = [
            (21, 63, 176),
            (63, 126, 172),
            (63, 252, 174),
            (126, 252, 168),
        ]
    else:
        _ratio_delta_rank_windows: list[tuple[int, None, int]] = [
            (3, None, 188),
            (5, None, 184),
            (10, None, 176),
        ]
        _ratio_delta_over_std_windows: list[tuple[int, int, int]] = [
            (5, 20, 180),
            (15, 40, 176),
            (10, 60, 174),
            (20, 60, 178),
            (25, 90, 172),
            (30, 120, 170),
        ]

    for partner in partner_names:
        if partner not in fields_by_name and partner not in ALLOWED_EXTERNAL_RATIO_PARTNERS:
            continue
        ratio_expr = f"{field_name}/{partner}"
        ratio_label = f"{field_name}_over_{partner}"
        ratio_priority_boost = 0
        if use_dataset_heuristics and (field_name, partner) in FUNDAMENTAL6_HIGH_CONVICTION_RATIO_PAIRS:
            ratio_priority_boost = 18

        # Delta rank 变体
        for delta, _, pri in _ratio_delta_rank_windows:
            name = f"group_ratio_delta_rank_{delta}_{ratio_label}"
            expr = f"group_rank(ts_delta(rank(ts_backfill({ratio_expr}, {bw})), {delta}), subindustry)"
            if not _is_blacklisted_template(name, expr, dataset_id=dataset_id):
                diversified.append((name, expr, pri + DELTA_STD_PRIORITY_BOOST + ratio_priority_boost))

        # Delta over std 变体
        for delta, std, pri in _ratio_delta_over_std_windows:
            diversified.append(
                (
                    f"group_ratio_delta_over_std_{delta}_{std}_{ratio_label}",
                    f"group_rank(ts_delta(ts_backfill({ratio_expr}, {bw}), {delta}) / ts_std_dev(ts_backfill({ratio_expr}, {bw}), {std}), subindustry)",
                    pri + DELTA_STD_PRIORITY_BOOST + ratio_priority_boost,
                )
            )

        # fundamental6 用长窗口, 其他数据集保留短窗口
        if use_dataset_heuristics:
            diversified.extend(
                [
                    (
                        f"group_ratio_zscore_{ratio_label}",
                        f"group_rank(ts_zscore(ts_backfill({ratio_expr}, {bw}), 63), subindustry)",
                        160 + ratio_priority_boost,
                    ),
                    (
                        f"ratio_mean_spread_over_std_{ratio_label}",
                        f"rank((ts_mean(ts_backfill({ratio_expr}, {bw}), 63) - ts_mean(ts_backfill({ratio_expr}, {bw}), {bw})) / ts_std_dev(ts_backfill({ratio_expr}, {bw}), 126))",
                        156 + ratio_priority_boost,
                    ),
                    (
                        f"ratio_zscore_spread_{ratio_label}",
                        f"rank(ts_zscore(ts_backfill({ratio_expr}, {bw}), 63) - ts_zscore(ts_backfill({ratio_expr}, {bw}), {bw}))",
                        152 + ratio_priority_boost,
                    ),
                ]
            )
        else:
            diversified.extend(
                [
                    (
                        f"group_ratio_zscore_{ratio_label}",
                        f"group_rank(ts_zscore(ts_backfill({ratio_expr}, {bw}), 60), subindustry)",
                        160,
                    ),
                    (
                        f"ratio_mean_spread_over_std_{ratio_label}",
                        f"rank((ts_mean(ts_backfill({ratio_expr}, {bw}), 20) - ts_mean(ts_backfill({ratio_expr}, {bw}), {bw})) / ts_std_dev(ts_backfill({ratio_expr}, {bw}), 60))",
                        156,
                    ),
                    (
                        f"ratio_zscore_spread_{ratio_label}",
                        f"rank(ts_zscore(ts_backfill({ratio_expr}, {bw}), 20) - ts_zscore(ts_backfill({ratio_expr}, {bw}), {bw}))",
                        152,
                    ),
                ]
            )

        legacy.extend(
            [
                (f"raw_ratio_{ratio_label}", ratio_expr, 154 + ratio_priority_boost),
                (
                    f"group_rank_ratio_{ratio_label}",
                    f"group_rank({ratio_expr}, subindustry)",
                    152 + ratio_priority_boost,
                ),
                (f"ratio_{ratio_label}", f"rank({ratio_expr})", 148 + ratio_priority_boost),
                (
                    f"decay_ratio_{ratio_label}",
                    f"rank(ts_decay_linear(ts_backfill({ratio_expr}, {bw}), 63))",
                    126 + ratio_priority_boost,
                ),
            ]
        )

    if use_dataset_heuristics:
        diversified = [
            (
                name,
                expr,
                pri + FUNDAMENTAL6_ACCOUNT_TEMPLATE_BOOST if name.startswith("account_") else pri,
            )
            for name, expr, pri in diversified
        ]

    return diversified, legacy


def build_expression_candidates(
    field: dict[str, Any],
    template_library: TemplateLibrary,
    max_templates_per_field: int,
    max_templates_per_family: int,
    legacy_similarity_penalty: int,
    all_fields: Sequence[dict[str, Any]] | None = None,
    field_feedback: dict[str, Any] | None = None,
    global_failed_check_counts: dict[str, int] | None = None,
    use_dataset_heuristics: bool = True,
    *,
    dataset_id: str = "",
) -> list[tuple[str, str, int]]:
    """
    为单个字段构建、变异、多样化并排序表达式候选。

    这是表达式构建的核心函数，整合了模板选择、变异生成、
    优先级调整和数量限制等多个步骤。

    Args:
        field (dict[str, Any]): 字段元数据。
        template_library (TemplateLibrary): 模板库字典。
        max_templates_per_field (int): 每个字段的模板数量上限。
        max_templates_per_family (int): 每个家族的模板数量上限。
        legacy_similarity_penalty (int): legacy 家族的相似度惩罚。
        all_fields (Sequence[dict[str, Any]] | None): 所有可用字段列表。
        field_feedback (dict[str, Any] | None): 字段反馈数据。
        global_failed_check_counts (dict[str, int] | None): 全局失败检查计数。
        use_dataset_heuristics (bool): 是否使用数据集启发式规则。
        dataset_id (str): 数据集 ID，用于按数据集过滤黑名单模板。

    Returns:
        list[tuple[str, str, int]]: 最终的表达式候选列表，
            每个元素为 (name, expression, priority) 元组。

    处理步骤：
        1. 从模板库选择基础模板
        2. 添加反馈驱动的变异
        3. 对于 MATRIX 类型字段，添加多样化的模板
        4. 添加 legacy 模板（原始字段、分组排名等）
        5. 为比率型模板发现配对字段
        6. 应用相似度惩罚
        7. 应用自适应优先级调整
        8. 按优先级排序
        9. 限制每个家族的模板数量
        10. 限制总数

    Example:
        >>> candidates = build_expression_candidates(
        ...     field={"id": "sales", "type": "MATRIX"},
        ...     template_library=load_template_library(""),
        ...     max_templates_per_field=50,
        ...     max_templates_per_family=10,
        ...     legacy_similarity_penalty=30,
        ...     all_fields=[{"id": "cap", "type": "MATRIX"}],
        ...     use_dataset_heuristics=True,
        ... )
        >>> print(len(candidates))
        50  # 限制后最多 50 个候选
    """
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    all_fields = all_fields or []
    global_failed_check_counts = global_failed_check_counts or {}
    bw = get_backfill_window()

    # Template selection is now driven by an externalizable library so we can
    # expand or shrink search coverage between runs without changing code.
    raw_templates = template_library.get(field_type) or template_library.get("default", [])
    templates = [
        (
            str(item["name"]),
            str(item["expression"]).format(field=field_name),
            int(item.get("priority", 0))
            + (
                _fundamental6_template_priority_adjustment(str(item["name"]))
                if dataset_id == "fundamental6" and use_dataset_heuristics
                else 0
            ),
        )
        for item in raw_templates
        if isinstance(item, dict)
        and "name" in item
        and "expression" in item
        and not (
            dataset_id == "fundamental6"
            and str(item["name"]) in FUNDAMENTAL6_DISABLED_TEMPLATES
        )
        and not _is_blacklisted_template(str(item["name"]), str(item["expression"]), dataset_id=dataset_id)
    ]
    templates.extend(build_feedback_mutations(field_name, field_feedback, dataset_id=dataset_id))

    if field_type == "MATRIX":
        diversified, legacy = _build_matrix_templates(
            field_name,
            bw,
            all_fields,
            use_dataset_heuristics,
            dataset_id=dataset_id,
        )
        templates.extend(diversified)
        templates.extend(legacy)

    templates = apply_similarity_penalty(templates, legacy_similarity_penalty)
    templates = apply_adaptive_priority(
        templates,
        field_feedback=field_feedback,
        global_failed_check_counts=global_failed_check_counts,
    )
    templates = sort_templates_by_priority(templates)
    return limit_templates(
        cap_templates_per_family(templates, max_templates_per_family),
        max_templates_per_field,
    )
