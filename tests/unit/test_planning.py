"""Read-only dry-run planning tests."""

from __future__ import annotations

from types import SimpleNamespace

from alpha.app.planning import run_dry_run_plan
from alpha.config.application import ApplicationConfig
from alpha.config.models import DatasetExpressionPolicy
from alpha.models.domain import TemplateField
from alpha.models.io_types import RunFilters, RunPaths
from alpha.runtime.contexts import HistoricalRunState


def _paths(tmp_path) -> RunPaths:
    return RunPaths(
        results_dir=str(tmp_path / "results"),
        log_file=str(tmp_path / "run.log"),
        state_file=str(tmp_path / "state.json"),
        checkpoint_file=str(tmp_path / "checkpoint.json"),
        datasets_root=str(tmp_path / "datasets"),
        fields_cache_file=str(tmp_path / "fields.json"),
        template_library_file=str(tmp_path / "library.json"),
        output=str(tmp_path / "output.json"),
        feedback_output=str(tmp_path / "feedback.json"),
    )


def _config(paths: RunPaths) -> ApplicationConfig:
    args = SimpleNamespace(
        output=paths.output,
        template_library_file=paths.template_library_file,
        fields_cache_file=paths.fields_cache_file,
        creds_file="",
        creds_key_file="",
        include_fields_file="",
        exclude_fields_file="",
        include_templates_file="",
        exclude_templates_file="",
        dataset_id="fundamental6",
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
        backfill_window=504,
        page_size=50,
    )
    return ApplicationConfig.from_args(args, paths)


def _patch_local_resources(monkeypatch, historical_state: HistoricalRunState) -> None:
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.ensure_dataset_template_library",
        lambda path, _dataset_id: path,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.load_template_library",
        lambda _path, **_kwargs: {},
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.load_run_filters_extended",
        lambda _paths: RunFilters(),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.get_dataset_expression_policy",
        lambda _dataset_id, **_kwargs: DatasetExpressionPolicy(dataset_id="fundamental6"),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.build_historical_run_state",
        lambda *_args, **_kwargs: historical_state,
    )


def test_dry_run_plan_uses_local_cache_without_runtime_writes(monkeypatch, tmp_path) -> None:
    paths = _paths(tmp_path)
    args = _config(paths)
    historical_state = HistoricalRunState()
    captured: dict[str, object] = {}
    _patch_local_resources(monkeypatch, historical_state)

    def _load_history(output_path, feedback_path, *, repair_corrupt_summary):
        captured["history_paths"] = (output_path, feedback_path)
        captured["repair_corrupt_summary"] = repair_corrupt_summary
        return historical_state

    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.build_historical_run_state", _load_history
    )

    def _load_cache(cache_path, **kwargs):
        captured["cache_path"] = cache_path
        captured["cache_ttl_hours"] = kwargs["cache_ttl_hours"]
        return [TemplateField("field_1", "field_1", "MATRIX")]

    monkeypatch.setattr("alpha.app.planning.load_fields_cache", _load_cache)
    monkeypatch.setattr(
        "alpha.app.planning.prepare_fields_for_execution",
        lambda fields, **_kwargs: (fields, {}),
    )
    execution_state = SimpleNamespace(
        results=[], attempted_keys=set(), skipped_fields_due_to_queue=set()
    )
    monkeypatch.setattr(
        "alpha.app.planning.create_execution_state",
        lambda **_kwargs: execution_state,
    )
    monkeypatch.setattr(
        "alpha.app.planning.print_dry_run_plan",
        lambda **kwargs: captured.update(planned_fields=kwargs["fields"]),
    )

    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    assert run_dry_run_plan(args) is True
    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

    assert before == after
    assert captured["cache_path"] == paths.fields_cache_file
    assert captured["cache_ttl_hours"] == 0
    assert captured["repair_corrupt_summary"] is False
    assert captured["planned_fields"] == [TemplateField("field_1", "field_1", "MATRIX")]


def test_dry_run_plan_fails_without_matching_local_cache(monkeypatch, tmp_path) -> None:
    paths = _paths(tmp_path)
    args = _config(paths)
    _patch_local_resources(monkeypatch, HistoricalRunState())
    monkeypatch.setattr("alpha.app.planning.load_fields_cache", lambda *_args, **_kwargs: [])

    assert run_dry_run_plan(args) is False
