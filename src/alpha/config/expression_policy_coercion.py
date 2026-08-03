"""Coercion helpers for expression-policy YAML overrides."""

from __future__ import annotations

from typing import Any

from .expression_policy_schema import (
    EXPRESSION_POLICY_DICT_INT_FIELDS,
    EXPRESSION_POLICY_DICT_TUPLE_FIELDS,
    EXPRESSION_POLICY_FEEDBACK_LOOP_FIELD,
    EXPRESSION_POLICY_INT_FIELDS,
    EXPRESSION_POLICY_SET_FIELDS,
    EXPRESSION_POLICY_TEMPLATE_PREFIX_PENALTIES_FIELD,
    EXPRESSION_POLICY_TEMPLATE_SPEC_FIELDS,
    EXPRESSION_POLICY_TRANSFORM_FIELDS,
    EXPRESSION_POLICY_TUPLE_FIELDS,
    EXPRESSION_POLICY_TUPLE_PAIR_FIELDS,
    EXPRESSION_POLICY_TUPLE_WINDOW2_FIELDS,
    EXPRESSION_POLICY_TUPLE_WINDOW3_FIELDS,
)
from .policy_coercers import (
    coerce_feedback_loop_policy,
    coerce_field_transform_spec,
    coerce_template_prefix_penalties,
    resolve_tier_value,
    tuple_tuple_int,
    tuple_tuple_str_int,
)


def coerce_expression_policy_override(
    key: str,
    value: object,
    *,
    tiers: dict[str, int],
) -> tuple[bool, Any]:
    """Coerce one supported expression-policy override value.

    Returns ``(False, None)`` when the previous inline parser would skip the
    field because coercion failed.
    """
    if key in EXPRESSION_POLICY_SET_FIELDS and isinstance(value, (list, tuple, set)):
        return True, {str(item) for item in value}
    if key in EXPRESSION_POLICY_TUPLE_FIELDS and isinstance(value, (list, tuple)):
        return True, tuple(str(item) for item in value)
    if key in EXPRESSION_POLICY_DICT_TUPLE_FIELDS and isinstance(value, dict):
        return True, {
            str(name): tuple(str(item) for item in items)
            for name, items in value.items()
            if isinstance(items, (list, tuple))
        }
    if key in EXPRESSION_POLICY_DICT_INT_FIELDS and isinstance(value, dict):
        coerced: dict[Any, int] = {}
        for name, score in value.items():
            resolved = resolve_tier_value(score, tiers)
            if resolved is not None:
                coerced[name] = resolved
        return True, coerced
    if key == EXPRESSION_POLICY_TEMPLATE_PREFIX_PENALTIES_FIELD:
        return True, coerce_template_prefix_penalties(value, tiers=tiers)
    if key in EXPRESSION_POLICY_INT_FIELDS:
        resolved = resolve_tier_value(value, tiers)
        return (True, resolved) if resolved is not None else (False, None)
    if key in EXPRESSION_POLICY_TUPLE_PAIR_FIELDS and isinstance(value, (list, tuple)):
        return True, {
            (str(item[0]), str(item[1]))
            for item in value
            if isinstance(item, (list, tuple)) and len(item) == 2
        }
    if key in EXPRESSION_POLICY_TUPLE_WINDOW3_FIELDS:
        return True, tuple_tuple_int(value, 3)
    if key in EXPRESSION_POLICY_TUPLE_WINDOW2_FIELDS:
        return True, tuple_tuple_int(value, 2)
    if key in EXPRESSION_POLICY_TEMPLATE_SPEC_FIELDS:
        return True, tuple_tuple_str_int(value)
    if key in EXPRESSION_POLICY_TRANSFORM_FIELDS:
        transform = coerce_field_transform_spec(value)
        return (True, transform) if transform is not None else (False, None)
    if key == EXPRESSION_POLICY_FEEDBACK_LOOP_FIELD:
        loop_policy = coerce_feedback_loop_policy(value)
        return (True, loop_policy) if loop_policy is not None else (False, None)
    return True, value
