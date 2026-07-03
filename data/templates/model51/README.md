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

## Recommended Workflow
Broad exploration:
- `model51` has already shown enough structure that wide template sweeps should stay narrow and curated.
- Prefer the dataset library over the shared base library.

Focused refine:
- Use [focused_fields.txt](focused_fields.txt) to keep the run centered on the strongest local field family:
  - `unsystematic_risk_last_360_days`
  - `systematic_risk_last_360_days`
- Use [focused_templates.txt](focused_templates.txt) to keep the run centered on the strongest template family:
  - `model51_industry_zscore_decay_63`
  - `model51_market_zscore_decay_63`
  - `model51_group_zscore_market_126`
- [local_refine_round7.json](local_refine_round7.json) keeps a small set of proven local refine variants around the same risk-field branch. It is stored here instead of the repository root because it is reusable dataset knowledge, not a one-off temporary file.
- [local_refine_industry_decay_triplet_round9.json](local_refine_industry_decay_triplet_round9.json) and [local_refine_market_decay_triplet_round9.json](local_refine_market_decay_triplet_round9.json) keep a tighter decay sweep (`10/15/20`) around the `ts_zscore(..., 63)` branch for industry and market neutralization.

Current local evidence behind this narrower focus:
- `unsystematic_risk_last_360_days + model51_industry_zscore_decay_63` has already produced `submittable=true`.
- `unsystematic_risk_last_60/90_days + model51_group_zscore_market_126` repeatedly landed near the platform threshold on fitness.
- `beta_last_*_spy` and `correlation_last_*_spy` have been consistently weak in both broad and focused runs, so they are no longer part of the default refine whitelist.

Suggested commands:
```bash
python3 -m alpha --dataset-id model51 --dry-run-plan \
  --include-fields-file data/templates/model51/focused_fields.txt \
  --include-templates-file data/templates/model51/focused_templates.txt \
  --limit 2 --max-templates-per-field 3 --max-templates-per-family 1 \
  --output results/model51/focused_validation.json \
  --feedback-output results/model51/focused_validation.json \
  --no-auto-update-blacklist
```

```bash
python3 -m alpha --dataset-id model51 \
  --include-fields-file data/templates/model51/focused_fields.txt \
  --include-templates-file data/templates/model51/focused_templates.txt \
  --limit 2 --max-templates-per-field 3 --max-templates-per-family 1 \
  --max-concurrent-simulations 1 --max-concurrent-creates 1 \
  --output results/model51/focused_validation.json \
  --feedback-output results/model51/focused_validation.json \
  --no-auto-update-blacklist
```

Local evidence:
- `unsystematic_risk_last_360_days + model51_industry_zscore_decay_63` has already produced a `submittable=true` result locally.
- `beta/correlation` families have shown clearly weaker quality than the risk families in repeated runs.
- That makes `model51` a better candidate for continued refine than `fundamental6` under the current template framework, but specifically along the risk-field branch rather than the broader SPY beta/correlation branch.

## Things To Revisit Later
- Add regime-aware variants only if later runs show that risk fields respond to separate high-vol / low-vol pathways.
- Re-check whether one of the plain first-order rank/zscore templates can be demoted behind grouped bucket variants.
