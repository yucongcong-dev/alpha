"""Validate repository-local Markdown links and documentation boundaries."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
CLI_FLAG_PATTERN = re.compile(r"(?<![A-Za-z0-9-])(--[a-z](?:[a-z0-9-]*[a-z0-9])?)")
REPO_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:README\.md|(?:config|datasets|docs|scripts|src|tests)/[A-Za-z0-9_./-]+)"
)
ABSOLUTE_LOCAL_PATH_PATTERN = re.compile(
    r"(?:/Users/[^\s`'\")]+|/home/[^\s`'\")]+|[A-Za-z]:\\[^\s`'\")]+)"
)
CONCRETE_RUN_PATH_PATTERN = re.compile(r"datasets/(?!<)[A-Za-z0-9._-]+/runs/[A-Za-z0-9._/-]+")
PLACEHOLDER_MARKERS = ("<", ">", "*", "$", "{")
DATASET_STATUS_PATTERN = re.compile(r"\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|")


def documentation_files() -> list[Path]:
    """Return every maintained Markdown entrypoint in deterministic order."""
    return [
        ROOT / "README.md",
        *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "datasets").glob("**/*.md")),
    ]


def local_link_target(raw_target: str) -> str:
    """Normalize a Markdown link target and discard anchors or query strings."""
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return ""
    return target.split("#", 1)[0].split("?", 1)[0]


def documented_cli_flags() -> set[str]:
    """Return options exposed by the run and command-specific parser help."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    flags: set[str] = set()
    for command_args in ([], ["clean"], ["check-submissions"]):
        completed = subprocess.run(
            [sys.executable, "-m", "alpha", *command_args, "--help"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        flags.update(CLI_FLAG_PATTERN.findall(completed.stdout))
    return flags


def _concrete_repo_paths(line: str) -> set[str]:
    """Extract concrete repository paths from inline-code spans."""
    paths: set[str] = set()
    for code in INLINE_CODE_PATTERN.findall(line):
        if any(marker in code for marker in PLACEHOLDER_MARKERS):
            continue
        for match in REPO_PATH_PATTERN.findall(code):
            paths.add(match.rstrip(".,;:"))
    return paths


def _repository_path_exists(root: Path, target: str) -> bool:
    """Resolve root paths and documented package-relative module paths."""
    return (root / target).exists() or (root / "src" / "alpha" / target).exists()


def _concrete_cli_flags(line: str) -> set[str]:
    """Extract concrete options while ignoring documented wildcard families."""
    return {
        match.group(1)
        for match in CLI_FLAG_PATTERN.finditer(line)
        if not line[match.end() :].startswith("-*")
    }


def check_document(
    path: Path,
    *,
    root: Path = ROOT,
    valid_cli_flags: set[str] | None = None,
) -> list[str]:
    """Return actionable documentation errors for one Markdown file."""
    relative_path = path.relative_to(root)
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        absolute_path = ABSOLUTE_LOCAL_PATH_PATTERN.search(line)
        if absolute_path:
            errors.append(
                f"{relative_path}:{line_number}: absolute local path is not portable: "
                f"{absolute_path.group(0)}"
            )

        for raw_target in LINK_PATTERN.findall(line):
            target = local_link_target(raw_target)
            if not target:
                continue
            target_path = Path(target)
            if target_path.is_absolute():
                errors.append(
                    f"{relative_path}:{line_number}: absolute local link is not portable: {target}"
                )
                continue
            if not (path.parent / target_path).exists():
                errors.append(f"{relative_path}:{line_number}: missing local link target: {target}")

        errors.extend(
            (f"{relative_path}:{line_number}: missing repository path in inline code: {target}")
            for target in sorted(_concrete_repo_paths(line))
            if not _repository_path_exists(root, target)
        )

        if valid_cli_flags is not None:
            errors.extend(
                f"{relative_path}:{line_number}: undocumented CLI option: {flag}"
                for flag in sorted(_concrete_cli_flags(line))
                if flag not in valid_cli_flags
            )

        if relative_path.parts[:1] == ("datasets",):
            match = CONCRETE_RUN_PATH_PATTERN.search(line)
            if match:
                errors.append(
                    f"{relative_path}:{line_number}: dataset knowledge must not depend on "
                    f"cleanable run output: {match.group(0)}"
                )

    return errors


def check_dataset_strategy_consistency(*, root: Path = ROOT) -> list[str]:
    """Keep the dataset status table aligned with runtime profiles and presets."""
    import yaml

    status_path = root / "datasets" / "README.md"
    profile_path = root / "config" / "dataset_profiles.yaml"
    if not status_path.is_file() or not profile_path.is_file():
        return []

    profile_data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    profiles = profile_data.get("dataset_profiles", {})
    errors: list[str] = []
    for dataset_id, raw_status in DATASET_STATUS_PATTERN.findall(
        status_path.read_text(encoding="utf-8")
    ):
        status = raw_status.strip()
        profile = profiles.get(dataset_id, {}) if isinstance(profiles, dict) else {}
        if status in {"暂停", "基线保留"} and not bool(profile.get("paused", False)):
            errors.append(
                f"datasets/README.md: non-active dataset {dataset_id} is not paused in "
                "config/dataset_profiles.yaml"
            )
        if status != "探索":
            continue
        if bool(profile.get("paused", False)):
            errors.append(
                f"datasets/README.md: explore dataset {dataset_id} is paused in "
                "config/dataset_profiles.yaml"
            )
        preset_name = str(profile.get("default_preset", "") or "").strip()
        if not preset_name:
            errors.append(f"datasets/README.md: explore dataset {dataset_id} has no default_preset")
            continue
        preset_dir = root / "datasets" / dataset_id / "presets" / preset_name
        missing = [
            path.name
            for path in (
                preset_dir / "template.json",
                preset_dir / "fields.txt",
                preset_dir / "templates.txt",
            )
            if not path.is_file()
        ]
        if missing:
            errors.append(
                f"datasets/README.md: explore dataset {dataset_id} preset {preset_name} "
                f"is incomplete: {', '.join(missing)}"
            )
    return errors


def main() -> int:
    """Validate all maintained Markdown files."""
    valid_cli_flags = documented_cli_flags()
    errors = [
        error
        for path in documentation_files()
        for error in check_document(path, valid_cli_flags=valid_cli_flags)
    ]
    errors.extend(check_dataset_strategy_consistency())
    if errors:
        print("\n".join(errors))
        return 1
    print(f"[docs-check] validated {len(documentation_files())} Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
