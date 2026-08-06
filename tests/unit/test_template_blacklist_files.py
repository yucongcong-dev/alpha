"""Dataset template and blacklist file lifecycle tests."""

from __future__ import annotations

import json

from alpha.generators.templates.variation_common import (
    is_blacklisted_template as _is_blacklisted_template,
)
from alpha.policy.blacklist_store import ensure_template_blacklist_file
from alpha.policy.template_blacklist import invalidate_blacklist_cache


def test_ensure_template_blacklist_file_creates_empty_dataset_file(tmp_path) -> None:
    """Missing dataset blacklist files should be created with the expected schema."""
    path = ensure_template_blacklist_file("custom_ds", datasets_root=str(tmp_path / "datasets"))

    blacklist_file = tmp_path / "datasets" / "custom_ds" / "blacklist.json"
    payload = json.loads(blacklist_file.read_text(encoding="utf-8"))
    assert path == str(blacklist_file)
    assert payload["dataset_id"] == "custom_ds"
    assert payload["learned_templates"] == []
    assert payload["expression_rules"] == []


def test_blacklist_prefers_name_and_stage_over_name_only(monkeypatch, tmp_path) -> None:
    blacklist_file = tmp_path / "datasets" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "learned_templates": [
                    {
                        "name": "weak_template",
                        "template_stage": "group_second_order",
                        "template_family": "group_zscore",
                    }
                ],
                "expression_rules": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()

    assert _is_blacklisted_template(
        "weak_template",
        "group_rank(ts_zscore(close, 60), subindustry)",
        template_metadata={"stage": "group_second_order", "family": "group_zscore"},
        dataset_id="custom_ds",
    )
    assert not _is_blacklisted_template(
        "weak_template",
        "rank(ts_zscore(close, 60))",
        template_metadata={"stage": "first_order", "family": "zscore_time"},
        dataset_id="custom_ds",
    )


def test_legacy_blacklist_name_only_only_applies_without_runtime_metadata(
    monkeypatch, tmp_path
) -> None:
    blacklist_file = tmp_path / "datasets" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "learned_templates": [{"name": "legacy_template"}],
                "expression_rules": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()

    assert _is_blacklisted_template("legacy_template", dataset_id="custom_ds")
    assert not _is_blacklisted_template(
        "legacy_template",
        "rank(close)",
        template_metadata={"stage": "first_order", "family": "legacy_level"},
        dataset_id="custom_ds",
    )


def test_blacklist_pattern_rules_support_exact_and_regex(monkeypatch, tmp_path) -> None:
    blacklist_file = tmp_path / "datasets" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "learned_templates": [],
                "expression_rules": [
                    {"type": "exact", "pattern": "rank(close)"},
                    {"type": "regex", "pattern": r"ts_delta\(.*?, 5\)"},
                    {
                        "target": "template_name",
                        "type": "contains",
                        "pattern": "blocked_name",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()

    assert _is_blacklisted_template("t1", "rank(close)", dataset_id="custom_ds")
    assert _is_blacklisted_template("t2", "rank(ts_delta(close, 5))", dataset_id="custom_ds")
    assert _is_blacklisted_template("blocked_name_template", "rank(open)", dataset_id="custom_ds")
    assert not _is_blacklisted_template("t3", "rank(close) + 1", dataset_id="custom_ds")
