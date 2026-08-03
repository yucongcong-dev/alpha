"""Remove local Python development caches in a cross-platform way."""

from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

NAMED_CACHE_DIRS = {
    "__pycache__",
    ".pycache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
}
ROOT_CACHE_FILES = {".coverage", ".coverage.json"}
ROOT_CACHE_PATHS = {Path("tmp") / "pycache"}
SEARCH_ROOTS = ("src", "tests", "scripts")


def _remove_path(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def clean_dev(root: Path = ROOT) -> list[str]:
    """Remove common local development caches and return removed relative paths."""
    removed: list[str] = []
    candidates: list[Path] = []
    for relative_root in SEARCH_ROOTS:
        search_root = root / relative_root
        if search_root.exists():
            candidates.extend(
                path
                for path in search_root.rglob("*")
                if path.name in NAMED_CACHE_DIRS or path.name.endswith(".egg-info")
            )

    candidates.extend(root / name for name in sorted(NAMED_CACHE_DIRS))

    removed.extend(
        path.relative_to(root).as_posix()
        for path in sorted(set(candidates), key=lambda item: len(item.parts), reverse=True)
        if _remove_path(path)
    )

    for relative_path in sorted(ROOT_CACHE_PATHS):
        path = root / relative_path
        if _remove_path(path):
            removed.append(relative_path.as_posix())

    for name in sorted(ROOT_CACHE_FILES):
        path = root / name
        if _remove_path(path):
            removed.append(name)
    return sorted(set(removed))


def main() -> int:
    removed = clean_dev()
    print(f"[clean-dev] removed {len(removed)} Python cache artifact(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
