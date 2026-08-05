"""Staged blacklist review and promotion tests."""

from __future__ import annotations

from alpha.app.blacklist_commands import run_blacklist_command
from alpha.policy.blacklist_review import promote_staged_blacklist
from alpha.policy.blacklist_store import (
    build_default_blacklist,
    read_blacklist_payload,
    read_blacklist_staging_payload,
    write_blacklist_payload,
    write_blacklist_staging_payload,
)
from alpha.policy.types import LEARNED_BLACKLIST_KEY, PATTERN_RULES_KEY


def _entry(name: str, *, stage: str = "seed") -> dict[str, object]:
    return {
        "name": name,
        "dataset_id": "fundamental6",
        "template_stage": stage,
        "template_family": "cashflow",
        "reason": "low quality",
    }


def test_promote_staged_blacklist_merges_duplicates_and_clears_staging(tmp_path) -> None:
    datasets_root = str(tmp_path / "datasets")
    repository = build_default_blacklist("fundamental6")
    repository[LEARNED_BLACKLIST_KEY] = [_entry("existing")]
    repository[PATTERN_RULES_KEY] = [{"target": "template_name", "pattern": "legacy"}]
    write_blacklist_payload("fundamental6", repository, datasets_root=datasets_root)

    staging = build_default_blacklist("fundamental6")
    staging[LEARNED_BLACKLIST_KEY] = [_entry("existing"), _entry("new")]
    staging[PATTERN_RULES_KEY] = [
        {"target": "template_name", "pattern": "legacy"},
        {"target": "expression", "pattern": "unstable"},
    ]
    write_blacklist_staging_payload("fundamental6", staging, datasets_root=datasets_root)

    summary = promote_staged_blacklist("fundamental6", datasets_root=datasets_root)

    assert summary.promoted_entries == 1
    assert summary.duplicate_entries == 1
    assert summary.promoted_rules == 1
    promoted = read_blacklist_payload("fundamental6", datasets_root=datasets_root)
    assert [item["name"] for item in promoted[LEARNED_BLACKLIST_KEY]] == ["existing", "new"]
    assert len(promoted[PATTERN_RULES_KEY]) == 2
    cleared = read_blacklist_staging_payload("fundamental6", datasets_root=datasets_root)
    assert cleared[LEARNED_BLACKLIST_KEY] == []
    assert cleared[PATTERN_RULES_KEY] == []


def test_blacklist_review_command_prints_pending_entries(tmp_path, capsys) -> None:
    datasets_root = str(tmp_path / "datasets")
    staging = build_default_blacklist("fundamental6")
    staging[LEARNED_BLACKLIST_KEY] = [_entry("candidate")]
    write_blacklist_staging_payload("fundamental6", staging, datasets_root=datasets_root)

    assert (
        run_blacklist_command(
            "blacklist-review",
            dataset_id="fundamental6",
            datasets_root=datasets_root,
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "staged_entries=1" in output
    assert "name=candidate" in output


def test_blacklist_promote_command_reports_empty_staging(tmp_path, capsys) -> None:
    assert (
        run_blacklist_command(
            "blacklist-promote",
            dataset_id="fundamental6",
            datasets_root=str(tmp_path / "datasets"),
        )
        == 0
    )

    assert "promoted_entries=0/0" in capsys.readouterr().out
