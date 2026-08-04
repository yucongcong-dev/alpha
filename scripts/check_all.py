"""Cross-platform repository check orchestrator."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class CheckCommand:
    argv: tuple[str, ...]
    quiet: bool = False


FULL_CHECK_ORDER = (
    "python-version",
    "coverage",
    "help",
    "whitespace",
    "docs",
    "scan-secrets",
    "repo-boundary",
    "removed-compat-file",
    "compat-import",
    "arch-boundary",
    "todo",
    "config-sync",
    "ruff",
    "format",
    "mypy",
)


def build_task_commands(
    python: str = sys.executable,
    *,
    ruff_executable: str | None = None,
) -> dict[str, tuple[CheckCommand, ...]]:
    py = (python,)
    resolved_ruff = ruff_executable or shutil.which("ruff")
    ruff = (resolved_ruff,) if resolved_ruff else (*py, "-m", "ruff")
    return {
        "python-version": (CheckCommand((*py, "scripts/check_python_version.py")),),
        "test": (CheckCommand((*py, "-m", "pytest", "-q")),),
        "coverage": (
            CheckCommand(
                (
                    *py,
                    "-m",
                    "pytest",
                    "--cov=alpha",
                    "--cov-report=term:skip-covered",
                    "--cov-report=json:.coverage.json",
                    "-q",
                )
            ),
            CheckCommand((*py, "scripts/check_critical_coverage.py", ".coverage.json")),
        ),
        "help": (CheckCommand((*py, "-m", "alpha", "--help"), quiet=True),),
        "whitespace": (CheckCommand(("git", "diff", "--check")),),
        "docs": (CheckCommand((*py, "scripts/check_docs.py")),),
        "scan-secrets": (CheckCommand((*py, "scripts/check_repo.py", "scan-secrets")),),
        "repo-boundary": (CheckCommand((*py, "scripts/check_repo.py", "repo-boundary")),),
        "removed-compat-file": (
            CheckCommand((*py, "scripts/check_repo.py", "removed-compat-file")),
        ),
        "compat-import": (CheckCommand((*py, "scripts/check_repo.py", "compat-import")),),
        "arch-boundary": (CheckCommand((*py, "scripts/check_repo.py", "arch-boundary")),),
        "todo": (CheckCommand((*py, "scripts/check_repo.py", "todo")),),
        "config-sync": (CheckCommand((*py, "scripts/sync_config.py", "--check")),),
        "ruff": (CheckCommand((*ruff, "check", ".")),),
        "format": (CheckCommand((*ruff, "format", "--check", "src", "tests", "scripts")),),
        "mypy": (CheckCommand((*py, "-m", "mypy", "src/alpha")),),
    }


def build_check_environment(root: Path = ROOT) -> dict[str, str]:
    env = dict(os.environ)
    src_path = str(root / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_checks(task_names: list[str], *, root: Path = ROOT) -> int:
    commands_by_task = build_task_commands()
    selected = task_names if task_names else list(FULL_CHECK_ORDER)
    env = build_check_environment(root)

    for task_name in selected:
        print(f"[check] {task_name}", flush=True)
        for command in commands_by_task[task_name]:
            print(f"+ {subprocess.list2cmdline(command.argv)}", flush=True)
            try:
                subprocess.run(
                    command.argv,
                    cwd=root,
                    env=env,
                    check=True,
                    stdout=subprocess.DEVNULL if command.quiet else None,
                )
            except subprocess.CalledProcessError as exc:
                return int(exc.returncode or 1)
    return 0


def main(argv: list[str] | None = None) -> int:
    commands_by_task = build_task_commands()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tasks",
        nargs="*",
        help="Checks to run; omit to run the complete repository check suite.",
    )
    args = parser.parse_args(argv)
    unknown = sorted(set(args.tasks) - set(commands_by_task))
    if unknown:
        parser.error(f"unknown checks: {', '.join(unknown)}")
    return run_checks(args.tasks)


if __name__ == "__main__":
    raise SystemExit(main())
