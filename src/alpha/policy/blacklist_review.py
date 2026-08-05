"""Review and promotion workflow for staged learned blacklist entries."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any

from ..config.constants import DATE_FORMAT_ISO
from .blacklist_store import (
    build_default_blacklist,
    exclusive_blacklist_transaction,
    invalidate_blacklist_runtime_cache,
    read_blacklist_payload,
    read_blacklist_staging_payload,
    write_blacklist_payload,
    write_blacklist_staging_payload,
)
from .types import (
    LEARNED_BLACKLIST_KEY,
    PATTERN_RULES_KEY,
    BlacklistPayload,
    build_blacklist_entry_key,
)


@dataclass(frozen=True, slots=True)
class BlacklistPromotionSummary:
    """Counts produced by one atomic staging promotion."""

    staged_entries: int
    promoted_entries: int
    duplicate_entries: int
    staged_rules: int
    promoted_rules: int


def _dict_entries(payload: BlacklistPayload, key: str) -> list[dict[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def staged_blacklist_entries(
    dataset_id: str,
    *,
    datasets_root: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load staged learned entries and expression rules for human review."""
    payload = read_blacklist_staging_payload(dataset_id, datasets_root=datasets_root)
    return (
        _dict_entries(payload, LEARNED_BLACKLIST_KEY),
        _dict_entries(payload, PATTERN_RULES_KEY),
    )


def _learned_entry_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return build_blacklist_entry_key(
        str(item.get("name", "")),
        str(item.get("field_type", "")),
        str(item.get("template_stage", "")),
        str(item.get("template_family", "")),
    )


def _rule_key(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def promote_staged_blacklist(
    dataset_id: str,
    *,
    datasets_root: str = "",
) -> BlacklistPromotionSummary:
    """Atomically merge staged entries into the repository blacklist and clear staging."""
    with exclusive_blacklist_transaction(dataset_id, datasets_root=datasets_root):
        repository = read_blacklist_payload(dataset_id, datasets_root=datasets_root)
        staging = read_blacklist_staging_payload(dataset_id, datasets_root=datasets_root)
        repository_entries = _dict_entries(repository, LEARNED_BLACKLIST_KEY)
        staged_entries = _dict_entries(staging, LEARNED_BLACKLIST_KEY)
        existing_entry_keys = {_learned_entry_key(item) for item in repository_entries}
        promoted_entries: list[dict[str, Any]] = []
        for item in staged_entries:
            entry_key = _learned_entry_key(item)
            if not entry_key[0] or entry_key in existing_entry_keys:
                continue
            promoted_entries.append(item)
            existing_entry_keys.add(entry_key)

        repository_rules = _dict_entries(repository, PATTERN_RULES_KEY)
        staged_rules = _dict_entries(staging, PATTERN_RULES_KEY)
        existing_rule_keys = {_rule_key(item) for item in repository_rules}
        promoted_rules: list[dict[str, Any]] = []
        for item in staged_rules:
            rule_key = _rule_key(item)
            if rule_key in existing_rule_keys:
                continue
            promoted_rules.append(item)
            existing_rule_keys.add(rule_key)

        repository[LEARNED_BLACKLIST_KEY] = [*repository_entries, *promoted_entries]
        repository[PATTERN_RULES_KEY] = [*repository_rules, *promoted_rules]
        repository["_updated"] = time.strftime(DATE_FORMAT_ISO)
        write_blacklist_payload(dataset_id, repository, datasets_root=datasets_root)
        write_blacklist_staging_payload(
            dataset_id,
            build_default_blacklist(dataset_id),
            datasets_root=datasets_root,
        )

    invalidate_blacklist_runtime_cache(dataset_id)
    return BlacklistPromotionSummary(
        staged_entries=len(staged_entries),
        promoted_entries=len(promoted_entries),
        duplicate_entries=len(staged_entries) - len(promoted_entries),
        staged_rules=len(staged_rules),
        promoted_rules=len(promoted_rules),
    )
