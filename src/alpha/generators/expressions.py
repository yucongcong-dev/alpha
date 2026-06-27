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

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..config import (
    BACKFILL_WINDOW,
    DELTA_STD_PRIORITY_BOOST,
    EXPR_ITER_BOOST_THRESHOLD,
    EXPR_MUTATION_EXTEND_THRESHOLD,
    EXPR_NEARPASS_BOOST_THRESHOLD,
    EXPR_RATIO_PENALTY_THRESHOLD,
    NEGATIVE_RAW_FIELDS,
    POSITIVE_RAW_FIELDS,
    RATIO_KEYWORDS,
    RATIO_PARTNER_CANDIDATES,
    STATS_DEFAULT_SCORE,
)
from ..models.base import TemplateLibrary
from ..utils.helpers import choose_field_name, choose_field_type


def tokenize_field_name(field_name: str) -> List[str]:
    """
    将字段名拆分为小写字母数字 token。

    通过正则表达式将字段名分解为独立的字母数字单元，
    用于字段名称的相似性比较和配对打分。

    Args:
        field_name (str): 要拆分的字段名称。

    Returns:
        List[str]: 拆分后的小写 token 列表，去除空 token。

    Example:
        >>> tokens = tokenize_field_name("sales_per_share")
        >>> print(tokens)
        ['sales', 'per', 'share']

        >>> tokens = tokenize_field_name("EBITDA-2024")
        >>> print(tokens)
        ['ebitda', '2024']
    """
    return [token for token in re.split(r"[^a-z0-9]+", field_name.lower()) if token]


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
    if partner_name in {"assets", "equity", "debt", "liabilities", "cash", "enterprise_value", "cap"}:
        score += 15
    if partner_name in {"fnd6_mkvalt", "fnd6_mkvaltq", "liabilities_curr"}:
        score += 25
    return score


def discover_partner_fields(
    field_name: str,
    all_fields: Sequence[Dict[str, Any]],
    *,
    limit: int = 4,
    use_curated_heuristics: bool = True,
) -> List[str]:
    """
    为比值类模板扩展寻找可能合适的配对字段。

    根据启发式规则和推荐配置，从所有字段中筛选出最合适的
    配对字段，用于构建比率型 Alpha 表达式。

    Args:
        field_name (str): 主字段名称。
        all_fields (Sequence[Dict[str, Any]]): 所有可用字段的列表。
        limit (int): 返回的配对字段数量上限。默认为 4。
        use_curated_heuristics (bool): 是否使用精选启发式规则。默认为 True。

    Returns:
        List[str]: 配对字段名称列表，按得分排序。

    Example:
        >>> fields = [
        ...     {"name": "cap", "type": "MATRIX"},
        ...     {"name": "assets", "type": "MATRIX"},
        ...     {"name": "sales", "type": "MATRIX"}
        ... ]
        >>> partners = discover_partner_fields("debt", fields, limit=2)
        >>> print(partners)
        ['cap', 'assets']
    """
    if not use_curated_heuristics:
        return []

    candidates: List[Tuple[int, str]] = []
    available_by_name = {
        choose_field_name(item): item
        for item in all_fields
        if choose_field_type(item) == "MATRIX"
    }

    # Seed the candidate list with curated pairings first so extremely
    # important ratios like debt/cap are never crowded out by weaker matches.
    for partner_name in RATIO_PARTNER_CANDIDATES.get(field_name, ()):
        if partner_name == field_name or partner_name not in available_by_name:
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
    result: List[str] = []
    for _, partner_name in candidates:
        if partner_name in seen:
            continue
        seen.add(partner_name)
        result.append(partner_name)
        if len(result) >= limit:
            break
    return result


def sort_templates_by_priority(
    templates: Sequence[Tuple[str, str, int]]
) -> List[Tuple[str, str, int]]:
    """
    按有效优先级从高到低排序候选模板。

    优先级越高（数值越大）的模板排序越靠前，优先被测试。
    这样可以让最可能成功的模板先运行，提高整体效率。

    Args:
        templates (Sequence[Tuple[str, str, int]]): 模板列表，
            每个元素为 (name, expression, priority) 元组。

    Returns:
        List[Tuple[str, str, int]]: 排序后的模板列表。

    Example:
        >>> templates = [
        ...     ("low", "expr1", 10),
        ...     ("high", "expr2", 100),
        ...     ("mid", "expr3", 50)
        ... ]
        >>> sorted_templates = sort_templates_by_priority(templates)
        >>> print(sorted_templates[0][0])
        'high'
    """
    # Higher-priority templates run first so likely winners are tested earlier.
    return sorted(templates, key=lambda item: (-item[2], item[0], item[1]))


def limit_templates(
    templates: List[Tuple[str, str, int]],
    max_templates_per_field: int,
) -> List[Tuple[str, str, int]]:
    """
    在排序与多样化之后应用字段级模板数量上限。

    通过硬性限制每个字段最多测试的模板数量，控制测试规模
    和资源消耗。

    Args:
        templates (List[Tuple[str, str, int]]): 已排序的模板列表。
        max_templates_per_field (int): 每个字段的模板数量上限。
            如果为 0 或负数，不限制数量。

    Returns:
        List[Tuple[str, str, int]]: 限制后的模板列表。

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
        >>> family = classify_expression_family("group_rank_delta", "group_rank(ts_delta(rank(close), 20), subindustry)")
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
    return prefix or "other"


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

        >>> is_legacy = is_legacy_family("group_zscore", "group_rank(ts_zscore(close, 60), subindustry)")
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


def apply_similarity_penalty(
    templates: Sequence[Tuple[str, str, int]],
    legacy_similarity_penalty: int,
) -> List[Tuple[str, str, int]]:
    """
    对 legacy 形态模板施加相似度惩罚，让多样化候选优先运行。

    通过降低 legacy 家族模板的优先级，鼓励多样化的表达式形式，
    避免 Alpha 过度集中在传统模式上。

    Args:
        templates (Sequence[Tuple[str, str, int]]): 模板列表。
        legacy_similarity_penalty (int): legacy 家族的惩罚分数。

    Returns:
        List[Tuple[str, str, int]]: 应用惩罚后的模板列表。

    惩罚规则：
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
    penalized: List[Tuple[str, str, int]] = []
    for name, expression, priority in templates:
        family = classify_expression_family(name, expression)
        penalty = 0
        if family == "legacy_level":
            penalty = legacy_similarity_penalty
        elif family == "legacy_group_level":
            penalty = max(legacy_similarity_penalty - 6, 0)
        elif family == "legacy_ratio":
            penalty = max(legacy_similarity_penalty - 10, 0)
        elif family == "legacy_neg_ratio":
            penalty = max(legacy_similarity_penalty - 8, 0)
        elif family == "group_ratio_level":
            penalty = max(legacy_similarity_penalty - 14, 0)
        penalized.append((name, expression, priority - penalty))
    return penalized


def dominant_failed_check_names(counts: Dict[str, int], limit: int = 4) -> set:
    """
    返回失败检查计数最高的若干名称。

    从失败检查计数字典中提取出现次数最多的失败类型，
    用于指导模板优先级的自适应调整。

    Args:
        counts (Dict[str, int]): 失败检查计数字典。
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


def merge_failed_check_counts(*count_maps: Dict[str, Any]) -> Dict[str, int]:
    """
    合并多个失败检查计数字典。

    将多个来源的失败检查计数合并为一个字典，
    用于综合分析失败模式。

    Args:
        *count_maps: 可变数量的失败检查计数字典。

    Returns:
        Dict[str, int]: 合并后的计数字典。

    Example:
        >>> counts1 = {"LOW_SHARPE": 10}
        >>> counts2 = {"LOW_TURNOVER": 5, "LOW_SHARPE": 3}
        >>> merged = merge_failed_check_counts(counts1, counts2)
        >>> print(merged["LOW_SHARPE"])
        13
    """
    merged: Dict[str, int] = {}
    for count_map in count_maps:
        for name, count in count_map.items():
            if not isinstance(count, int):
                continue
            merged[str(name)] = merged.get(str(name), 0) + count
    return merged


def adaptive_template_priority_adjustment(
    template_name: str,
    expression: str,
    *,
    field_feedback: Optional[Dict[str, Any]],
    global_failed_check_counts: Dict[str, int],
) -> int:
    """
    根据字段与全局失败分布动态调整模板优先级。

    通过分析历史失败检查模式，智能调整模板的优先级，
    让更可能通过检查的表达式形式优先测试。

    Args:
        template_name (str): 模板名称。
        expression (str): 表达式字符串。
        field_feedback (Optional[Dict[str, Any]]): 字段反馈数据，
            包含 failed_check_counts 和 best_score 等。
        global_failed_check_counts (Dict[str, int]): 全局失败检查计数。

    Returns:
        int: 优先级调整值（可正可负）。

    调整规则：
        - LOW_SHARPE/LOW_SUB_UNIVERSE_SHARPE 主导时：
            - 分组型家族加分
            - zscore/spread 型加分
            - legacy 型减分
        - LOW_FITNESS 主导时：
            - delta/spread 型加分
            - legacy 型减分
        - LOW_TURNOVER 主导时：
            - delta 型加分
            - legacy 型减分
        - HIGH_TURNOVER 主导时：
            - spread/decay 型加分
            - delta 型减分
        - CONCENTRATED_WEIGHT 主导时：
            - group 型加分
            - ratio 型减分
        - 历史最佳分数高时：
            - iter_nearpass 型加分

    Example:
        >>> adjustment = adaptive_template_priority_adjustment(
        ...     "group_zscore",
        ...     "group_rank(ts_zscore(close, 60), subindustry)",
        ...     field_feedback={"failed_check_counts": {"LOW_SHARPE": 5}},
        ...     global_failed_check_counts={"LOW_SHARPE": 10}
        ... )
        >>> print(adjustment)
        28  # group_zscore 家族在 LOW_SHARPE 主导时加分
    """
    field_counts = field_feedback.get("failed_check_counts", {}) if field_feedback else {}
    dominant_names = dominant_failed_check_names(merge_failed_check_counts(global_failed_check_counts, field_counts))
    family = classify_expression_family(template_name, expression)
    lower_name = template_name.lower()
    adjustment = 0

    if "LOW_SHARPE" in dominant_names or "LOW_SUB_UNIVERSE_SHARPE" in dominant_names:
        if family.startswith("group_") or family in {"group_rank_delta", "group_zscore", "group_mean_spread", "group_vol_scaled_delta"}:
            adjustment += 28
        if family in {"zscore_time", "rank_spread", "mean_spread", "vol_scaled_delta", "rank_delta", "decayed_delta"}:
            adjustment += 18
        if family in {"legacy_level", "legacy_group_level", "legacy_ratio", "legacy_neg_ratio", "group_ratio_level"}:
            adjustment -= 35

    if "LOW_FITNESS" in dominant_names:
        if "delta" in family or "spread" in family or lower_name.startswith("iter_"):
            adjustment += 22
        if family in {"legacy_level", "legacy_group_level"}:
            adjustment -= 25
        # vol-scaled delta consistently produces better fitness on fundamental6
        if family in {"group_vol_scaled_delta", "vol_scaled_delta"}:
            adjustment += 15

    if "LOW_TURNOVER" in dominant_names:
        if "delta" in family or lower_name.startswith(("iter_rank_delta", "iter_rank_then_delta")):
            adjustment += 30
        if family in {"legacy_level", "legacy_group_level", "mean_spread"}:
            adjustment -= 18

    if "HIGH_TURNOVER" in dominant_names:
        if family in {"mean_spread", "decayed_delta", "decayed_ratio"}:
            adjustment += 20
        if "delta" in family:
            adjustment -= 20

    if "CONCENTRATED_WEIGHT" in dominant_names:
        if family.startswith("group_"):
            adjustment += 24
        if family in {"legacy_ratio", "legacy_neg_ratio", "group_ratio_level"}:
            adjustment -= 30

    # Results show rank_zscore_spread is fundamentally broken on fundamental6:
    # negative Sharpe, extreme turnover (0.86-0.99), concentrated weight (0.5).
    # Heavily penalize spread-type templates when both HIGH_TURNOVER + CONCENTRATED_WEIGHT fire.
    if "HIGH_TURNOVER" in dominant_names and "CONCENTRATED_WEIGHT" in dominant_names:
        if family in {"rank_spread", "mean_spread"}:
            adjustment -= 50
        if "zscore" in lower_name and "spread" in lower_name:
            adjustment -= 45

    # Ratio-based templates consistently underperform on standalone fields.
    # When the field already has near-pass feedback on non-ratio templates,
    # skip ratio exploration entirely.
    if field_feedback:
        best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE))
        if best_score >= EXPR_NEARPASS_BOOST_THRESHOLD and lower_name.startswith("iter_nearpass_"):
            adjustment += 40
        elif best_score >= EXPR_ITER_BOOST_THRESHOLD and lower_name.startswith("iter_"):
            adjustment += 18
        # Ratio templates waste queue when field already has decent non-ratio signal.
        if best_score >= EXPR_RATIO_PENALTY_THRESHOLD and family in {"legacy_ratio", "legacy_neg_ratio", "group_ratio_level"}:
            adjustment -= 40
        # group_rank_delta nearpass deserves extra boost — best Sharpe on fundamental6
        if best_score >= EXPR_NEARPASS_BOOST_THRESHOLD and family == "group_rank_delta" and "nearpass" in lower_name:
            adjustment += 20
        # vol-scaled delta nearpass deserves the highest boost — best overall on fundamental6
        if family in {"group_vol_scaled_delta", "vol_scaled_delta"}:
            adjustment += 25
            if "nearpass" in lower_name:
                adjustment += 15

    return adjustment


def apply_adaptive_priority(
    templates: Sequence[Tuple[str, str, int]],
    *,
    field_feedback: Optional[Dict[str, Any]],
    global_failed_check_counts: Dict[str, int],
) -> List[Tuple[str, str, int]]:
    """
    对候选模板应用自适应优先级调整。

    批量应用自适应优先级调整，根据失败模式优化所有模板的优先级。

    Args:
        templates (Sequence[Tuple[str, str, int]]): 模板列表。
        field_feedback (Optional[Dict[str, Any]]): 字段反馈数据。
        global_failed_check_counts (Dict[str, int]): 全局失败检查计数。

    Returns:
        List[Tuple[str, str, int]]: 调整后的模板列表。

    Example:
        >>> templates = [("group_zscore", "expr", 100)]
        >>> adjusted = apply_adaptive_priority(
        ...     templates,
        ...     field_feedback=None,
        ...     global_failed_check_counts={"LOW_SHARPE": 10}
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
    templates: Sequence[Tuple[str, str, int]],
    max_templates_per_family: int,
) -> List[Tuple[str, str, int]]:
    """
    限制每个结构家族仅保留前 N 个候选模板。

    通过限制每个家族的模板数量，确保表达式的多样性，
    避免 Alpha 过度集中在某一类型。

    Args:
        templates (Sequence[Tuple[str, str, int]]): 已排序的模板列表。
        max_templates_per_family (int): 每个家族的模板数量上限。
            如果为 0 或负数，不限制数量。

    Returns:
        List[Tuple[str, str, int]]: 限制后的模板列表。

    Example:
        >>> templates = [
        ...     ("group_zscore1", "expr1", 100),
        ...     ("group_zscore2", "expr2", 90),
        ...     ("group_zscore3", "expr3", 80),
        ...     ("rank_delta1", "expr4", 70)
        ... ]
        >>> capped = cap_templates_per_family(templates, max_templates_per_family=2)
        >>> print(len(capped))
        3  # group_zscore 家族保留 2 个，rank_delta 家族保留 1 个
    """
    if max_templates_per_family <= 0:
        return list(templates)
    kept: List[Tuple[str, str, int]] = []
    family_counts: Dict[str, int] = {}
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
    field_feedback: Optional[Dict[str, Any]],
) -> List[Tuple[str, str, int]]:
    """
    基于历史失败检查结果生成额外的表达式变异候选。

    通过分析历史失败模式，生成针对性的表达式变异，
    提高通过检查的概率。

    Args:
        field_name (str): 字段名称。
        field_feedback (Optional[Dict[str, Any]]): 字段反馈数据，
            包含 failed_check_counts、best_expression、best_score 等。

    Returns:
        List[Tuple[str, str, int]]: 变异表达式列表。

    Example:
        >>> mutations = build_feedback_mutations(
        ...     "sales",
        ...     {"failed_check_counts": {"LOW_TURNOVER": 5}}
        ... )
        >>> print(len(mutations))
        8  # 包含基础变异和 LOW_TURNOVER 针对性变异
    """
    # Use failed-check feedback to bias the search toward higher-turnover,
    # less-concentrated, better-neutralized variants.
    bw = BACKFILL_WINDOW
    mutations: List[Tuple[str, str, int]] = [
        (
            "iter_group_rank_delta_of_rank_3",
            f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 3), subindustry)",
            182,
        ),
        (
            "iter_group_rank_delta_of_rank_5",
            f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 5), subindustry)",
            180,
        ),
        # --- std-normalized delta templates (vol-scaled) ---
        # These consistently produce higher Sharpe on fundamental6
        (
            "iter_group_vol_scaled_delta_20_60",
            f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 20) / ts_std_dev(ts_backfill({field_name}, {bw}), 60), subindustry)",
            192,
        ),
        (
            "iter_group_vol_scaled_delta_15_40",
            f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 15) / ts_std_dev(ts_backfill({field_name}, {bw}), 40), subindustry)",
            190,
        ),
        (
            "iter_group_vol_scaled_delta_10_60",
            f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 10) / ts_std_dev(ts_backfill({field_name}, {bw}), 60), subindustry)",
            188,
        ),
        (
            "iter_group_vol_scaled_delta_25_90",
            f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 25) / ts_std_dev(ts_backfill({field_name}, {bw}), 90), subindustry)",
            186,
        ),
        # --- backfill window variants for vol-scaled ---
        (
            "iter_group_vol_scaled_delta_20_60_bf180",
            f"group_rank(ts_delta(ts_backfill({field_name}, 180), 20) / ts_std_dev(ts_backfill({field_name}, 180), 60), subindustry)",
            184,
        ),
        (
            "iter_group_vol_scaled_delta_20_60_bf260",
            f"group_rank(ts_delta(ts_backfill({field_name}, 260), 20) / ts_std_dev(ts_backfill({field_name}, 260), 60), subindustry)",
            182,
        ),
        (
            "iter_group_mean_spread_over_std_5_20_20",
            f"group_rank((ts_mean(ts_backfill({field_name}, {bw}), 5) - ts_mean(ts_backfill({field_name}, {bw}), 20)) / ts_std_dev(ts_backfill({field_name}, {bw}), 20), subindustry)",
            178,
        ),
        (
            "iter_rank_mean_spread_over_std_5_20_20",
            f"rank((ts_mean(ts_backfill({field_name}, {bw}), 5) - ts_mean(ts_backfill({field_name}, {bw}), 20)) / ts_std_dev(ts_backfill({field_name}, {bw}), 20))",
            176,
        ),
    ]

    if not field_feedback:
        return mutations

    failed_counts = field_feedback.get("failed_check_counts", {})
    dominant_names = {
        name
        for name, _ in sorted(failed_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    }
    _best_expression = str(field_feedback.get("best_expression", "")).strip()
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

    # Near-pass on vol-scaled: generate fine-tuned backfill/delta window variants
    if best_score >= EXPR_NEARPASS_BOOST_THRESHOLD:
        mutations.extend(
            [
                (
                    "iter_nearpass_vol_scaled_15_40_bf180",
                    f"group_rank(ts_delta(ts_backfill({field_name}, 180), 15) / ts_std_dev(ts_backfill({field_name}, 180), 40), subindustry)",
                    198,
                ),
                (
                    "iter_nearpass_vol_scaled_20_60_bf180",
                    f"group_rank(ts_delta(ts_backfill({field_name}, 180), 20) / ts_std_dev(ts_backfill({field_name}, 180), 60), subindustry)",
                    196,
                ),
                (
                    "iter_nearpass_vol_scaled_10_40",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 10) / ts_std_dev(ts_backfill({field_name}, {bw}), 40), subindustry)",
                    195,
                ),
                (
                    "iter_nearpass_vol_scaled_15_60",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 15) / ts_std_dev(ts_backfill({field_name}, {bw}), 60), subindustry)",
                    194,
                ),
                (
                    "iter_nearpass_vol_scaled_25_60",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 25) / ts_std_dev(ts_backfill({field_name}, {bw}), 60), subindustry)",
                    193,
                ),
                (
                    "iter_nearpass_vol_scaled_20_90",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 20) / ts_std_dev(ts_backfill({field_name}, {bw}), 90), subindustry)",
                    192,
                ),
                (
                    "iter_nearpass_vol_scaled_20_60_bf260",
                    f"group_rank(ts_delta(ts_backfill({field_name}, 260), 20) / ts_std_dev(ts_backfill({field_name}, 260), 60), subindustry)",
                    191,
                ),
            ]
        )

    if "LOW_TURNOVER" in dominant_names:
        mutations.extend(
            [
                ("iter_rank_delta_3", f"rank(ts_delta(ts_backfill({field_name}, {bw}), 3))", 186),
                ("iter_rank_delta_5", f"rank(ts_delta(ts_backfill({field_name}, {bw}), 5))", 184),
                ("iter_rank_then_delta_3", f"rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 3))", 183),
            ]
        )

    if "LOW_SUB_UNIVERSE_SHARPE" in dominant_names or "CONCENTRATED_WEIGHT" in dominant_names:
        mutations.extend(
            [
                ("iter_group_zscore_20", f"group_rank(ts_zscore(ts_backfill({field_name}, {bw}), 20), subindustry)", 185),
                (
                    "iter_group_zscore_spread_5_20",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, {bw}), 5) - ts_zscore(ts_backfill({field_name}, {bw}), 20), subindustry)",
                    183,
                ),
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


def build_expression_candidates(
    field: Dict[str, Any],
    template_library: TemplateLibrary,
    max_templates_per_field: int,
    max_templates_per_family: int,
    legacy_similarity_penalty: int,
    all_fields: Optional[Sequence[Dict[str, Any]]] = None,
    field_feedback: Optional[Dict[str, Any]] = None,
    global_failed_check_counts: Optional[Dict[str, int]] = None,
    use_dataset_heuristics: bool = True,
) -> List[Tuple[str, str, int]]:
    """
    为单个字段构建、变异、多样化并排序表达式候选。

    这是表达式构建的核心函数，整合了模板选择、变异生成、
    优先级调整和数量限制等多个步骤。

    Args:
        field (Dict[str, Any]): 字段元数据。
        template_library (TemplateLibrary): 模板库字典。
        max_templates_per_field (int): 每个字段的模板数量上限。
        max_templates_per_family (int): 每个家族的模板数量上限。
        legacy_similarity_penalty (int): legacy 家族的相似度惩罚。
        all_fields (Optional[Sequence[Dict[str, Any]]]): 所有可用字段列表。
        field_feedback (Optional[Dict[str, Any]]): 字段反馈数据。
        global_failed_check_counts (Optional[Dict[str, int]]): 全局失败检查计数。
        use_dataset_heuristics (bool): 是否使用数据集启发式规则。

    Returns:
        List[Tuple[str, str, int]]: 最终的表达式候选列表，
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
        ...     template_library=default_template_library(),
        ...     max_templates_per_field=50,
        ...     max_templates_per_family=10,
        ...     legacy_similarity_penalty=30,
        ...     all_fields=[{"id": "cap", "type": "MATRIX"}],
        ...     use_dataset_heuristics=True
        ... )
        >>> print(len(candidates))
        50  # 限制后最多 50 个候选
    """
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    all_fields = all_fields or []
    global_failed_check_counts = global_failed_check_counts or {}
    bw = BACKFILL_WINDOW

    # Template selection is now driven by an externalizable library so we can
    # expand or shrink search coverage between runs without changing code.
    raw_templates = template_library.get(field_type) or template_library.get("default", [])
    templates = [
        (
            str(item["name"]),
            str(item["expression"]).format(field=field_name),
            int(item.get("priority", 0)),
        )
        for item in raw_templates
        if isinstance(item, dict) and "name" in item and "expression" in item
    ]
    templates.extend(build_feedback_mutations(field_name, field_feedback))

    # Favor structural diversity over copying already-submitted shapes:
    # - de-emphasize raw level / simple group-rank / plain ratio expressions
    # - prioritize time-normalized, vol-scaled, and short-vs-long horizon spreads
    diversified_templates: List[Tuple[str, str, int]] = []
    legacy_templates: List[Tuple[str, str, int]] = []
    if field_type == "MATRIX":
        diversified_templates.extend(
            [
                (
                    "group_delta_over_std_subindustry_20_60",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 20) / ts_std_dev(ts_backfill({field_name}, {bw}), 60), subindustry)",
                    174 + DELTA_STD_PRIORITY_BOOST,
                ),
                (
                    "group_delta_over_std_subindustry_15_40",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 15) / ts_std_dev(ts_backfill({field_name}, {bw}), 40), subindustry)",
                    172 + DELTA_STD_PRIORITY_BOOST,
                ),
                (
                    "group_delta_over_std_subindustry_10_60",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 10) / ts_std_dev(ts_backfill({field_name}, {bw}), 60), subindustry)",
                    170 + DELTA_STD_PRIORITY_BOOST,
                ),
                (
                    "group_delta_over_std_subindustry_25_90",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 25) / ts_std_dev(ts_backfill({field_name}, {bw}), 90), subindustry)",
                    168 + DELTA_STD_PRIORITY_BOOST,
                ),
                (
                    "group_delta_over_std_subindustry_5_20",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 5) / ts_std_dev(ts_backfill({field_name}, {bw}), 20), subindustry)",
                    176 + DELTA_STD_PRIORITY_BOOST,
                ),
                (
                    "group_delta_over_std_subindustry_30_120",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 30) / ts_std_dev(ts_backfill({field_name}, {bw}), 120), subindustry)",
                    166 + DELTA_STD_PRIORITY_BOOST,
                ),
                (
                    "group_delta_over_std_industry_20_60",
                    f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), 20) / ts_std_dev(ts_backfill({field_name}, {bw}), 60), industry)",
                    166 + DELTA_STD_PRIORITY_BOOST,
                ),
                (
                    "group_short_long_mean_spread_subindustry_20_{bw}",
                    f"group_rank(ts_mean(ts_backfill({field_name}, {bw}), 20) - ts_mean(ts_backfill({field_name}, {bw}), {bw}), subindustry)",
                    164,
                ),
                (
                    "group_zscore_subindustry_60",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, {bw}), 60), subindustry)",
                    161,
                ),
                (
                    "rank_mean_spread_over_std_20_{bw}_60",
                    f"rank((ts_mean(ts_backfill({field_name}, {bw}), 20) - ts_mean(ts_backfill({field_name}, {bw}), {bw})) / ts_std_dev(ts_backfill({field_name}, {bw}), 60))",
                    158,
                ),
                (
                    "rank_zscore_spread_20_{bw}",
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
        legacy_templates.extend(
            [
                ("raw_field", field_name, 145),
                ("group_rank_subindustry", f"group_rank({field_name}, subindustry)", 143),
                ("group_rank_industry", f"group_rank({field_name}, industry)", 141),
                ("rank_raw_field", f"rank({field_name})", 118),
            ]
        )
        if use_dataset_heuristics and field_name in POSITIVE_RAW_FIELDS:
            legacy_templates.append(("neg_raw_field", f"-{field_name}", 132))
        elif use_dataset_heuristics and field_name in NEGATIVE_RAW_FIELDS:
            legacy_templates.append(("neg_raw_field", f"-{field_name}", 144))
        elif use_dataset_heuristics:
            legacy_templates.append(("neg_raw_field", f"-{field_name}", 128))

        fields_by_name = {choose_field_name(item): item for item in all_fields}
        partner_names = discover_partner_fields(
            field_name,
            all_fields,
            limit=4,
            use_curated_heuristics=use_dataset_heuristics,
        )
        for partner in partner_names:
            if partner not in fields_by_name:
                continue
            diversified_templates.extend(
                [
                    (
                        f"group_ratio_delta_rank_3_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(rank(ts_backfill({field_name}/{partner}, {bw})), 3), subindustry)",
                        188 + DELTA_STD_PRIORITY_BOOST,
                    ),
                    (
                        f"group_ratio_delta_rank_5_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(rank(ts_backfill({field_name}/{partner}, {bw})), 5), subindustry)",
                        184 + DELTA_STD_PRIORITY_BOOST,
                    ),
                    (
                        f"group_ratio_delta_rank_10_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(rank(ts_backfill({field_name}/{partner}, {bw})), 10), subindustry)",
                        176 + DELTA_STD_PRIORITY_BOOST,
                    ),
                    (
                        f"group_ratio_delta_over_std_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(ts_backfill({field_name}/{partner}, {bw}), 20) / ts_std_dev(ts_backfill({field_name}/{partner}, {bw}), 60), subindustry)",
                        178 + DELTA_STD_PRIORITY_BOOST,
                    ),
                    (
                        f"group_ratio_delta_over_std_15_40_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(ts_backfill({field_name}/{partner}, {bw}), 15) / ts_std_dev(ts_backfill({field_name}/{partner}, {bw}), 40), subindustry)",
                        176 + DELTA_STD_PRIORITY_BOOST,
                    ),
                    (
                        f"group_ratio_delta_over_std_10_60_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(ts_backfill({field_name}/{partner}, {bw}), 10) / ts_std_dev(ts_backfill({field_name}/{partner}, {bw}), 60), subindustry)",
                        174 + DELTA_STD_PRIORITY_BOOST,
                    ),
                    (
                        f"group_ratio_delta_over_std_25_90_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(ts_backfill({field_name}/{partner}, {bw}), 25) / ts_std_dev(ts_backfill({field_name}/{partner}, {bw}), 90), subindustry)",
                        172 + DELTA_STD_PRIORITY_BOOST,
                    ),
                    (
                        f"group_ratio_delta_over_std_5_20_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(ts_backfill({field_name}/{partner}, {bw}), 5) / ts_std_dev(ts_backfill({field_name}/{partner}, {bw}), 20), subindustry)",
                        180 + DELTA_STD_PRIORITY_BOOST,
                    ),
                    (
                        f"group_ratio_delta_over_std_30_120_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(ts_backfill({field_name}/{partner}, {bw}), 30) / ts_std_dev(ts_backfill({field_name}/{partner}, {bw}), 120), subindustry)",
                        170 + DELTA_STD_PRIORITY_BOOST,
                    ),
                    (
                        f"group_ratio_zscore_{field_name}_over_{partner}",
                        f"group_rank(ts_zscore(ts_backfill({field_name}/{partner}, {bw}), 60), subindustry)",
                        160,
                    ),
                    (
                        f"ratio_mean_spread_over_std_{field_name}_over_{partner}",
                        f"rank((ts_mean(ts_backfill({field_name}/{partner}, {bw}), 20) - ts_mean(ts_backfill({field_name}/{partner}, {bw}), {bw})) / ts_std_dev(ts_backfill({field_name}/{partner}, {bw}), 60))",
                        156,
                    ),
                    (
                        f"ratio_zscore_spread_{field_name}_over_{partner}",
                        f"rank(ts_zscore(ts_backfill({field_name}/{partner}, {bw}), 20) - ts_zscore(ts_backfill({field_name}/{partner}, {bw}), {bw}))",
                        152,
                    ),
                ]
            )
            legacy_templates.extend(
                [
                    (f"raw_ratio_{field_name}_over_{partner}", f"{field_name}/{partner}", 154),
                    (f"group_rank_ratio_{field_name}_over_{partner}", f"group_rank({field_name}/{partner}, subindustry)", 152),
                    (f"ratio_{field_name}_over_{partner}", f"rank({field_name}/{partner})", 148),
                    (f"rank_ratio_{field_name}_over_{partner}", f"rank({field_name}/{partner})", 138),
                    (
                        f"decay_ratio_{field_name}_over_{partner}",
                        f"rank(ts_decay_linear(ts_backfill({field_name}/{partner}, {bw}), 10))",
                        126,
                    ),
                ]
            )

        templates.extend(diversified_templates)
        templates.extend(legacy_templates)

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
