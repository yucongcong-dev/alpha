"""Dataset template and blacklist file lifecycle tests."""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

from alpha.core.executor import build_pending_templates_for_field, inflight_template_keys
from alpha.core.scheduler import handle_completed_future
from alpha.generators import templates as template_module
from alpha.generators.expression_builder import _is_blacklisted_template
from alpha.generators.payload import build_settings_fingerprint_from_payload
from alpha.generators.templates import ensure_dataset_template_library, load_template_library
from alpha.generators.templates import library_paths as _library_paths
from alpha.policy.blacklist_runtime import auto_update_blacklist
from alpha.policy.blacklist_store import ensure_template_blacklist_file, invalidate_blacklist_path_cache
from alpha.models.domain import FailedCheck, FieldTestResult, TemplateCandidate, TemplateLibraryItem
from alpha.models.runtime import (
    ExecutionState,
    FutureCompletionContext,
    PendingFutureContext,
    ResultWriteOptions,
    TemplateBuildContext,
    TemplateBuildOptions,
)
from alpha.policy.expression import get_dataset_expression_policy
from alpha.policy.template_blacklist import invalidate_blacklist_cache


def test_ensure_dataset_template_library_copies_base_when_missing(monkeypatch, tmp_path) -> None:
    """Missing dataset-specific template files should be generated from the base library."""
    base = tmp_path / "worldquant_template_library.json"
    target = tmp_path / "worldquant_template_library_custom_ds.json"
    base.write_text(
        json.dumps(
            {
                "_comment": "base",
                "default": [
                    {
                        "name": "rank_backfill",
                        "expression": "rank(ts_backfill({field}, {backfill_window}))",
                        "priority": 123,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(_library_paths, "_BUILTIN_TEMPLATE_LIBRARY_FILE", str(base))

    resolved = ensure_dataset_template_library(str(target), "custom_ds")

    assert resolved == str(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["_dataset_id"] == "custom_ds"
    assert payload["default"][0]["name"] == "rank_backfill"
    assert payload["default"][0]["priority"] == 123

    library = load_template_library(str(target))
    assert library["default"][0].priority == 123


def test_ensure_dataset_template_library_preserves_existing(monkeypatch, tmp_path) -> None:
    """Existing dataset template files should not be overwritten by the base library."""
    base = tmp_path / "worldquant_template_library.json"
    target = tmp_path / "worldquant_template_library_custom_ds.json"
    base.write_text(
        json.dumps({"default": [{"name": "base", "expression": "rank({field})"}]}),
        encoding="utf-8",
    )
    target.write_text(
        json.dumps({"default": [{"name": "custom", "expression": "zscore({field})"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_library_paths, "_BUILTIN_TEMPLATE_LIBRARY_FILE", str(base))

    ensure_dataset_template_library(str(target), "custom_ds")

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["default"][0]["name"] == "custom"


def test_load_template_library_preserves_optional_metadata(tmp_path) -> None:
    template_file = tmp_path / "library.json"
    template_file.write_text(
        json.dumps(
            {
                "default": [
                    {
                        "name": "custom",
                        "expression": "rank({field})",
                        "priority": 100,
                        "family": "custom_family",
                        "layer": "ratio",
                        "stage": "first_order",
                        "requires_partner_field": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    library = load_template_library(str(template_file))

    item = library["default"][0]
    assert item.family == "custom_family"
    assert item.metadata.get("layer") == "ratio"
    assert item.stage == "first_order"
    assert item.metadata.get("requires_partner_field") is False


def test_load_template_library_infers_stage_from_layer(tmp_path) -> None:
    template_file = tmp_path / "library.json"
    template_file.write_text(
        json.dumps(
            {
                "default": [
                    {
                        "name": "group_custom",
                        "expression": "group_rank({field}, subindustry)",
                        "priority": 100,
                        "layer": "group",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    library = load_template_library(str(template_file))

    assert library["default"][0].stage == "group_second_order"


def test_ensure_dataset_template_library_fills_missing_priorities(
    monkeypatch, tmp_path
) -> None:
    """Missing priorities should be filled by file order without overwriting manual values."""
    base = tmp_path / "worldquant_template_library.json"
    target = tmp_path / "worldquant_template_library_custom_ds.json"
    base.write_text(json.dumps({"default": []}), encoding="utf-8")
    target.write_text(
        json.dumps(
            {
                "default": [
                    {"name": "first", "expression": "rank({field})"},
                    {"name": "manual", "expression": "zscore({field})", "priority": 999},
                    {"name": "third", "expression": "scale({field})"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(_library_paths, "_BUILTIN_TEMPLATE_LIBRARY_FILE", str(base))

    ensure_dataset_template_library(str(target), "custom_ds")

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert [item["priority"] for item in payload["default"]] == [1000, 999, 998]


def test_ensure_dataset_template_library_does_not_mutate_base_template(
    monkeypatch, tmp_path
) -> None:
    """The tracked base template library should not be rewritten by priority filling."""
    base = tmp_path / "worldquant_template_library.json"
    base.write_text(
        json.dumps({"default": [{"name": "base", "expression": "rank({field})"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_library_paths, "_BUILTIN_TEMPLATE_LIBRARY_FILE", str(base))

    ensure_dataset_template_library(str(base), "custom_ds")

    payload = json.loads(base.read_text(encoding="utf-8"))
    assert "priority" not in payload["default"][0]


def test_load_template_library_legacy_base_path_falls_back_to_new_location(
    monkeypatch, tmp_path
) -> None:
    new_base = tmp_path / "templates" / "base" / "library.json"
    legacy_base = tmp_path / "worldquant_template_library.json"
    new_base.parent.mkdir(parents=True, exist_ok=True)
    new_base.write_text(
        json.dumps({"default": [{"name": "base", "expression": "rank({field})"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_library_paths, "_BUILTIN_TEMPLATE_LIBRARY_FILE", str(new_base))
    monkeypatch.setattr(_library_paths, "_LEGACY_BUILTIN_TEMPLATE_LIBRARY_FILE", str(legacy_base))

    library = load_template_library(str(legacy_base))

    assert library["default"][0].name == "base"


def test_ensure_template_blacklist_file_creates_empty_dataset_file(tmp_path) -> None:
    """Missing dataset blacklist files should be created with the expected schema."""
    path = ensure_template_blacklist_file("custom_ds", data_dir=str(tmp_path))

    blacklist_file = tmp_path / "blacklists" / "custom_ds" / "blacklist.json"
    payload = json.loads(blacklist_file.read_text(encoding="utf-8"))
    assert path == str(blacklist_file)
    assert payload["dataset_id"] == "custom_ds"
    assert payload["blacklisted_templates"] == []
    assert payload["auto_avoid_rules"] == []


def test_auto_update_blacklist_appends_low_quality_template_once(tmp_path) -> None:
    """Low-quality templates should be appended to the dataset blacklist without duplicates."""
    results = [
        FieldTestResult(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            expression="rank(sales)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.1),
                FailedCheck(name="LOW_FITNESS", value=0.2),
            ],
        ),
        FieldTestResult(
            field_id="assets",
            field_type="MATRIX",
            field_name="assets",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            expression="rank(assets)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.2),
                FailedCheck(name="LOW_FITNESS", value=0.3),
            ],
        ),
    ]

    auto_update_blacklist(results, "custom_ds", data_dir=str(tmp_path))
    auto_update_blacklist(results, "custom_ds", data_dir=str(tmp_path))

    payload = json.loads((tmp_path / "blacklists" / "custom_ds" / "blacklist.json").read_text(encoding="utf-8"))
    entries = payload["blacklisted_templates"]
    assert [entry["name"] for entry in entries] == ["weak_template"]
    assert entries[0]["template_family"] == "group_vol_scaled_delta"
    assert entries[0]["fields_tested"] == ["sales", "assets"]


def test_auto_update_blacklist_is_visible_to_same_process(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()

    assert not _is_blacklisted_template("weak_template", "rank(close)", dataset_id="custom_ds")

    results = [
        FieldTestResult(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            template_stage="group_second_order",
            expression="rank(sales)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.1),
                FailedCheck(name="LOW_FITNESS", value=0.2),
            ],
        ),
        FieldTestResult(
            field_id="assets",
            field_type="MATRIX",
            field_name="assets",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            template_stage="group_second_order",
            expression="rank(assets)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.2),
                FailedCheck(name="LOW_FITNESS", value=0.3),
            ],
        ),
    ]

    auto_update_blacklist(results, "custom_ds", data_dir=str(data_dir))

    assert _is_blacklisted_template(
        "weak_template",
        "group_rank(ts_zscore(close, 60), subindustry)",
        template_metadata={
            "stage": "group_second_order",
            "family": "group_vol_scaled_delta",
        },
        dataset_id="custom_ds",
    )


def test_scheduler_dump_results_shrinks_next_template_queue(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    results_path = tmp_path / "results.json"
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()
    invalidate_blacklist_path_cache()
    monkeypatch.setattr("alpha.io.common.DATA_DIR", data_dir)
    monkeypatch.setattr(
        "alpha.core.executor.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )

    args = Namespace(
        output=str(results_path),
        dataset_id="custom_ds",
        auto_update_blacklist=True,
        template_disable_after=0,
        disable_legacy_after=0,
        max_templates_per_field=1000,
        max_templates_per_family=1000,
        legacy_similarity_penalty=0,
    )
    completion_ctx = FutureCompletionContext(
        result_write_options=ResultWriteOptions(
            dataset_id=args.dataset_id,
            output_path=args.output,
            auto_update_blacklist=args.auto_update_blacklist,
        ),
        settings_fingerprint="settings_fp",
        template_library_fingerprint="tpl_fp",
        run_config={"mode": "test"},
    )
    template_library = {
        "default": [
            TemplateLibraryItem(
                name="weak_template",
                expression="rank(ts_backfill({field}, {backfill_window}))",
                priority=9999,
                family="legacy_level",
                stage="first_order",
            )
        ]
    }
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        all_fields=[{"id": "sales", "type": "MATRIX"}],
        template_library=template_library,
        include_templates={"weak_template"},
        use_dataset_heuristics=False,
        expression_policy=None,
    )

    before_pending, before_disabled, before_count = build_pending_templates_for_field(
        build_ctx,
        {"id": "sales", "type": "MATRIX"},
        template_stats={},
        attempted_keys=set(),
        prior_results=[],
    )
    assert before_count >= 1
    assert len(before_pending) == 1
    assert before_disabled == 0

    existing_results = [
        FieldTestResult(
            field_id="field_a",
            field_type="MATRIX",
            field_name="field_a",
            template_name="weak_template",
            template_family="legacy_level",
            template_stage="first_order",
            expression="rank(ts_backfill(field_a, 240))",
            status="simulated",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.1),
                FailedCheck(name="LOW_FITNESS", value=0.2),
            ],
        )
    ]

    class _DoneFuture:
        def result(self) -> FieldTestResult:
            return FieldTestResult(
                field_id="field_b",
                field_type="MATRIX",
                field_name="field_b",
                template_name="weak_template",
                template_family="legacy_level",
                template_stage="first_order",
                expression="rank(ts_backfill(field_b, 240))",
                status="simulated",
                submittable=False,
                failed_checks=[
                    FailedCheck(name="LOW_SHARPE", value=0.1),
                    FailedCheck(name="LOW_FITNESS", value=0.2),
                ],
            )

    future = _DoneFuture()
    execution_state = ExecutionState(
        results=existing_results,
        attempted_keys=set(),
        template_stats={},
        pending_futures={
            future: PendingFutureContext(
                field_id="field_b",
                field_name="field_b",
                field_type="MATRIX",
                template_name="weak_template",
                template_family="legacy_level",
                template_stage="first_order",
                expression="rank(ts_backfill(field_b, 240))",
                settings_fingerprint="variant_fp",
            )
        },
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )
    handle_completed_future(
        future,
        completion_ctx=completion_ctx,
        execution_state=execution_state,
    )

    after_pending, after_disabled, after_count = build_pending_templates_for_field(
        build_ctx,
        {"id": "sales", "type": "MATRIX"},
        template_stats={},
        attempted_keys=set(),
        prior_results=[],
    )
    assert after_count >= 1
    assert after_pending == []
    assert after_disabled == 0
    assert _is_blacklisted_template(
        "weak_template",
        "rank(ts_backfill(sales, 240))",
        template_metadata={"family": "legacy_level", "stage": "first_order"},
        dataset_id="custom_ds",
    )


def test_fundamental6_template_library_has_family_and_layer_metadata() -> None:
    """Common dataset template library entries should carry explicit family/layer metadata."""
    template_file = Path(__file__).resolve().parents[2] / "data" / "templates" / "fundamental6" / "library.json"
    payload = json.loads(template_file.read_text(encoding="utf-8"))

    missing = []
    for section, items in payload.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or "name" not in item or "expression" not in item:
                continue
            if "family" not in item or "layer" not in item:
                missing.append((section, item["name"]))

    assert missing == []


def test_build_pending_templates_skips_inflight_duplicate(monkeypatch) -> None:
    settings_payload = {"neutralization": "SUBINDUSTRY", "truncation": 0.08}
    monkeypatch.setattr(
        "alpha.core.executor.build_setting_variants",
        lambda *args, **kwargs: [settings_payload],
    )
    monkeypatch.setattr(
        "alpha.core.executor.build_expression_candidates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "model51_market_zscore_decay_63",
                "ts_decay_linear(group_neutralize(ts_zscore(winsorize(ts_backfill(unsystematic_risk_last_360_days, 504), std=4), 63), market), 20)",
                1000,
                {"family": "neutralize_decay", "stage": "group_second_order"},
            )
        ],
    )
    args = Namespace(
        dataset_id="model51",
        template_disable_after=0,
        disable_legacy_after=0,
        max_templates_per_field=3,
        max_templates_per_family=1,
        legacy_similarity_penalty=0,
    )
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        all_fields=[
            {
                "id": "unsystematic_risk_last_360_days",
                "type": "MATRIX",
                "name": "unsystematic_risk_last_360_days",
            }
        ],
        template_library={},
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("model51"),
    )

    pending_futures = {
        object(): PendingFutureContext(
            field_id="unsystematic_risk_last_360_days",
            field_name="unsystematic_risk_last_360_days",
            field_type="MATRIX",
            template_name="model51_market_zscore_decay_63",
            template_family="neutralize_decay",
            template_stage="group_second_order",
            expression="ts_decay_linear(group_neutralize(ts_zscore(winsorize(ts_backfill(unsystematic_risk_last_360_days, 504), std=4), 63), market), 20)",
            settings_fingerprint=build_settings_fingerprint_from_payload(
                settings_payload
            ),
        )
    }

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {
            "id": "unsystematic_risk_last_360_days",
            "type": "MATRIX",
            "name": "unsystematic_risk_last_360_days",
        },
        template_stats={},
        attempted_keys=set(),
        prior_results=[],
        reserved_keys=inflight_template_keys(pending_futures),
    )

    assert total == 1
    assert disabled == 0
    assert pending == []


def test_fundamental6_template_library_removes_known_weak_short_window_templates() -> None:
    template_file = Path(__file__).resolve().parents[2] / "data" / "templates" / "fundamental6" / "library.json"
    payload = json.loads(template_file.read_text(encoding="utf-8"))

    names = {
        item["name"]
        for section, items in payload.items()
        if isinstance(items, list)
        for item in items
        if isinstance(item, dict) and "name" in item
    }

    removed = {
        "vol_scaled_delta_5_20",
        "vol_scaled_delta_5_20_MARKET",
        "delta_5",
        "rank_delta_5",
        "group_delta_5",
        "group_delta_5_MARKET",
        "vec_avg_vol_scaled_delta_20_60",
        "vec_avg_delta_5",
        "vec_avg_delta_20",
        "vec_avg_delta_21",
        "vec_avg_delta_22",
        "vec_avg_delta_66",
        "vec_avg_rank_delta_5",
        "mean_diff_5_20",
        "vec_avg_ts_corr_self_60",
        "vec_avg_zscore",
        "vec_avg_backfill",
        "vec_avg_rank",
        "vec_avg_ts_mean_20",
        "vec_avg_ts_mean_22",
        "vec_avg_ts_mean_60",
        "vec_avg_ts_mean_63",
        "vec_avg_ts_mean_66",
        "vec_avg_ts_mean_252",
        "vec_avg_scale",
    }

    assert names.isdisjoint(removed)


def test_blacklist_prefers_name_and_stage_over_name_only(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    blacklist_file = data_dir / "blacklists" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "blacklisted_templates": [
                    {
                        "name": "weak_template",
                        "template_stage": "group_second_order",
                        "template_family": "group_zscore",
                    }
                ],
                "auto_avoid_rules": [],
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


def test_legacy_blacklist_name_only_only_applies_without_runtime_metadata(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    blacklist_file = data_dir / "blacklists" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "blacklisted_templates": [{"name": "legacy_template"}],
                "auto_avoid_rules": [],
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


def test_resimulate_stage_prefers_refine_templates_over_broad_generation(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.core.executor.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )
    args = Namespace(
        dataset_id="fundamental6",
        template_disable_after=0,
        disable_legacy_after=0,
        max_templates_per_field=6,
        max_templates_per_family=3,
        legacy_similarity_penalty=0,
    )
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        all_fields=[{"id": "cash_st", "type": "MATRIX", "name": "cash_st"}],
        template_library={
            "default": [
                TemplateLibraryItem(
                    name="broad_template",
                    expression="rank(ts_backfill({field}, {backfill_window}))",
                    priority=9999,
                    family="legacy_level",
                    stage="first_order",
                )
            ]
        },
        field_feedback={
            "cash_st": {
                "field_name": "cash_st",
                "best_score": 0.30,
                "best_expression": "group_rank(ts_zscore(ts_backfill(cash_st, 504), 60), subindustry)",
                "best_template_name": "account_group_zscore_60_subindustry",
                "best_template_family": "group_zscore",
                "best_template_stage": "group_second_order",
                "attempted_templates": 4,
                "failed_check_counts": {"LOW_SHARPE": 1, "LOW_FITNESS": 1},
            }
        },
        use_dataset_heuristics=False,
    )
    prior_results = [
        FieldTestResult(
            field_id="cash_st",
            field_type="MATRIX",
            field_name="cash_st",
            template_name="account_group_zscore_60_subindustry",
            template_family="group_zscore",
            template_stage="group_second_order",
            status="simulated",
            submittable=False,
            expression="group_rank(ts_zscore(ts_backfill(cash_st, 504), 60), subindustry)",
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=1.21, limit=1.25),
                FailedCheck(name="LOW_FITNESS", value=0.64, limit=1.0),
            ],
        )
    ]

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {"id": "cash_st", "type": "MATRIX", "name": "cash_st"},
        template_stats={},
        attempted_keys=set(),
        prior_results=prior_results,
    )

    assert total > 0
    assert disabled == 0
    assert pending
    assert pending[0].template_name.startswith("refine_")
    assert all(entry.template_name != "broad_template" for entry in pending)


def test_event_field_uses_narrower_template_budget(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.core.executor.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )
    monkeypatch.setattr(
        "alpha.core.executor.build_expression_candidates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "vec_avg_ts_rank_63",
                "rank(ts_rank(vec_avg(x), 63))",
                100,
                {"family": "ts_rank", "stage": "first_order"},
            ),
            TemplateCandidate(
                "vec_avg_ts_zscore_63",
                "rank(ts_zscore(vec_avg(x), 63))",
                99,
                {"family": "zscore_time", "stage": "first_order"},
            ),
            TemplateCandidate(
                "vec_avg_decay_20",
                "rank(ts_decay_linear(vec_avg(x), 20))",
                98,
                {"family": "decay_level", "stage": "first_order"},
            ),
            TemplateCandidate(
                "iter_reuse_best_trade_when_volume_expansion",
                "trade_when(ts_mean(volume, 10) > ts_mean(volume, 60), rank(x), -1)",
                97,
                {"family": "event_trade_when", "stage": "event_conditioned"},
            ),
        ],
    )
    args = Namespace(
        dataset_id="fundamental6",
        template_disable_after=0,
        disable_legacy_after=0,
        max_templates_per_field=10,
        max_templates_per_family=3,
        legacy_similarity_penalty=0,
    )
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        all_fields=[{"id": "fnd6_cptnewqeventv110_apq", "type": "VECTOR", "name": "fnd6_cptnewqeventv110_apq"}],
        template_library={},
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, _disabled, total = build_pending_templates_for_field(
        build_ctx,
        {"id": "fnd6_cptnewqeventv110_apq", "type": "VECTOR", "name": "fnd6_cptnewqeventv110_apq"},
        template_stats={},
        attempted_keys=set(),
        prior_results=[],
    )

    assert total == 3
    assert len(pending) == 3


def test_blacklist_pattern_rules_support_exact_and_regex(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    blacklist_file = data_dir / "blacklists" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "blacklisted_templates": [],
                "auto_avoid_rules": [
                    {"type": "exact", "pattern": "rank(close)"},
                    {"type": "regex", "pattern": r"ts_delta\(.*?, 5\)"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()

    assert _is_blacklisted_template("t1", "rank(close)", dataset_id="custom_ds")
    assert _is_blacklisted_template("t2", "rank(ts_delta(close, 5))", dataset_id="custom_ds")
    assert not _is_blacklisted_template("t3", "rank(close) + 1", dataset_id="custom_ds")
