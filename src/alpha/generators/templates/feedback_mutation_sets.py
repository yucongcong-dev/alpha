"""Reusable feedback mutation template sets."""

from __future__ import annotations

from ...config import (
    TEMPLATE_STAGE_FIRST_ORDER,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
    DatasetExpressionPolicy,
)
from ...models.domain import TemplateCandidate
from .candidates import _candidate_metadata, _make_template_candidate
from .variation_common import is_blacklisted_template


def build_base_feedback_mutations(
    field_name: str,
    backfill_window: int,
    *,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> list[TemplateCandidate]:
    """Build baseline feedback mutations available during generate stage."""
    bw = backfill_window
    mutations: list[TemplateCandidate] = [
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
    for delta, std, pri in [(63, 126, 192), (63, 252, 190), (126, 252, 188), (252, 504, 186)]:
        name = f"iter_group_vol_scaled_delta_{delta}_{std}"
        expr = f"group_rank(ts_delta(ts_backfill({field_name}, {bw}), {delta}) / ts_std_dev(ts_backfill({field_name}, {bw}), {std}), subindustry)"
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

    for bf_window, pri in [(180, 184), (260, 182)]:
        name = f"iter_group_vol_scaled_delta_63_126_bf{bf_window}"
        expr = f"group_rank(ts_delta(ts_backfill({field_name}, {bf_window}), 63) / ts_std_dev(ts_backfill({field_name}, {bf_window}), 126), subindustry)"
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

    mutations.extend(
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
    return mutations


def build_nearpass_extension_mutations(
    field_name: str,
    backfill_window: int,
) -> list[TemplateCandidate]:
    """Build short-window near-pass extension mutations."""
    bw = backfill_window
    return [
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


def build_account_resimulation_mutations(
    field_name: str,
    backfill_window: int,
) -> list[TemplateCandidate]:
    """Build account-oriented mutations for promising account templates."""
    bw = backfill_window
    return [
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


def build_nearpass_vol_scaled_mutations(
    field_name: str,
    backfill_window: int,
    *,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> list[TemplateCandidate]:
    """Build vol-scaled mutations for high-scoring near-pass fields."""
    mutations: list[TemplateCandidate] = []
    for delta, std, bf, pri in [
        (63, 126, 180, 198),
        (63, 252, 180, 196),
        (126, 252, None, 195),
        (63, 126, None, 194),
        (126, 504, None, 193),
        (252, 504, None, 192),
        (63, 126, 260, 191),
    ]:
        bf_val = bf if bf is not None else backfill_window
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
    return mutations


def build_low_turnover_repair_mutations(
    field_name: str,
    backfill_window: int,
) -> list[TemplateCandidate]:
    """Build faster delta mutations when turnover is too low."""
    bw = backfill_window
    return [
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


def build_group_quality_repair_mutations(
    field_name: str,
    backfill_window: int,
) -> list[TemplateCandidate]:
    """Build group zscore mutations for sub-universe/concentration failures."""
    bw = backfill_window
    return [
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

