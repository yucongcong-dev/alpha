"""
字段配对发现逻辑。

本模块负责为 ratio 类模板寻找合适的分母/配对字段，避免
expressions.py 同时承担字段配对、模板构造和表达式变异等多重职责。
"""

from __future__ import annotations

from collections.abc import Sequence
import re

from ...config import (
    ALLOWED_EXTERNAL_RATIO_PARTNERS,
    PARTNER_KEYWORD_MATCH_SCORE,
    PARTNER_PREFERRED_BASE_SCORE,
    PARTNER_RANK_MAX_SCORE,
    PARTNER_RANK_STEP_PENALTY,
    PARTNER_REVERSE_KEYWORD_SCORE,
    PARTNER_SELF_MATCH_PENALTY,
    PARTNER_SHARED_TOKEN_WEIGHT,
    PARTNER_SUBSTRING_SCORE,
    DatasetExpressionPolicy,
)
from ...models.base import TemplateField
from ...utils.helpers import choose_field_name, choose_field_type

_TOKENIZE_REGEX: re.Pattern = re.compile(r"[^a-z0-9]+")
"""字段名分词正则模式（预编译）。"""


def tokenize_field_name(field_name: str) -> list[str]:
    """
    将字段名拆分为小写字母数字 token。

    Args:
        field_name: 要拆分的字段名称。

    Returns:
        list[str]: 拆分后的小写 token 列表，去除空 token。
    """
    return [token for token in _TOKENIZE_REGEX.split(field_name.lower()) if token]


def score_partner_candidate(
    field_name: str,
    partner_name: str,
    policy: DatasetExpressionPolicy,
) -> int:
    """
    启发式打分两个字段是否适合作为比值配对。

    得分越高表示越适合配对；负值表示应排除。
    """
    if field_name == partner_name:
        return PARTNER_SELF_MATCH_PENALTY
    field_tokens = set(tokenize_field_name(field_name))
    partner_tokens = set(tokenize_field_name(partner_name))
    score = 0
    preferred_partners = policy.ratio_partner_candidates.get(field_name, ())
    if partner_name in preferred_partners:
        score += PARTNER_PREFERRED_BASE_SCORE
        preferred_rank = preferred_partners.index(partner_name)
        score += max(0, PARTNER_RANK_MAX_SCORE - preferred_rank * PARTNER_RANK_STEP_PENALTY)
    if partner_name in policy.ratio_keywords.get(field_name, ()):
        score += PARTNER_KEYWORD_MATCH_SCORE
    if field_name in policy.ratio_keywords.get(partner_name, ()):
        score += PARTNER_REVERSE_KEYWORD_SCORE
    if field_tokens & partner_tokens:
        score += PARTNER_SHARED_TOKEN_WEIGHT * len(field_tokens & partner_tokens)
    for token in field_tokens:
        if token and token in partner_name:
            score += PARTNER_SUBSTRING_SCORE
    score += int(policy.preferred_partner_score_bonuses.get(partner_name, 0))
    return score


def discover_partner_fields(
    field_name: str,
    all_fields: Sequence[TemplateField],
    policy: DatasetExpressionPolicy,
    *,
    limit: int = 4,
) -> list[str]:
    """
    为比值类模板扩展寻找可能合适的配对字段。

    Args:
        field_name: 主字段名称。
        all_fields: 所有可用字段元数据。
        policy: 数据集表达式策略。
        limit: 返回的配对字段数量上限。

    Returns:
        list[str]: 配对字段名称列表，按启发式得分排序。
    """
    if not policy.use_curated_heuristics:
        return []

    candidates: list[tuple[int, str]] = []
    available_by_name = {
        choose_field_name(item): item for item in all_fields if choose_field_type(item) == "MATRIX"
    }

    for partner_name in policy.ratio_partner_candidates.get(field_name, ()):
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
        score = score_partner_candidate(field_name, partner_name, policy)
        if score <= 0:
            continue
        candidates.append((score, partner_name))
    candidates.sort(key=lambda item: (-item[0], item[1]))

    seen: set[str] = set()
    result: list[str] = []
    for _, partner_name in candidates:
        if partner_name in seen:
            continue
        seen.add(partner_name)
        result.append(partner_name)
        if len(result) >= limit:
            break
    return result
