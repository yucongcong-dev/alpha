# WorldQuant Brain Alpha Runner

Generic WorldQuant Brain dataset alpha simulation/check/submit runner.

## Setup

```bash
python3 -m pip install -r requirements.txt
```

## Run

Small test run:

```bash
python3 worldquant_brain_dataset_submit.py --limit 1 --max-templates-per-field 1 --max-concurrent-simulations 1 --max-concurrent-creates 1
```

Normal run:

```bash
python3 worldquant_brain_dataset_submit.py
```

The first run prompts for WorldQuant Brain credentials and stores them encrypted locally. Credential files, logs, caches, and result files are ignored by git.
