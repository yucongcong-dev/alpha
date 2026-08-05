"""Local CLI commands for staged blacklist review and promotion."""

from __future__ import annotations

from ..policy.blacklist_review import promote_staged_blacklist, staged_blacklist_entries


def run_blacklist_command(
    command: str,
    *,
    dataset_id: str,
    datasets_root: str,
) -> int:
    """Run one local blacklist command without authentication or runtime bootstrap."""
    if command == "blacklist-review":
        entries, rules = staged_blacklist_entries(dataset_id, datasets_root=datasets_root)
        print(
            f"[blacklist-review] dataset={dataset_id} "
            f"staged_entries={len(entries)} staged_rules={len(rules)}"
        )
        for item in entries:
            print(
                "[blacklist-review] "
                f"name={item.get('name', '')} stage={item.get('template_stage', '')} "
                f"family={item.get('template_family', '')} reason={item.get('reason', '')}"
            )
        for item in rules:
            print(f"[blacklist-review] rule={item}")
        return 0

    if command == "blacklist-promote":
        summary = promote_staged_blacklist(dataset_id, datasets_root=datasets_root)
        print(
            f"[blacklist-promote] dataset={dataset_id} "
            f"promoted_entries={summary.promoted_entries}/{summary.staged_entries} "
            f"duplicates={summary.duplicate_entries} "
            f"promoted_rules={summary.promoted_rules}/{summary.staged_rules}"
        )
        return 0

    raise ValueError(f"unsupported blacklist command: {command}")
