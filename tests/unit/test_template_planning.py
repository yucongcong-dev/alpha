"""Template planning service assembly tests."""

from __future__ import annotations

import alpha.core.executor as executor
import alpha.core.template_planning as template_planning


def test_executor_planning_services_read_current_module_dependencies(monkeypatch) -> None:
    """Executor-level monkeypatch/plugin overrides should remain late-bound."""

    def variants(*_args, **_kwargs):
        return []

    monkeypatch.setattr(executor, "build_setting_variants", variants)

    services = executor.build_executor_template_planning_services()

    assert services.build_setting_variants is variants
    assert services.build_expression_candidates is executor.build_expression_candidates


def test_low_level_planning_services_read_current_module_dependencies(monkeypatch) -> None:
    """Direct low-level callers should receive the same late-binding behavior."""

    def refine(*_args, **_kwargs):
        return []

    monkeypatch.setattr(template_planning, "build_refine_templates", refine)

    services = template_planning.build_template_planning_services()

    assert services.build_refine_templates is refine
    assert (
        services.build_settings_fingerprint
        is template_planning.build_settings_fingerprint_from_payload
    )
