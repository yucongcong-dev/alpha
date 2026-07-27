"""Validate repository-local Markdown links and documentation boundaries."""

from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CONCRETE_RUN_PATH_PATTERN = re.compile(r"datasets/(?!<)[A-Za-z0-9._-]+/runs/[A-Za-z0-9._/-]+")


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


def check_document(path: Path) -> list[str]:
    """Return actionable documentation errors for one Markdown file."""
    relative_path = path.relative_to(ROOT)
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
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
    errors = [error for path in documentation_files() for error in check_document(path)]
    if errors:
        print("\n".join(errors))
        return 1
    print(f"[docs-check] validated {len(documentation_files())} Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
