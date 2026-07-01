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

Core default shapes:
- `rank_zscore_decay_126`
- `rank_ts_rank_126`
- market-neutral zscore decay
- market/sector group ranking
- bucket cap / bucket liquidity long-window grouped templates

Legacy handling:
- Older weaker fallback templates live in `legacy.json`, not the main default library.

## Things To Revisit Later
- Add a small sector-relative spread family if later runs show enough differentiation between value/quality/growth-style fields.
- Verify whether `information_ratio` should remain in the core default set or be demoted behind grouped bucket variants.
