"""Run configuration snapshot tests."""

from __future__ import annotations

import sys

from alpha.cli.parser import parse_application_config
from alpha.cli.run_config import build_run_config_snapshot
from alpha.config.yaml import clear_yaml_caches


def test_run_config_snapshot_captures_research_inputs(monkeypatch, tmp_path) -> None:
    clear_yaml_caches()
    monkeypatch.chdir(tmp_path)
    filter_paths = {
        option: tmp_path / filename
        for option, filename in (
            ("--include-fields-file", "include-fields.txt"),
            ("--exclude-fields-file", "exclude-fields.txt"),
            ("--include-templates-file", "include-templates.txt"),
            ("--exclude-templates-file", "exclude-templates.txt"),
        )
    }
    for path in filter_paths.values():
        path.write_text("entry\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--dataset-id",
            "pv1",
            "--pasteurization",
            "OFF",
            "--unit-handling",
            "OFF",
            "--language",
            "FASTEXPR",
            "--start-date",
            "2021-01-01",
            "--end-date",
            "2024-12-31",
            "--backfill-window",
            "360",
            "--min-sharpe",
            "1.4",
            "--min-fitness",
            "1.1",
            "--min-turnover",
            "0.02",
            "--max-turnover",
            "0.6",
            "--max-weight",
            "0.08",
            *(value for option, path in filter_paths.items() for value in (option, str(path))),
        ],
    )

    config = parse_application_config()
    snapshot = build_run_config_snapshot(config, config.paths)

    assert snapshot["settings"] == {
        "decay": config.simulation.decay,
        "neutralization": config.simulation.neutralization,
        "truncation": config.simulation.truncation,
        "nan_handling": config.simulation.nan_handling,
        "pasteurization": "OFF",
        "unit_handling": "OFF",
        "max_trade": config.simulation.max_trade,
        "language": "FASTEXPR",
        "start_date": "2021-01-01",
        "end_date": "2024-12-31",
        "backfill_window": 360,
    }
    assert snapshot["quality"] == {
        "min_sharpe": 1.4,
        "min_fitness": 1.1,
        "min_turnover": 0.02,
        "max_turnover": 0.6,
        "max_weight": 0.08,
    }
    assert snapshot["filters"] == {
        "top_fields_by_feedback": config.planning.top_fields_by_feedback,
        "include_fields_file": str(filter_paths["--include-fields-file"]),
        "exclude_fields_file": str(filter_paths["--exclude-fields-file"]),
        "include_templates_file": str(filter_paths["--include-templates-file"]),
        "exclude_templates_file": str(filter_paths["--exclude-templates-file"]),
    }
    assert snapshot["config_source_chains"]["pasteurization"] == ["parser_default", "cli"]
