"""Feedback-driven mutation strategies."""

from __future__ import annotations

from typing import Any

from ...config import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    CHECK_LOW_TURNOVER,
    EXPR_MUTATION_EXTEND_THRESHOLD,
    EXPR_NEARPASS_BOOST_THRESHOLD,
    FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
    FEEDBACK_STAGE_GENERATE,
    FEEDBACK_STAGE_RESIMULATE,
    STATS_DEFAULT_SCORE,
    TEMPLATE_STAGE_FIRST_ORDER,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
    DatasetExpressionPolicy,
    get_backfill_window,
)
from ...models.base import TemplateCandidate
from .candidates import _candidate_metadata, _make_template_candidate
from .historical_reuse import build_historical_reuse_templates
from .priority import dominant_failed_check_names
from .variation_common import is_blacklisted_template
from .wrappers import invert_expression


def build_feedback_mutations(
    field_name: str,
    field_feedback: dict[str, Any] | None,
    *,
    expression_policy: DatasetExpressionPolicy | None = None,
    feedback_stage: str = FEEDBACK_STAGE_GENERATE,
) -> list[TemplateCandidate]:
    """Build mutations from field feedback and best-known expressions."""
    bw = get_backfill_window()
    vol_scaled_windows: list[tuple[int, int, int]] = [
        (63, 126, 192),
        (63, 252, 190),
        (126, 252, 188),
        (252, 504, 186),
    ]
    base_mutations: list[TemplateCandidate] = [
        _make_template_candidate(
            "iter_group_rank_delta_of_rank_63",
            f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 63), subindustry)",
            184,
            metadata=_candidate_metadata(
                family="group_rank_delta",
                layer="group",
                stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
            ),
        ),
        _make_template_candidate(
            "iter_group_rank_delta_of_rank_126",
            f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 126), subindustry)",
            182,
            metadata=_candidate_metadata(
                family="group_rank_delta",
                layer="group",
                stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
            ),
        ),
    ]

    for delta, std, pri in vol_scaled_windows:
        name = f"iter_group_vol_scaled_delta_{delta}_{std}"
        expr = f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), {delta}) / ts_std_dev(ts_backfill({field_name}, {bw}), {std}), subindustry)"
        if not is_blacklisted_template(name, expr, policy=expression_policy):
            base_mutations.append(
                _make_template_candidate(
                    name,
                    expr,
                    pri,
                    metadata=_candidate_metadata(
                        family="group_vol_scaled_delta",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                )
            )

    for bf_window, pri in [(180, 184), (260, 182)]:
        name = f"iter_group_vol_scaled_delta_63_126_bf{bf_window}"
        expr = f"group_rank(ts_delta(ts_backfill({field_name}, {bf_window}), 63) / ts_std_dev(ts_backfill({field_name}, {bf_window}), 126), subindustry)"
        if not is_blacklisted_template(name, expr, policy=expression_policy):
            base_mutations.append(
                _make_template_candidate(
                    name,
                    expr,
                    pri,
                    metadata=_candidate_metadata(
                        family="group_vol_scaled_delta",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                )
            )

    base_mutations.extend(
        [
            _make_template_candidate(
                "iter_group_mean_spread_over_std_63_240_126",
                f"group_rank((ts_mean(ts_backfill({field_name}, {bw}), 63) - ts_mean(ts_backfill({field_name}, {bw}), {bw})) / ts_std_dev(ts_backfill({field_name}, {bw}), 126), subindustry)",
                178,
                metadata=_candidate_metadata(
                    family="group_mean_spread",
                    layer="group",
                    stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                ),
            ),
            _make_template_candidate(
                "iter_rank_mean_spread_over_std_63_240_126",
                f"rank((ts_mean(ts_backfill({field_name}, {bw}), 63) - ts_mean(ts_backfill({field_name}, {bw}), {bw})) / ts_std_dev(ts_backfill({field_name}, {bw}), 126))",
                176,
                metadata=_candidate_metadata(
                    family="mean_spread",
                    layer="signal",
                    stage=TEMPLATE_STAGE_FIRST_ORDER,
                ),
            ),
        ]
    )

    if not field_feedback:
        return base_mutations if feedback_stage == FEEDBACK_STAGE_GENERATE else []

    mutations = list(base_mutations)
    failed_counts = field_feedback.get("failed_check_counts", {})
    dominant_names = dominant_failed_check_names(failed_counts, limit=3)
    best_expression = str(field_feedback.get("best_expression", "")).strip()
    best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE))

    if feedback_stage == FEEDBACK_STAGE_RESIMULATE and best_score >= EXPR_MUTATION_EXTEND_THRESHOLD:
        mutations.extend(
            [
                _make_template_candidate(
                    "iter_nearpass_group_rank_delta_of_rank_10",
                    f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 10), subindustry)",
                    194,
                    metadata=_candidate_metadata(
                        family="group_rank_delta",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
                _make_template_candidate(
                    "iter_nearpass_group_rank_delta_of_rank_20",
                    f"group_rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 20), subindustry)",
                    190,
                    metadata=_candidate_metadata(
                        family="group_rank_delta",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
                _make_template_candidate(
                    "iter_nearpass_group_delta_zscore_5_60",
                    f"group_rank(ts_delta(ts_zscore(ts_backfill({field_name}, {bw}), 60), 5), subindustry)",
                    188,
                    metadata=_candidate_metadata(
                        family="group_rank_delta",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
                _make_template_candidate(
                    "iter_nearpass_group_delta_zscore_10_60",
                    f"group_rank(ts_delta(ts_zscore(ts_backfill({field_name}, {bw}), 60), 10), subindustry)",
                    186,
                    metadata=_candidate_metadata(
                        family="group_rank_delta",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
            ]
        )

    best_template_name = str(field_feedback.get("best_template_name", "")).strip()
    if feedback_stage == FEEDBACK_STAGE_RESIMULATE and (
        best_template_name in {"account_rank_backfill_504", "account_ir_60"} or best_score >= 0.45
    ):
        mutations.extend(
            [
                _make_template_candidate(
                    "iter_account_group_backfill_504_subindustry",
                    f"group_rank(ts_backfill({field_name}, {bw}), subindustry)",
                    201,
                    metadata=_candidate_metadata(
                        family="legacy_group_level",
                        layer="account",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
                _make_template_candidate(
                    "iter_account_backfill_zscore_decay_63_subindustry",
                    f"group_rank(ts_decay_linear(ts_zscore(ts_backfill({field_name}, {bw}), 63), 20), subindustry)",
                    199,
                    metadata=_candidate_metadata(
                        family="group_zscore",
                        layer="account",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
                _make_template_candidate(
                    "iter_account_ir_60_decay_20",
                    f"rank(ts_decay_linear(ts_mean({field_name}, 60) / ts_std_dev({field_name}, 60), 20))",
                    197,
                    metadata=_candidate_metadata(
                        family="decay_level",
                        layer="account",
                        stage=TEMPLATE_STAGE_FIRST_ORDER,
                    ),
                ),
                _make_template_candidate(
                    "iter_account_group_ir_60_subindustry",
                    f"group_rank(ts_mean({field_name}, 60) / ts_std_dev({field_name}, 60), subindustry)",
                    195,
                    metadata=_candidate_metadata(
                        family="legacy_group_level",
                        layer="account",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
            ]
        )

    if feedback_stage == FEEDBACK_STAGE_RESIMULATE and best_score >= EXPR_NEARPASS_BOOST_THRESHOLD:
        nearpass_vol_scaled_configs: list[tuple[int, int, int | None, int]] = [
            (63, 126, 180, 198),
            (63, 252, 180, 196),
            (126, 252, None, 195),
            (63, 126, None, 194),
            (126, 504, None, 193),
            (252, 504, None, 192),
            (63, 126, 260, 191),
        ]
        for delta, std, bf, pri in nearpass_vol_scaled_configs:
            bf_val = bf if bf is not None else bw
            bf_suffix = f"_bf{bf_val}" if bf is not None else ""
            name = f"iter_nearpass_vol_scaled_{delta}_{std}{bf_suffix}"
            expr = f"group_rank(ts_delta(ts_backfill({field_name}, {bf_val}), {delta}) / ts_std_dev(ts_backfill({field_name}, {bf_val}), {std}), subindustry)"
            if not is_blacklisted_template(name, expr, policy=expression_policy):
                mutations.append(
                    _make_template_candidate(
                        name,
                        expr,
                        pri,
                        metadata=_candidate_metadata(
                            family="group_vol_scaled_delta",
                            layer="group",
                            stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                        ),
                    )
                )

    if feedback_stage != FEEDBACK_STAGE_GENERATE and CHECK_LOW_TURNOVER in dominant_names:
        mutations.extend(
            [
                _make_template_candidate(
                    "iter_rank_delta_3",
                    f"rank(ts_delta(ts_backfill({field_name}, {bw}), 3))",
                    186,
                    metadata=_candidate_metadata(
                        family="rank_delta",
                        layer="signal",
                        stage=TEMPLATE_STAGE_FIRST_ORDER,
                    ),
                ),
                _make_template_candidate(
                    "iter_rank_delta_5",
                    f"rank(ts_delta(ts_backfill({field_name}, {bw}), 5))",
                    184,
                    metadata=_candidate_metadata(
                        family="rank_delta",
                        layer="signal",
                        stage=TEMPLATE_STAGE_FIRST_ORDER,
                    ),
                ),
                _make_template_candidate(
                    "iter_rank_then_delta_3",
                    f"rank(ts_delta(rank(ts_backfill({field_name}, {bw})), 3))",
                    183,
                    metadata=_candidate_metadata(
                        family="rank_delta",
                        layer="signal",
                        stage=TEMPLATE_STAGE_FIRST_ORDER,
                    ),
                ),
            ]
        )

    if feedback_stage != FEEDBACK_STAGE_GENERATE and (
        CHECK_LOW_SUB_UNIVERSE_SHARPE in dominant_names
        or CHECK_CONCENTRATED_WEIGHT in dominant_names
    ):
        mutations.extend(
            [
                _make_template_candidate(
                    "iter_group_zscore_20",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, {bw}), 20), subindustry)",
                    185,
                    metadata=_candidate_metadata(
                        family="group_zscore",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
                _make_template_candidate(
                    "iter_group_zscore_spread_5_20",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, {bw}), 5) - ts_zscore(ts_backfill({field_name}, {bw}), 20), subindustry)",
                    183,
                    metadata=_candidate_metadata(
                        family="group_zscore",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
                ),
            ]
        )

    if feedback_stage == FEEDBACK_STAGE_RESIMULATE and best_expression:
        mutations.extend(
            [
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
                    metadata=_candidate_metadata(
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    ),
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
        )
        if best_score >= FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD:
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

    mutations.extend(
        build_historical_reuse_templates(
            field_name,
            field_feedback,
            feedback_stage=feedback_stage,
            expression_policy=expression_policy,
        )
    )
    return mutations
