# model51 Notes

## Positioning
`model51` is treated here as a risk/systematic-metric style dataset.
The library is intentionally built around:
- persistence
- long-window normalization
- market/industry neutralization
- volatility/cap bucket grouping
- avoidance of short-window directional operators

## Evidence Layers
Official:
- As with `model16`, no dataset-specific official template guide was available locally.
- General BRAIN documentation still supports grouped, neutralized, structured expressions.

Local structural inference:
- Field naming and behavior suggested risk or systematic descriptors rather than classic reactive alpha inputs.
- That makes short-window `delta`, `mean_diff`, and broad momentum sweeps poor defaults.

Local run evidence:
- Short-window and generic delta families were weak enough to be explicitly disabled in policy.
- Curated long-window market/industry-normalized templates were more consistent with the intended use of this dataset.

Public-script inspiration:
- Bucket grouping was worth absorbing for more stable relative comparisons.
- The shared preprocessing style also motivated applying winsorization on top of long backfill.

## Current Template Direction
Preprocessing:
- `504`-day backfill plus `winsorize(std=4)`.

Core default shapes:
- market-neutral and industry-neutral zscore decay
- market-group zscore
- long-window rank / zscore / decay / IR
- bucket cap and bucket volatility grouped templates

What was removed:
- Default `stddev`-only templates were dropped from the curated main library because they were less targeted than the newer bucket/risk-aware shapes.

## Things To Revisit Later
- Add regime-aware variants only if later runs show that risk fields respond to separate high-vol / low-vol pathways.
- Re-check whether one of the plain first-order rank/zscore templates can be demoted behind grouped bucket variants.
