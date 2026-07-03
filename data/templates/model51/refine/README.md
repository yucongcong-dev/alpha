# model51 Refine Templates

This folder stores curated local-refine template packs for `model51`.

- Keep `../library.json` as the default narrow production library.
- Put small, evidence-backed local sweeps here instead of the dataset root.
- Load a pack explicitly with `--template-library-file data/templates/model51/refine/<file>.json`.
- Move a template into `../library.json` only after repeated near-pass or submittable evidence.
- If a run needs a manually curated field fixture rather than a regenerated API cache, keep it under `fields/` here instead of `cache/`.

Current packs:

- `local_refine_round7.json`: early local variants around proven unsystematic-risk winners.
- `local_refine_market_decay_triplet_round9.json`: market-neutral decay triplet sweep.
- `local_refine_industry_decay_triplet_round9.json`: industry-neutral decay triplet sweep.
- `local_refine_decay_density_round10.json`: denser decay sweep around the strongest families.
- `local_refine_window_sweep_round11.json`: neighboring zscore-window sweep (`56/63/70`) around the strongest decay branch.

Recent diagnostic fixtures:

- `fields/unsystematic_group_branch_round12_fields.txt` with `group_branch_round12_templates.txt`: non-decay recheck on `unsystematic_risk_last_60/90/360_days`.
- `fields/systematic_branch_round13_fields.txt` with `systematic_branch_round13_templates.txt`: non-decay recheck on `systematic_risk_last_30/60/90_days`.

Historical preference order from pre-gated local results:

- Primary:
  - `model51_market_zscore_decay_63_d12`
  - `model51_industry_zscore_decay_63_d12`
- Secondary:
  - `model51_market_zscore_decay_56_d12`
  - `model51_industry_zscore_decay_56_d12`
- Tertiary but still passing:
  - `model51_market_zscore_decay_70_d12`
  - `model51_industry_zscore_decay_70_d12`

Current status after self-correlation rechecks:

- `window_sweep_round11_selfcorr_recheck` excluded all 6 decay-window variants because `SELF_CORRELATION` remained `PENDING` through the full poll budget.
- `group_branch_round12_recheck` excluded the first 9 unsystematic non-decay variants for the same reason.
- `systematic_branch_round13_recheck` excluded 9 systematic non-decay variants for the same reason.
- Because of that, the preference order above should now be treated as historical only, not as an active recommendation for further overnight exploration.
- Under the current workflow, these results should be stored and revisited via the dedicated pending-self-correlation recheck mode, not immediately fed back as ordinary refine evidence.

Curated field fixtures:

- `fields/unsystematic_only_round11_fields.json`: single-field fixture used to force window-sweep experiments onto `unsystematic_risk_last_360_days` without relying on transient include-file state.
