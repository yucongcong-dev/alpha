# model16 Notes

## Positioning
`model16` is currently treated as a slow-moving score/composite dataset rather than a raw high-frequency signal source.
The template library therefore favors:
- long-window rank/zscore smoothing
- mild decay
- market/sector-aware grouped ranking
- limited bucket-group templates

## Evidence Layers
Official:
- No dataset-specific official template manual was available in local context.
- The usable official guidance is general expression style from BRAIN alpha examples.

Public-script inspiration:
- The shared public script reinforced the value of preprocessed long-window inputs and controlled bucket grouping.

Local structural inference:
- Field naming and observed behavior were more consistent with composite score fields than with daily reactive signals.
- That makes short `delta`, aggressive mean-reversion, and brute-force operator sweeps poor default choices.

Local run / policy evidence:
- The curated library already outperformed legacy fallback shapes strongly enough that several older templates were moved out of the default library.
- Current protected templates bias toward `126`-day structures and group-aware ranking.

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

Legacy handling:
- Older weaker fallback templates live in `legacy.json`, not the main default library.
- mean-reversion, `information_ratio`, normalize/quantile wrappers, and extra long-window neighbors are better treated as refine/experimental branches unless new evidence promotes them
- The current recovery pack is `templates/model16/refine/broad_search_neighbors.json`.

## Things To Revisit Later
- Add a small sector-relative spread family if later runs show enough differentiation between value/quality/growth-style fields.
- Verify whether `information_ratio` should remain in the core default set or be demoted behind grouped bucket variants.
