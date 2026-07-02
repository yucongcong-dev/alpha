"""
配置数据模型。

本模块集中定义表达式策略、字段预处理和反馈闭环相关 dataclass。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldTransformStage:
    """字段预处理单个 stage 的配置。"""

    kind: str
    window: int = 0
    std: float | None = None


@dataclass(frozen=True)
class FieldTransformSpec:
    """字段预处理流水线配置。"""

    stages: tuple[FieldTransformStage, ...] = ()
    backfill_window: int = 0
    winsorize_std: float | None = None


@dataclass(frozen=True)
class FeedbackPhasePolicy:
    """单个 feedback 阶段的预算与门槛。"""

    min_attempted_templates: int = 0
    min_best_score: float = -999.0
    settings_variant_budget: int = 3
    enable_template_pruning: bool = False
    enable_resimulation_mutations: bool = False
    preferred_template_stages: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeedbackLoopPolicy:
    """表达式搜索反馈闭环：generate -> prune -> resimulate。"""

    generate: FeedbackPhasePolicy = field(default_factory=FeedbackPhasePolicy)
    prune: FeedbackPhasePolicy = field(default_factory=FeedbackPhasePolicy)
    resimulate: FeedbackPhasePolicy = field(default_factory=FeedbackPhasePolicy)


@dataclass(frozen=True)
class DatasetExpressionPolicy:
    """数据集表达式生成策略。"""

    dataset_id: str = ""
    use_curated_heuristics: bool = False
    partner_limit: int = 4
    account_template_boost: int = 0
    high_conviction_ratio_priority_boost: int = 0
    disabled_templates: set[str] = field(default_factory=set)
    protected_templates: set[str] = field(default_factory=set)
    high_conviction_ratio_pairs: set[tuple[str, str]] = field(default_factory=set)
    template_priority_penalties: dict[str, int] = field(default_factory=dict)
    template_prefix_penalties: dict[tuple[str, ...], int] = field(default_factory=dict)
    matrix_delta_over_std_windows: tuple[tuple[int, int, int], ...] = ()
    matrix_diversified_template_specs: tuple[tuple[str, str, int], ...] = ()
    ratio_delta_rank_windows: tuple[tuple[int, int], ...] = ()
    ratio_delta_over_std_windows: tuple[tuple[int, int, int], ...] = ()
    ratio_diversified_template_specs: tuple[tuple[str, str, int], ...] = ()
    ratio_legacy_template_specs: tuple[tuple[str, str, int], ...] = ()
    positive_raw_fields: set[str] = field(default_factory=set)
    negative_raw_fields: set[str] = field(default_factory=set)
    blacklisted_template_name_substrings: tuple[str, ...] = ()
    ratio_partner_candidates: dict[str, tuple[str, ...]] = field(default_factory=dict)
    ratio_keywords: dict[str, tuple[str, ...]] = field(default_factory=dict)
    preferred_partner_score_bonuses: dict[str, int] = field(default_factory=dict)
    preferred_field_order: dict[str, int] = field(default_factory=dict)
    overtested_weak_fields: set[str] = field(default_factory=set)
    promising_field_min_priority: float = 0.65
    always_keep_families: set[str] = field(default_factory=set)
    slow_template_prefixes: tuple[str, ...] = ()
    slow_template_names: set[str] = field(default_factory=set)
    concentrated_weak_families: set[str] = field(default_factory=set)
    concentrated_weak_prefixes: tuple[str, ...] = ()
    concentrated_weak_names: set[str] = field(default_factory=set)
    low_sharpe_weak_ratio_families: set[str] = field(default_factory=set)
    low_sharpe_weak_ratio_prefixes: tuple[str, ...] = ()
    weak_mean_spread_fields: set[str] = field(default_factory=set)
    broken_zscore_spread_fields: set[str] = field(default_factory=set)
    weak_ratio_standalone_fields: set[str] = field(default_factory=set)
    low_sharpe_ratio_fail_threshold: int = 0
    blacklist_min_fields_for_nearpass: int = 0
    blacklist_protected_min_avg_sharpe: float = 0.0
    blacklist_protected_min_avg_fitness: float = 0.0
    field_min_coverage: float = 0.0
    field_min_date_coverage: float = 0.0
    field_min_alpha_count: int = 0
    field_min_user_count: int = 0
    field_coverage_weight: float = 0.0
    field_date_coverage_weight: float = 0.0
    field_alpha_validation_weight: float = 0.0
    field_user_validation_weight: float = 0.0
    field_alpha_crowding_penalty_weight: float = 0.0
    field_user_crowding_penalty_weight: float = 0.0
    field_recency_weight: float = 0.0
    field_theme_bonus_weight: float = 0.0
    field_preferred_unexplored_bonus: float = 0.0
    event_field_prefixes: tuple[str, ...] = ()
    event_field_min_coverage: float = 0.0
    event_field_min_date_coverage: float = 0.0
    event_field_min_alpha_count: int = 0
    event_field_min_user_count: int = 0
    event_max_templates_per_field: int = 0
    event_max_templates_per_family: int = 0
    event_allowed_template_stages: tuple[str, ...] = ()
    event_allowed_template_prefixes: tuple[str, ...] = ()
    event_allowed_template_families: set[str] = field(default_factory=set)
    default_field_transform: FieldTransformSpec = field(default_factory=FieldTransformSpec)
    matrix_field_transform: FieldTransformSpec = field(default_factory=FieldTransformSpec)
    vector_field_transform: FieldTransformSpec = field(default_factory=FieldTransformSpec)
    ratio_numerator_transform: FieldTransformSpec = field(default_factory=FieldTransformSpec)
    ratio_denominator_transform: FieldTransformSpec = field(default_factory=FieldTransformSpec)
    feedback_loop_policy: FeedbackLoopPolicy = field(default_factory=FeedbackLoopPolicy)
