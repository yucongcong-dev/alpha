# WorldQuant Brain Alpha Runner

Generic WorldQuant Brain dataset alpha simulation/check/submit runner.

## Setup

```bash
python3 -m pip install -r requirements.txt
```

## Run

Smoke test, only for checking login/API flow:

```bash
python3 worldquant_brain_dataset_submit.py --smoke-test
```

Default exploration run, suitable for looking for candidate alphas. This is the recommended daily command because it tests a useful sample instead of only one field/template:

```bash
python3 worldquant_brain_dataset_submit.py
```

Wider exploration, when you want a better chance of finding useful candidates:

```bash
python3 worldquant_brain_dataset_submit.py --limit 50 --max-templates-per-field 8
```

Force refresh the local field cache before exploring:

```bash
python3 worldquant_brain_dataset_submit.py --refresh-fields-cache
```

Full run, can be slow and queue-heavy. Use it only when you are ready to spend more API queue time:

```bash
python3 worldquant_brain_dataset_submit.py --full-run
```

Avoid using `--limit 1 --max-templates-per-field 1` for alpha discovery. That mode is intentionally tiny and almost never finds high-quality alphas.

The script automatically refreshes the field cache when the cached field count is smaller than the requested `--limit`.

After each run, inspect `*_test_results_analysis.json` for `failed_check_leaderboard`, `near_pass_summary`, and `optimization_hints`. These sections show the main blockers and the best candidates for the next iteration.

The first run prompts for WorldQuant Brain credentials and stores them encrypted locally. Credential files, logs, caches, and result files are ignored by git.
