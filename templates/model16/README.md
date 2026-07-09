# model16 Notes

## Positioning
`model16` is currently treated as a slow-moving score/composite dataset rather than a raw high-frequency signal source.
The template library therefore favors:
- long-window rank/zscore smoothing
- mild decay
- market/sector-aware grouped ranking
- limited bucket-group templates

## Official Guidance
- No dataset-specific official template manual was available in local context.
- The usable official guidance is general expression style from BRAIN alpha examples.

## Local Evidence

Public-script inspiration:
- The shared public script reinforced the value of preprocessed long-window inputs and controlled bucket grouping.

Local structural inference:
- Field naming and observed behavior were more consistent with composite score fields than with daily reactive signals.
- That makes short `delta`, aggressive mean-reversion, and brute-force operator sweeps poor default choices.

Local run / policy evidence:
- The curated library already outperformed legacy fallback shapes strongly enough that several older templates were moved out of the default library.
- Current protected templates bias toward `126`-day structures and group-aware ranking.
- Recent `stage2_lane_validation_round2` evidence showed the dense-derivative partner-ratio families were systematically weak:
  - `high_conviction_ratio` and `group_ratio_zscore` were usually blocked by `LOW_SHARPE` and `LOW_FITNESS`
  - `group_vol_scaled_delta` repeatedly failed with `CONCENTRATED_WEIGHT` and weak sub-universe behavior
  - default broad search should therefore stop treating derivative pair-ratio branches as first-line candidates

## Current Template Direction
Preprocessing:
- `252`-day backfill plus `winsorize(std=4)`.

Current default-library goal:
- keep a compact production candidate pool centered on the strongest slow-score hypotheses
- avoid letting many close cousins of the same `120/126`-day idea crowd out true idea diversity

Core default shapes:
- `zscore_decay_120`
- `rank_ts_rank_120`
- market/sector group ranking
- cap-ratio / bucket-cap-ratio representatives
- one `mean_spread` branch plus one groupfill representative

Dense derivative lane:
- Prefer `cap-ratio` and `bucket-cap-ratio` as the default broad-search representatives.
- Do not let derivative `pair ratio` families dominate broad search unless a later refine run produces clear near-pass evidence.

Dynamic ratio policy:
- `fscore_*` / `fscore_bfl_*` pair-ratio exploration stays available.
- Dense derivative partner-ratio families are intentionally removed from the default broad-search policy.
- `group_ratio_zscore_*` and `group_vol_scaled_delta` are no longer first-line `model16` defaults.

## What Not To Do

- Do not treat short `delta` and aggressive mean-reversion families as first-line defaults for this dataset.
- Do not let dense derivative pair-ratio branches crowd broad search unless later refine evidence clearly improves.
- Do not promote legacy fallback wrappers back into the main library just because they add quantity.

## Recommended Workflow

Broad exploration:
- Keep broad search compact and hypothesis-driven.
- Prefer the curated dataset library over broad fallback expansion.
- Let structural diversity beat near-neighbor window density.

Focused refine:
- Use refine packs to reopen demoted lanes only after clear near-pass evidence.
- Prefer cap-ratio / bucket-cap-ratio expansions before reviving weak derivative pair-ratio families.

Legacy handling:
- Older weaker fallback templates live in `legacy.json`, not the main default library.
- mean-reversion, `information_ratio`, normalize/quantile wrappers, and extra long-window neighbors are better treated as refine/experimental branches unless new evidence promotes them
- The current recovery pack is `templates/model16/refine/broad_search_neighbors.json`.

## Open Questions
- Add a small sector-relative spread family if later runs show enough differentiation between value/quality/growth-style fields.
- Verify whether `information_ratio` should remain in the core default set or be demoted behind grouped bucket variants.
