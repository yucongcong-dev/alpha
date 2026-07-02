"""Best-expression feedback mutation templates."""

from __future__ import annotations

from ...config import (
    FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
    TEMPLATE_STAGE_FIRST_ORDER,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
)
from ...models.base import TemplateCandidate
from .candidates import _candidate_metadata, _make_template_candidate
from .wrappers import invert_expression


def build_best_expression_mutations(
    best_expression: str,
    best_score: float,
    backfill_window: int,
) -> list[TemplateCandidate]:
    """Build mutations around the best historical expression."""
    bw = backfill_window
    mutations = [
        _make_template_candidate(
            "iter_flip_best",
            invert_expression(best_expression),
            172,
            metadata=_candidate_metadata(stage=TEMPLATE_STAGE_FIRST_ORDER),
        ),
        _make_template_candidate(
            "iter_group_flip_best",
            f"group_rank({invert_expression(best_expression)}, subindustry)",
            174,
            metadata=_candidate_metadata(layer="group", stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER),
        ),
        _make_template_candidate(
            "iter_group_decay_best_5",
            f"group_rank(ts_decay_linear(ts_backfill({best_expression}, {bw}), 5), subindustry)",
            170,
            metadata=_candidate_metadata(
                family="neutralize_decay",
                layer="group",
                stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
            ),
        ),
    ]
    if best_score < FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD:
        return mutations

    for window in (3, 5, 10):
        mutations.extend(
            [
                _make_template_candidate(
                    f"iter_nearpass_delta_best_{window}",
                    f"rank(ts_delta({best_expression}, {window}))",
                    188 - window,
                    metadata=_candidate_metadata(
                        family="rank_delta",
                        layer="signal",
                        stage=TEMPLATE_STAGE_FIRST_ORDER,
                    ),
                ),
                _make_template_candidate(
                    f"iter_nearpass_group_delta_best_{window}",
                    f"group_rank(ts_delta({best_expression}, {window}), subindustry)",
                    192 - window,
                    metadata=_candidate_metadata(
                        family="group_rank_delta",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
            ]
        )
    mutations.extend(
        [
            _make_template_candidate(
                f"iter_nearpass_decay_best_{decay}",
                f"rank(ts_decay_linear({best_expression}, {decay}))",
                184 - decay,
                metadata=_candidate_metadata(
                    family="decay_level",
                    layer="signal",
                    stage=TEMPLATE_STAGE_FIRST_ORDER,
                ),
            )
            for decay in (3, 5, 8)
        ]
    )
    return mutations
