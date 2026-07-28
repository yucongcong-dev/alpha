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


def documentation_files() -> list[Path]:
    """Return every maintained Markdown entrypoint in deterministic order."""
    return [
        ROOT / "README.md",
        *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "datasets").glob("**/README.md")),
    ]


def local_link_target(raw_target: str) -> str:
    """Normalize a Markdown link target and discard anchors or query strings."""
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return ""
    return target.split("#", 1)[0].split("?", 1)[0]


def documented_cli_flags() -> set[str]:
    """Return the CLI options exposed by the current parser help."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "alpha", "--help"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return set(CLI_FLAG_PATTERN.findall(completed.stdout))


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


def main() -> int:
    """Validate all maintained Markdown files."""
    valid_cli_flags = documented_cli_flags()
    errors = [
        error
        for path in documentation_files()
        for error in check_document(path, valid_cli_flags=valid_cli_flags)
    ]
    if errors:
        print("\n".join(errors))
        return 1
    print(f"[docs-check] validated {len(documentation_files())} Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
