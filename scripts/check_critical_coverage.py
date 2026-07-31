"""Enforce risk-weighted per-file coverage floors from coverage.py JSON output."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

CRITICAL_COVERAGE_FLOORS = {
    "src/alpha/config/runtime_values.py": 90.0,
    "src/alpha/config/yaml.py": 65.0,
    "src/alpha/core/executor.py": 65.0,
    "src/alpha/core/checkpoint.py": 85.0,
    "src/alpha/core/simulation.py": 80.0,
    "src/alpha/core/simulation_stages.py": 85.0,
    "src/alpha/io/results_store.py": 85.0,
    "src/alpha/analysis/results_loader.py": 80.0,
    "src/alpha/analysis/feedback_run_index.py": 80.0,
    "src/alpha/analysis/result_identity.py": 75.0,
    "src/alpha/analysis/failed_checks.py": 90.0,
    "src/alpha/app/finalize.py": 80.0,
    "src/alpha/app/run_loop_rounds.py": 80.0,
    "src/alpha/generators/fields.py": 65.0,
    "src/alpha/generators/fingerprint.py": 95.0,
    "src/alpha/generators/payload.py": 90.0,
    "src/alpha/selection/feedback_filters.py": 85.0,
    "src/alpha/cli/filters.py": 90.0,
    "src/alpha/io/credentials.py": 80.0,
    "src/alpha/io/credentials_crypto.py": 80.0,
    "src/alpha/io/file_lock.py": 95.0,
}


def normalize_report_files(files: dict[str, Any]) -> dict[str, Any]:
    """Normalize coverage.py file keys across POSIX and Windows reports."""
    return {file_path.replace("\\", "/"): details for file_path, details in files.items()}


def main() -> int:
    report_path = Path(sys.argv[1] if len(sys.argv) > 1 else ".coverage.json")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    files = normalize_report_files(payload.get("files", {}))
    failures: list[str] = []
    for file_path, minimum in CRITICAL_COVERAGE_FLOORS.items():
        summary = files.get(file_path, {}).get("summary", {})
        actual = float(summary.get("percent_covered", 0.0) or 0.0)
        if actual < minimum:
            failures.append(f"{file_path}: {actual:.1f}% < required {minimum:.1f}%")
    if failures:
        print("[coverage] critical module floors failed:\n" + "\n".join(failures))
        return 1
    print(f"[coverage] validated {len(CRITICAL_COVERAGE_FLOORS)} critical module floors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
