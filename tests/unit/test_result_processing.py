"""Typed result-processing service assembly tests."""

from __future__ import annotations

import alpha.analysis.results_persistence as results_persistence
import alpha.core.result_processing as result_processing


def test_build_result_processing_services_reads_current_dependencies(monkeypatch) -> None:
    """Late test/plugin overrides should be captured for each processing call."""

    def informative(_result) -> bool:
        return False

    def writer(*_args, **_kwargs) -> int:
        return 7

    monkeypatch.setattr(result_processing, "is_informative_result", informative)
    monkeypatch.setattr(results_persistence, "dump_results_incremental", writer)

    services = result_processing.build_result_processing_services()

    assert services.is_informative_result is informative
    assert services.dump_results_incremental is writer
    assert services.result_identity is result_processing.result_identity
