"""Wrapper-style template variations."""

from __future__ import annotations

from ...config import TEMPLATE_STAGE_EVENT_CONDITIONED, TEMPLATE_STAGE_GROUP_SECOND_ORDER
from ...models.base import TemplateCandidate
from .candidates import _candidate_metadata, _make_template_candidate

_BUCKET_GROUP_SPECS: tuple[tuple[str, str, int], ...] = (
    ("cap_bucket", "bucket(rank(cap), range='0.1, 1, 0.1')", 174),
    ("asset_bucket", "bucket(rank(assets), range='0.1, 1, 0.1')", 172),
    ("volatility_bucket", "bucket(rank(ts_std_dev(returns, 20)), range='0.1, 1, 0.1')", 170),
    ("liquidity_bucket", "bucket(rank(close * volume), range='0.1, 1, 0.1')", 168),
)

_TRADE_WHEN_EVENT_SPECS: tuple[tuple[str, str, int], ...] = (
    ("volume_expansion", "ts_mean(volume, 10) > ts_mean(volume, 60)", 166),
    ("price_breakout_20", "ts_arg_max(close, 20) == 0", 164),
    ("return_zscore_high", "ts_zscore(returns, 60) > 2", 162),
    ("high_volatility_sector", "group_rank(ts_std_dev(returns, 60), sector) > 0.7", 160),
)


def invert_expression(expression: str) -> str:
    """Flip the sign of an expression."""
    if expression.startswith("-"):
        return expression[1:]
    return f"-{expression}"


def build_bucket_group_templates(
    expression: str,
    *,
    name_prefix: str,
    priority_offset: int = 0,
) -> list[TemplateCandidate]:
    """Build bucket-group wrappers around an expression."""
    templates: list[TemplateCandidate] = []
    for group_label, group_expr, priority in _BUCKET_GROUP_SPECS:
        name = f"{name_prefix}_bucket_group_rank_{group_label}"
        expr = f"group_rank({expression}, densify({group_expr}))"
        templates.append(
            _make_template_candidate(
                name,
                expr,
                priority + priority_offset,
                metadata=_candidate_metadata(
                    family="bucket_group_rank",
                    layer="group",
                    stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                ),
            )
        )
    return templates


def build_trade_when_templates(
    expression: str,
    *,
    name_prefix: str,
    priority_offset: int = 0,
) -> list[TemplateCandidate]:
    """Build trade_when wrappers around an expression."""
    templates: list[TemplateCandidate] = []
    for event_label, open_event, priority in _TRADE_WHEN_EVENT_SPECS:
        name = f"{name_prefix}_trade_when_{event_label}"
        expr = f"trade_when({open_event}, {expression}, -1)"
        templates.append(
            _make_template_candidate(
                name,
                expr,
                priority + priority_offset,
                metadata=_candidate_metadata(
                    family="event_trade_when",
                    layer="event",
                    stage=TEMPLATE_STAGE_EVENT_CONDITIONED,
                ),
            )
        )
    return templates
