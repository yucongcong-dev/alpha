# base Notes

## Positioning
`base` is the shared fallback template library for datasets that do not yet have a strongly curated dataset-specific library.
It is intentionally no longer treated as the best default for every dataset.
The current role of this library is:
- provide a compact general-purpose starting point
- keep relatively stable long-window rank/zscore/decay structures
- offer a small set of modern bucket/group templates
- leave dataset-specific specialization to `data/templates/{dataset_id}/library.json`

## Evidence Layers
Official:
- WorldQuant BRAIN alpha examples support grouped ranking, neutralization, and structured multi-step expressions.

Public-script inspiration:
- Shared public backtest scripts repeatedly used `ts_backfill + winsorize`.
- They also reinforced `bucket(...)` grouping and event gating as more modern building blocks than brute-force short-window sweeps.

Local run evidence:
- Old short-window default families such as `delta_5`, `group_delta_5*`, `ts_corr_self_*`, and `argmax/min_60` were repeatedly low-value across slow-frequency datasets.
- More stable behavior came from long-window normalization, grouped ranking, and a narrower template pool.

## Current Template Direction
What the base library keeps:
- medium/long-window `delta`, `ts_rank`, `ts_zscore`, and `decay`
- a limited set of grouped and neutralized templates
- bucket-aware cap, liquidity, and volatility grouped templates

What the base library no longer tries to do:
- act as a brute-force operator sweep for every dataset
- keep weak short-window templates at the front of the default queue
- substitute for dataset-native libraries such as `fundamental6`, `model16`, or `model51`

## Things To Revisit Later
- Continue shrinking base if a template family is consistently dominated by dataset-specific libraries.
- Add new shared templates only when they prove portable across multiple datasets, not just one dataset's local success.
- Keep comments and ordering aligned with actual runtime defaults so the base library remains trustworthy as a fallback reference.
