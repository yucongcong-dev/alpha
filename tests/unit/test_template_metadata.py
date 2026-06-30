from __future__ import annotations

from alpha.generators.expressions import (
    apply_similarity_penalty,
    cap_templates_per_family,
    classify_expression_family,
)


def test_classify_expression_family_prefers_explicit_metadata() -> None:
    family = classify_expression_family(
        "custom_template",
        "rank(ts_delta(close, 5))",
        {"family": "stable_value"},
    )

    assert family == "stable_value"


def test_similarity_penalty_uses_metadata_family() -> None:
    templates = [("custom_template", "rank(close)", 100)]
    penalized = apply_similarity_penalty(
        templates,
        legacy_similarity_penalty=30,
        metadata_by_key={("custom_template", "rank(close)"): {"family": "legacy_ratio"}},
    )

    assert penalized[0][2] == 80


def test_cap_templates_per_family_uses_metadata_family() -> None:
    templates = [
        ("template_a", "expr_a", 100),
        ("template_b", "expr_b", 90),
        ("template_c", "expr_c", 80),
    ]
    capped = cap_templates_per_family(
        templates,
        max_templates_per_family=2,
        metadata_by_key={
            ("template_a", "expr_a"): {"family": "quality"},
            ("template_b", "expr_b"): {"family": "quality"},
            ("template_c", "expr_c"): {"family": "quality"},
        },
    )

    assert [name for name, _, _ in capped] == ["template_a", "template_b"]
