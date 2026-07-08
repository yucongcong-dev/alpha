# fundamental6 Notes

## Positioning
`fundamental6` is treated here as a slow-frequency fundamental dataset.
The current library is intentionally biased toward:
- long-window stabilization (60/120/252/504)
- multiple preprocessing variants (backfill+winsorize, longfill, rawfill)
- ratio/pair templates to reduce self-correlation
- bucket grouping with densify
- event-self-change triggers for vector fields

## Evidence Layers
Official:
- WorldQuant BRAIN alpha examples support neutralization, grouped ranking, and structured expressions as first-class building blocks.

Official field metadata:
- Field filtering and ranking use `coverage`, `dateCoverage`, `alphaCount`, and `userCount`.
- Event-prefixed fields use stricter thresholds than ordinary fundamental fields.

Public-script inspiration:
- The local public script emphasized `winsorize(ts_backfill(...), std=4)`.
- It also used `bucket(...)` grouping and `trade_when(...)` gating.
- xiegengcai factory uses `vec_avg` + `vec_sum` dual channels, `densify()` for bucket groups, and field-self-change event triggers.

Local run evidence:
- Short-window `delta/group_delta/vol_scaled_delta` families repeatedly underperformed on this dataset.
- Near-threshold fields and families were more often found around `cash_st`, `debt`, `debt_lt`, `cogs`, `cashflow_op`, and related ratios.
- Event/vector fields behaved better when isolated into an `event_conditioned` lane instead of mixing with generic template pools.
- Template-level `group_neutralize` + settings `neutralization=SUBINDUSTRY` caused double-neutralization, over-compressing signals.
- Short-window templates (20/5) produce no signal on quarterly-updated fields.
- All 53 test results had `submittable=0` with v3 templates due to self-correlation.

## v4 Template Changes
1. **Removed template-level neutralization**: `group_neutralize` removed from all templates; relies on settings `neutralization=SUBINDUSTRY` instead.
2. **Deleted short-window templates**: `ts_rank_20`, `ts_zscore_20`, `decay_5`, `stddev_20`, `ir_20` removed (quarterly fields have no signal in 20-day windows).
3. **Added preprocessing variants**: `{field_longfill}` = `winsorize(ts_backfill(field, 252), std=3)`, `{field_rawfill}` = `ts_backfill(field, 120)`.
4. **Added ratio/pair templates**: `ratio_cap`, `ratio_assets`, `bucket_ratio` families to reduce self-correlation with existing alphas.
5. **Added densify() to bucket groups**: Prevents sparse-group errors per xiegengcai factory convention.
6. **Event fields use self-change triggers**: `ts_delta({field}) != 0` and `days_from_last_change({field}) <= 5` replace generic volume/returns conditions.
7. **Added vec_sum variants**: Dual-channel `vec_avg` + `vec_sum` per xiegengcai factory.
8. **Added hump parameter scan**: 0.2/0.3/0.4/0.5 thresholds.
9. **Added long-window variants**: `ts_rank_504`, `ts_zscore_126`, `decay_120`.

## Default Library Boundary

The default library should now be read as the narrow production queue for broad exploration:
- keep only a handful of core slow-frequency templates in `default`
- treat vector/event-conditioned families as specialty lanes rather than generic broad-search seeds
- keep cross-field ratio/pair exploration concentrated in the dedicated account/matrix lane instead of bloating scalar `default`
- treat extra long-window neighbors, rawfill/longfill alternates, and legacy cross-sectional wrappers as refine candidates unless they prove repeatedly useful
- the current recovery pack for these demoted defaults is `templates/fundamental6/refine/default_neighbors.json`

Refine pack convention:
- `default_neighbors.json` should now be read as an expansion ring around the new default spine rather than a dump of old scalar leftovers.
- It should primarily broaden:
  - slower or faster neighbors of the surviving slow-frequency templates
  - longer-window `ratio_cap` / `bucket_ratio` variants
  - grouped bucket variants around `cap` and liquidity
  - the secondary event-self-change path that is too specific for broad-search default use

## Things To Revisit Later
- Continue shifting from single-field transforms toward field-relation templates.
- Reassess whether remaining generic `ts_rank/ts_zscore/stddev` defaults should be narrowed even further.
- Keep separating conclusions that are directly supported by official docs from conclusions that come from local runs.
