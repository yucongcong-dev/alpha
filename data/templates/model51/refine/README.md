# model51 Refine Templates

This folder stores curated local-refine template packs for `model51`.

- Keep `../library.json` as the default narrow production library.
- Put small, evidence-backed local sweeps here instead of the dataset root.
- Load a pack explicitly with `--template-library-file data/templates/model51/refine/<file>.json`.
- Move a template into `../library.json` only after repeated near-pass or submittable evidence.

Current packs:

- `local_refine_round7.json`: early local variants around proven unsystematic-risk winners.
- `local_refine_market_decay_triplet_round9.json`: market-neutral decay triplet sweep.
- `local_refine_industry_decay_triplet_round9.json`: industry-neutral decay triplet sweep.
- `local_refine_decay_density_round10.json`: denser decay sweep around the strongest families.
- `local_refine_window_sweep_round11.json`: focused `56/63/70` zscore-window sweep with fixed decay 12.
