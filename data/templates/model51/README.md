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
- After tightening the checksubmit gate to wait for `SELF_CORRELATION`, the current risk-field branches no longer look production-viable: recent rechecks on both `unsystematic_risk_last_*` and `systematic_risk_last_*` were excluded because self-correlation never reached a terminal state within the poll budget.
- The workflow now preserves these candidates as `pending_self_correlation` results instead of pretending they are normal simulated failures, so they can be rechecked later without polluting template feedback.

Public-script inspiration:
- Bucket grouping was worth absorbing for more stable relative comparisons.
- The shared preprocessing style also motivated applying winsorization on top of long backfill.

## Current Template Direction
Preprocessing:
- `504`-day backfill plus `winsorize(std=4)`.

Current default-library goal:
- keep only a small production candidate pool with meaningfully different structures
- avoid filling the default queue with near-neighbor window variants around the same crowded risk branch

Core default shapes:
- first-order long-window `ts_rank / ts_zscore / decay`
- one bucket-cap grouped template
- one cap-ratio template plus one bucket-cap-ratio template that are less identical to the old risk-field branch

What was removed:
- Default `stddev`-only templates were dropped from the curated main library because they were less targeted than the newer bucket/risk-aware shapes.
- most extra grouped/decay/window neighbors should now be treated as refine or diagnostic inputs, not default broad-search seeds
- `IR` is no longer kept in the tiny default queue; it moved behind the ratio-oriented branch in `refine/`

Field ordering:
- crowded risk fields now rely on explicit `alphaCount/userCount` crowding penalties in policy instead of floating to the front just because they are historically common

## Recommended Workflow
Broad exploration:
- `model51` has already shown enough structure that wide template sweeps should stay narrow and curated.
- Prefer the dataset library over the shared base library.
- Do not keep spending broad-search budget on the current risk-field families until the self-correlation behavior is understood better.
- If you still run a broad sweep for diagnostics, treat it as a producer of `pending_self_correlation` backlog first and an alpha-discovery run second.

Focused refine:
- Historical focused fixtures remain in the repo for auditability, but they should currently be treated as diagnostic inputs rather than preferred production refine defaults.
- [refine/local_refine_round7.json](refine/local_refine_round7.json) keeps a small set of proven local refine variants around the same risk-field branch. It is stored here instead of the repository root because it is reusable dataset knowledge, not a one-off temporary file.
- [refine/local_refine_industry_decay_triplet_round9.json](refine/local_refine_industry_decay_triplet_round9.json) and [refine/local_refine_market_decay_triplet_round9.json](refine/local_refine_market_decay_triplet_round9.json) keep a tighter decay sweep (`10/15/20`) around the `ts_zscore(..., 63)` branch for industry and market neutralization.
- [refine/local_refine_decay_density_round10.json](refine/local_refine_decay_density_round10.json) keeps a denser decay sweep (`8/12/18/24`) around the same `ts_zscore(..., 63)` branch.
- [refine/local_refine_window_sweep_round11.json](refine/local_refine_window_sweep_round11.json) compares neighboring `ts_zscore` windows (`56/63/70`) at the same decay branch.
- [refine/fields/unsystematic_group_branch_round12_fields.txt](refine/fields/unsystematic_group_branch_round12_fields.txt) and [refine/group_branch_round12_templates.txt](refine/group_branch_round12_templates.txt) capture the non-decay recheck on the unsystematic branch.
- [refine/fields/systematic_branch_round13_fields.txt](refine/fields/systematic_branch_round13_fields.txt) and [refine/systematic_branch_round13_templates.txt](refine/systematic_branch_round13_templates.txt) capture the corresponding systematic-branch recheck.

Refine pack convention:
- Keep `library.json` as the default narrow production library.
- Keep targeted local sweeps under `refine/`.
- Load refine packs explicitly with `--template-library-file data/templates/model51/refine/<file>.json`.
- The current broadening pack is `data/templates/model51/refine/broad_search_neighbors.json`.
- If a focused experiment needs a stable hand-curated field cache, keep it under `refine/fields/` instead of `cache/`.
- grouped `market` zscore families, extra decay-window families, and bucket-volatility variants belong here once they stop earning a place in the default queue

Current local evidence behind this narrower focus:
- Historical runs once showed `submittable=true` or near-pass behavior on the risk-field branch, but those signals are no longer sufficient by themselves after the self-correlation gate was tightened.
- `beta_last_*_spy` and `correlation_last_*_spy` have been consistently weak in both broad and focused runs, so they are no longer part of the default refine whitelist.
- The current `focused_fields.txt` / `focused_templates.txt` pair therefore keeps only the still-worth-probing `systematic/unsystematic risk` branch and drops the weaker `beta/correlation` spy branch from the next focused round.
- `window_sweep_round11_selfcorr_recheck` revalidated the `unsystematic_risk_last_360_days` decay-window branch (`market/industry`, `56/63/70`) and all 6 candidates were excluded because `SELF_CORRELATION` stayed `PENDING`.
- `group_branch_round12_recheck` then retried `unsystematic_risk_last_60/90/360_days` with non-decay group/bucket/time-series templates, and the first 9 tested candidates were again excluded for the same reason.
- `systematic_branch_round13_recheck` repeated the same non-decay template families on `systematic_risk_last_30/60/90_days`, and all 9 tested candidates were likewise excluded because `SELF_CORRELATION` never reached a terminal state.
- `focused_validation` then reran a much narrower `5 fields x 4 templates = 20` validation set under the current workflow and all candidates reached terminal results. That removed the earlier ambiguity: the current blocker is no longer `SELF_CORRELATION`, but ordinary quality gates led by `LOW_FITNESS`.
- In that focused validation, `unsystematic_risk_last_60_days` became the only branch still close enough to justify more budget. The best three local candidates were `model51_ts_zscore_120` (`fitness=0.85`), `model51_bucket_cap_zscore_120` (`fitness=0.83`), and `model51_ts_rank_120` (`fitness=0.78`).
- `systematic_risk_last_*` remained broadly weak across the same pack, so the next local refine round should drop it and spend the budget only on `unsystematic_risk_last_60_days`.
- [refine/fields/unsystematic60_refine_round14_fields.txt](refine/fields/unsystematic60_refine_round14_fields.txt) and [refine/unsystematic60_refine_round14.json](refine/unsystematic60_refine_round14.json) capture that next-step local refine round. The pack keeps the three near-pass core templates and adds the `ratio_cap` / `bucket_ratio` / `60-day neighbor` variants that the prior focused validation did not really expand.

At this point the preferred next step is no longer a self-correlation diagnostic recheck. The tighter `focused_validation` run already showed that the most promising live branch can finish normally and is now primarily blocked by `LOW_FITNESS` / `LOW_SHARPE`, so the next budget should go to local refine rather than broader polling experiments.

Suggested round14 refine command:
```bash
python3 -m alpha run \
  --dataset-id model51 \
  --include-fields-file data/templates/model51/refine/fields/unsystematic60_refine_round14_fields.txt \
  --template-library-file data/templates/model51/refine/unsystematic60_refine_round14.json \
  --limit 1 \
  --max-templates-per-field 7 \
  --max-templates-per-family 2 \
  --max-concurrent-simulations 2 \
  --max-concurrent-creates 1 \
  --output results/model51/unsystematic60_refine_round14.json \
  --feedback-output results/model51/focused_validation.json \
  --no-auto-update-blacklist
```

Current assessment:
- `beta/correlation` families are still weak and do not become attractive just because the earlier risk-field branches stalled.
- The highest-signal remaining branch is now clearly `unsystematic_risk_last_60_days`, and its current gap is quality uplift, not workflow completion.
- Historical `submittable=true` records on neighboring risk branches should still be treated cautiously, but they are no longer the main driver of the next action.
- That makes `model51` worth one more small local refine round, not another broad exploration sweep.
- Operationally, this now means:
  - keep the search local around the best unsystematic branch
  - spend limited budget on structural neighbors rather than on wider field coverage
  - only return to broader diagnostics if the round14 local refine fails cleanly

## Things To Revisit Later
- Run another self-correlation-focused diagnostic only if a future branch again stalls in `PENDING`; it is no longer the default next step for the current round14 path.
- Add regime-aware variants only if later runs show that risk fields respond to separate high-vol / low-vol pathways.
- Re-check whether one of the plain first-order rank/zscore templates can be demoted behind grouped bucket variants.
