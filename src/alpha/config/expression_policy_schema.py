"""Expression-policy YAML override key groups."""

from __future__ import annotations

EXPRESSION_POLICY_META_FIELDS = {"priority_tiers"}

EXPRESSION_POLICY_SET_FIELDS = {
    "protected_templates",
    "supported_grouping_fields",
    "positive_raw_fields",
    "negative_raw_fields",
    "event_allowed_template_families",
}

EXPRESSION_POLICY_TUPLE_FIELDS = {
    "event_field_prefixes",
    "event_allowed_template_stages",
    "event_allowed_template_prefixes",
}

EXPRESSION_POLICY_DICT_TUPLE_FIELDS = {"ratio_partner_candidates", "ratio_keywords"}

EXPRESSION_POLICY_DICT_INT_FIELDS = {
    "template_priority_penalties",
    "preferred_partner_score_bonuses",
    "preferred_field_order",
    "preferred_field_type_order",
}

EXPRESSION_POLICY_INT_FIELDS = {
    "account_template_boost",
    "high_conviction_ratio_priority_boost",
    "partner_limit",
    "field_feedback_half_life_days",
    "field_feedback_min_attempts_for_promising",
}

EXPRESSION_POLICY_TUPLE_PAIR_FIELDS = {"high_conviction_ratio_pairs"}

EXPRESSION_POLICY_TUPLE_WINDOW3_FIELDS = {
    "matrix_delta_over_std_windows",
    "ratio_delta_over_std_windows",
}

EXPRESSION_POLICY_TUPLE_WINDOW2_FIELDS = {"ratio_delta_rank_windows"}

EXPRESSION_POLICY_TEMPLATE_SPEC_FIELDS = {
    "matrix_diversified_template_specs",
    "ratio_diversified_template_specs",
    "ratio_legacy_template_specs",
}

EXPRESSION_POLICY_TRANSFORM_FIELDS = {
    "default_field_transform",
    "matrix_field_transform",
    "vector_field_transform",
    "ratio_numerator_transform",
    "ratio_denominator_transform",
}

EXPRESSION_POLICY_FEEDBACK_LOOP_FIELD = "feedback_loop_policy"
EXPRESSION_POLICY_TEMPLATE_PREFIX_PENALTIES_FIELD = "template_prefix_penalties"

EXPRESSION_POLICY_TYPED_OVERRIDE_FIELDS = (
    EXPRESSION_POLICY_SET_FIELDS
    | EXPRESSION_POLICY_TUPLE_FIELDS
    | EXPRESSION_POLICY_DICT_TUPLE_FIELDS
    | EXPRESSION_POLICY_DICT_INT_FIELDS
    | EXPRESSION_POLICY_INT_FIELDS
    | EXPRESSION_POLICY_TUPLE_PAIR_FIELDS
    | EXPRESSION_POLICY_TUPLE_WINDOW3_FIELDS
    | EXPRESSION_POLICY_TUPLE_WINDOW2_FIELDS
    | EXPRESSION_POLICY_TEMPLATE_SPEC_FIELDS
    | EXPRESSION_POLICY_TRANSFORM_FIELDS
    | {
        EXPRESSION_POLICY_FEEDBACK_LOOP_FIELD,
        EXPRESSION_POLICY_TEMPLATE_PREFIX_PENALTIES_FIELD,
    }
)
