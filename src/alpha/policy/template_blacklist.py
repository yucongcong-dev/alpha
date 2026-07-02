"""
模板黑名单匹配策略。

本模块只负责读取黑名单文件、维护缓存、匹配模板名称/表达式规则。
表达式分类由调用方传入，避免和 generators.expressions 形成循环依赖。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from ..io.common import resolve_runtime_data_dir, sanitize_dataset_id_for_filename

_BLACKLIST_CACHE: dict[str, dict[str, Any]] = {}
"""按 dataset_id 缓存的黑名单数据，带文件签名用于热更新检测。"""
_DEFAULT_AVOID_RULES_CACHE: dict[str, Any] | None = None
"""跨数据集默认规避规则缓存，带文件签名用于热更新检测。"""


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
        return
    _BLACKLIST_CACHE.clear()


def _load_default_avoid_rules() -> list[dict[str, str]]:
    """加载跨数据集默认规避规则 template_blacklist.json。"""
    global _DEFAULT_AVOID_RULES_CACHE
    runtime_data_dir = resolve_runtime_data_dir()
    candidates = [os.path.join(str(runtime_data_dir), "template_blacklist.json")]
    for path in candidates:
        if os.path.isfile(path):
            signature = _file_signature(path)
            if (
                isinstance(_DEFAULT_AVOID_RULES_CACHE, dict)
                and _DEFAULT_AVOID_RULES_CACHE.get("path") == path
                and _DEFAULT_AVOID_RULES_CACHE.get("signature") == signature
            ):
                cached_rules = _DEFAULT_AVOID_RULES_CACHE.get("rules")
                if isinstance(cached_rules, list):
                    return cached_rules
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                if not isinstance(raw, dict):
                    continue
                rules = raw.get("_default_auto_avoid_rules", [])
                if not isinstance(rules, list):
                    rules = []
                _DEFAULT_AVOID_RULES_CACHE = {
                    "path": path,
                    "signature": signature,
                    "rules": rules,
                }
                return rules
            except (json.JSONDecodeError, OSError):
                continue
    _DEFAULT_AVOID_RULES_CACHE = {"path": None, "signature": None, "rules": []}
    return []


def _normalize_pattern_rule(rule: dict[str, Any]) -> dict[str, str] | None:
    """规范化黑名单 pattern 规则。"""
    pattern = str(rule.get("pattern", "")).strip()
    if not pattern:
        return None
    match_type = str(rule.get("type", "contains")).strip().lower() or "contains"
    if match_type not in {"contains", "exact", "regex"}:
        match_type = "contains"
    return {"pattern": pattern, "type": match_type}


def _match_pattern_rule(expression: str, rule: dict[str, str]) -> bool:
    """按规则类型匹配表达式黑名单。"""
    pattern = rule.get("pattern", "")
    match_type = rule.get("type", "contains")
    if not pattern:
        return False
    if match_type == "exact":
        return expression.strip() == pattern
    if match_type == "regex":
        try:
            return re.search(pattern, expression) is not None
        except re.error:
            return False
    return pattern in expression


def _load_blacklist(dataset_id: str) -> None:
    """按 dataset_id 加载统一黑名单文件 blacklists/{dataset_id}/blacklist.json。"""
    names: set[str] = set()
    pattern_rules: list[dict[str, str]] = []
    entries: list[dict[str, str]] = []
    dataset_signature: tuple[int, int] | None = None

    runtime_data_dir = resolve_runtime_data_dir()
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    legacy_filename = f"template_blacklist_{dataset_id}.json"
    candidates = list(
        dict.fromkeys(
            [
                os.path.join(str(runtime_data_dir), "blacklists", dataset_key, "blacklist.json"),
                os.path.join(str(runtime_data_dir), legacy_filename),
            ]
        )
    )
    blacklist_path = ""
    for path in candidates:
        if os.path.isfile(path):
            blacklist_path = path
            dataset_signature = _file_signature(path)
            break
    default_rules = _load_default_avoid_rules()
    default_cache_signature = None
    if isinstance(_DEFAULT_AVOID_RULES_CACHE, dict):
        default_cache_signature = _DEFAULT_AVOID_RULES_CACHE.get("signature")
    cached = _BLACKLIST_CACHE.get(dataset_id)
    if (
        isinstance(cached, dict)
        and cached.get("dataset_path") == blacklist_path
        and cached.get("dataset_signature") == dataset_signature
        and cached.get("default_signature") == default_cache_signature
    ):
        return
    if blacklist_path:
        try:
            with open(blacklist_path, "r", encoding="utf-8") as fh:
                ds_raw = json.load(fh)
            if isinstance(ds_raw, dict):
                for item in ds_raw.get("blacklisted_templates", []):
                    if isinstance(item, dict) and item.get("name"):
                        names.add(item["name"])
                        entries.append(
                            {
                                "name": str(item.get("name", "")).strip(),
                                "template_stage": str(item.get("template_stage", "")).strip().lower(),
                                "template_family": str(item.get("template_family", "")).strip().lower(),
                            }
                        )
                for rule in ds_raw.get("auto_avoid_rules", []):
                    if isinstance(rule, dict):
                        normalized_rule = _normalize_pattern_rule(rule)
                        if normalized_rule is not None:
                            pattern_rules.append(normalized_rule)
        except (json.JSONDecodeError, OSError):
            pass

    for rule in default_rules:
        if isinstance(rule, dict):
            normalized_rule = _normalize_pattern_rule(rule)
            if normalized_rule is not None and normalized_rule not in pattern_rules:
                pattern_rules.append(normalized_rule)

    _BLACKLIST_CACHE[dataset_id] = {
        "names": names,
        "pattern_rules": pattern_rules,
        "entries": entries,
        "dataset_path": blacklist_path,
        "dataset_signature": dataset_signature,
        "default_signature": default_cache_signature,
    }


def blacklist_match_reason(
    template_name: str,
    expression: str,
    *,
    dataset_id: str,
    current_family: str,
    current_stage: str,
    has_runtime_context: bool,
    protected_templates: set[str],
    blocked_name_substrings: tuple[str, ...],
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
            entry_stage = str(entry.get("template_stage", "")).strip().lower()
            entry_family = str(entry.get("template_family", "")).strip().lower()
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
            if isinstance(rule, dict) and _match_pattern_rule(expression, rule):
                return f"pattern:{rule.get('type', 'contains')}"
        for blocked_substring in blocked_name_substrings:
            if blocked_substring and blocked_substring in template_name:
                return "policy_name_substring"
    else:
        for rule in _load_default_avoid_rules():
            normalized_rule = _normalize_pattern_rule(rule) if isinstance(rule, dict) else None
            if normalized_rule and _match_pattern_rule(expression, normalized_rule):
                return f"default_pattern:{normalized_rule.get('type', 'contains')}"
    return None
