# fundamental6 Notes

## Positioning
`fundamental6` is treated here as a slow-frequency fundamental dataset.
The current library is intentionally biased toward:
- long-window stabilization
- preprocessed `backfill + winsorize`
- account-level curated templates
- field-relation and bucket/group structures
- event-only side channel for `fnd6_cptnewqeventv110_*`

## Evidence Layers
Official:
- WorldQuant BRAIN alpha examples support neutralization, grouped ranking, and structured expressions as first-class building blocks.

Official field metadata:
- Field filtering and ranking use `coverage`, `dateCoverage`, `alphaCount`, and `userCount`.
- Event-prefixed fields use stricter thresholds than ordinary fundamental fields.

Public-script inspiration:
- The local public script emphasized `winsorize(ts_backfill(...), std=4)`.
- It also used `bucket(...)` grouping and `trade_when(...)` gating.

Local run evidence:
- Short-window `delta/group_delta/vol_scaled_delta` families repeatedly underperformed on this dataset.
- Near-threshold fields and families were more often found around `cash_st`, `debt`, `debt_lt`, `cogs`, `cashflow_op`, and related ratios.
- Event/vector fields behaved better when isolated into an `event_conditioned` lane instead of mixing with generic template pools.

## Current Template Direction
Default library:
- Reduced generic slow-frequency sweep templates.
- Keeps a smaller set of long-window `ts_rank`, `ts_zscore`, `decay`, and shape/stat templates.

Dataset-specific matrix templates:
- Prioritize `account_*` templates using `{field_preprocessed}`.
- Add bucket-aware templates such as cap, liquidity, and volatility buckets.

Event templates:
- `event_trade_when_*` templates are reserved for event-like vector fields.

## Things To Revisit Later
- Continue shifting from single-field transforms toward field-relation templates.
- Reassess whether remaining generic `ts_rank/ts_zscore/stddev` defaults should be narrowed even further.
- Keep separating conclusions that are directly supported by official docs from conclusions that come from local runs.
