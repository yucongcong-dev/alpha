"""
模板黑名单匹配策略。

本模块只负责读取黑名单文件、维护缓存、匹配模板名称/表达式规则。
表达式分类由调用方传入，避免和 generators.expressions 形成循环依赖。
"""

from __future__ import annotations

import logging
import os
import re

from ..models.domain_types import TemplateMetadata
from .blacklist_context import clear_active_datasets_root
from .blacklist_store import (
    invalidate_blacklist_path_cache,
    read_blacklist_payload,
    resolve_blacklist_path,
)
from .types import (
    LEARNED_BLACKLIST_KEY,
    PATTERN_RULES_KEY,
    BlacklistCacheEntry,
    BlacklistMatcherEntry,
    BlacklistPatternRule,
    BlacklistRuntimePolicy,
)

_BLACKLIST_CACHE: dict[str, BlacklistCacheEntry] = {}
"""按 dataset_id 缓存的黑名单数据，带文件签名用于热更新检测。"""
logger = logging.getLogger(__name__)


def _file_signature(path: str | None) -> tuple[int, int] | None:
    """返回文件签名：(mtime_ns, size)。"""
    if not path or not os.path.isfile(path):
        return None
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def invalidate_blacklist_cache(dataset_id: str = "") -> None:
    """使黑名单缓存失效，便于同进程内感知文件更新。"""
    if dataset_id:
        _BLACKLIST_CACHE.pop(dataset_id, None)
        invalidate_blacklist_path_cache(dataset_id)
        return
    _BLACKLIST_CACHE.clear()
    invalidate_blacklist_path_cache()
    clear_active_datasets_root()


def _normalize_pattern_rule(rule: dict[str, object]) -> BlacklistPatternRule | None:
    """规范化模板名称或表达式的黑名单 pattern 规则。"""
    pattern = str(rule.get("pattern", "")).strip()
    if not pattern:
        return None
    match_type = str(rule.get("type", "contains")).strip().lower() or "contains"
    if match_type not in {"contains", "exact", "regex"}:
        match_type = "contains"
    target = str(rule.get("target", "expression")).strip().lower() or "expression"
    if target not in {"expression", "template_name"}:
        target = "expression"
    return {"pattern": pattern, "type": match_type, "target": target}


def _match_pattern_rule(
    template_name: str,
    expression: str,
    rule: BlacklistPatternRule,
) -> bool:
    """按 target 和规则类型匹配模板名称或表达式。"""
    pattern = rule.get("pattern", "")
    match_type = rule.get("type", "contains")
    value = template_name if rule.get("target") == "template_name" else expression
    if not pattern:
        return False
    if match_type == "exact":
        return value.strip() == pattern
    if match_type == "regex":
        try:
            return re.search(pattern, value) is not None
        except re.error:
            return False
    return pattern in value


def _load_blacklist(dataset_id: str) -> None:
    """加载 datasets/<dataset>/blacklist.json。"""
    names: set[str] = set()
    pattern_rules: list[BlacklistPatternRule] = []
    entries: list[BlacklistMatcherEntry] = []
    dataset_signature: tuple[int, int] | None = None

    blacklist_path = resolve_blacklist_path(dataset_id)
    if os.path.isfile(blacklist_path):
        dataset_signature = _file_signature(blacklist_path)
    else:
        blacklist_path = ""
    cached = _BLACKLIST_CACHE.get(dataset_id)
    if (
        isinstance(cached, dict)
        and cached.get("dataset_path") == blacklist_path
        and cached.get("dataset_signature") == dataset_signature
    ):
        return
    if blacklist_path:
        try:
            ds_raw = read_blacklist_payload(dataset_id)
            for item in ds_raw.get(LEARNED_BLACKLIST_KEY, []):
                if isinstance(item, dict) and item.get("name"):
                    names.add(item["name"])
                    entries.append(
                        {
                            "name": str(item.get("name", "")).strip(),
                            "field_type": str(item.get("field_type", "")).strip().upper(),
                            "template_stage": str(item.get("template_stage", "")).strip().lower(),
                            "template_family": str(item.get("template_family", "")).strip().lower(),
                        }
                    )
            for rule in ds_raw.get(PATTERN_RULES_KEY, []):
                if isinstance(rule, dict):
                    normalized_rule = _normalize_pattern_rule(rule)
                    if normalized_rule is not None:
                        pattern_rules.append(normalized_rule)
        except OSError:
            logger.warning(
                "[blacklist] failed to load dataset blacklist from %s; ignoring file",
                blacklist_path,
            )

    _BLACKLIST_CACHE[dataset_id] = {
        "names": names,
        "pattern_rules": pattern_rules,
        "entries": entries,
        "dataset_path": blacklist_path,
        "dataset_signature": dataset_signature,
    }


def runtime_blacklist_match_reason(
    template_name: str,
    expression: str = "",
    *,
    template_metadata: TemplateMetadata | None = None,
    dataset_id: str = "",
    policy: BlacklistRuntimePolicy | None = None,
    current_field_type: str = "",
    current_family: str = "",
    current_stage: str = "",
) -> str | None:
    """Match a template against blacklist rules with optional runtime policy context."""
    effective_dataset_id = policy.dataset_id if policy is not None else dataset_id
    protected_templates = policy.protected_templates if policy is not None else set()
    return blacklist_match_reason(
        template_name,
        expression,
        dataset_id=effective_dataset_id,
        current_field_type=current_field_type,
        current_family=current_family,
        current_stage=current_stage,
        has_runtime_context=bool(template_metadata or expression),
        protected_templates=set(protected_templates),
    )


def is_blacklisted_template(
    template_name: str,
    expression: str = "",
    *,
    template_metadata: TemplateMetadata | None = None,
    dataset_id: str = "",
    policy: BlacklistRuntimePolicy | None = None,
    current_field_type: str = "",
    current_family: str = "",
    current_stage: str = "",
) -> bool:
    """Return whether the template is blocked by dataset or policy blacklist rules."""
    return (
        runtime_blacklist_match_reason(
            template_name,
            expression,
            template_metadata=template_metadata,
            dataset_id=dataset_id,
            policy=policy,
            current_field_type=current_field_type,
            current_family=current_family,
            current_stage=current_stage,
        )
        is not None
    )


def blacklist_match_reason(
    template_name: str,
    expression: str,
    *,
    dataset_id: str,
    current_field_type: str,
    current_family: str,
    current_stage: str,
    has_runtime_context: bool,
    protected_templates: set[str],
) -> str | None:
    """返回命中的黑名单原因；未命中则返回 None。"""
    if template_name in protected_templates:
        return None
    if dataset_id:
        _load_blacklist(dataset_id)
        cached = _BLACKLIST_CACHE.get(dataset_id, {})
        matched_legacy_name = False
        for entry in cached.get("entries", []):
            if not isinstance(entry, dict) or entry.get("name") != template_name:
                continue
            entry_field_type = str(entry.get("field_type", "")).strip().upper()
            entry_stage = str(entry.get("template_stage", "")).strip().lower()
            entry_family = str(entry.get("template_family", "")).strip().lower()
            if entry_field_type and (
                not current_field_type or current_field_type.upper() != entry_field_type
            ):
                continue
            if entry_stage:
                if current_stage != entry_stage:
                    continue
                if entry_family and current_family and current_family != entry_family:
                    continue
                return f"name+stage{'+family' if entry_family else ''}"
            if entry_family:
                if current_family and current_family == entry_family:
                    return "name+family"
                continue
            matched_legacy_name = True
        if matched_legacy_name and not has_runtime_context:
            return "legacy_name_only"
        for rule in cached.get("pattern_rules", []):
            if isinstance(rule, dict) and _match_pattern_rule(template_name, expression, rule):
                return f"pattern:{rule.get('target', 'expression')}:{rule.get('type', 'contains')}"
    return None
