"""Cross-platform repository policy checks used by Makefile and CI."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERN = re.compile(r"github_[p]at_[A-Za-z0-9_]+|WQB_[P]ASSWORD=|Authorization: [B]asic")

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "cache",
    "dist",
    "htmlcov",
    "results",
    "scratch",
    "tmp",
}
DATASET_RUNTIME_DIRS = {"cache", "feedback", "runs"}

Check = Callable[[Path], list[str]]


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_skipped(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    return len(parts) >= 3 and parts[0] == "datasets" and parts[2] in DATASET_RUNTIME_DIRS


def _iter_files(root: Path, *roots: str) -> Iterable[Path]:
    for relative_root in roots:
        base = root / relative_root
        if not base.exists():
            continue
        if base.is_file():
            if not _is_skipped(base, root):
                yield base
            continue
        for path in base.rglob("*"):
            if path.is_file() and not _is_skipped(path, root):
                yield path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _line_matches(root: Path, files: Iterable[Path], pattern: re.Pattern[str]) -> list[str]:
    errors: list[str] = []
    for path in files:
        for line_number, line in enumerate(_read_text(path).splitlines(), start=1):
            if pattern.search(line):
                errors.append(f"{_relative(path, root)}:{line_number}: {line.strip()}")
    return errors


def scan_secrets(root: Path) -> list[str]:
    matches = _line_matches(
        root,
        (path for path in _iter_files(root, ".") if path.name != "Makefile"),
        SECRET_PATTERN,
    )
    if matches:
        return ["[check] sensitive literal scan failed", *matches]
    return []


def repo_boundary_check(root: Path) -> list[str]:
    matches = sorted(
        _relative(path, root)
        for path in root.iterdir()
        if path.is_file() and (path.match("tmp_*.txt") or path.match("tmp_*.json"))
    )
    if matches:
        return [
            "[check] root tmp_* files are not allowed; move them to tmp/ or "
            "datasets/<dataset>/presets/",
            *matches,
        ]
    return []


def removed_compat_file_check(root: Path) -> list[str]:
    root_app_names = ("bootstrap", "finalize.py", "loop_", "run_loop")
    removed = [
        path
        for path in (root / "src" / "alpha").iterdir()
        if path.is_file()
        and (
            path.name.startswith(root_app_names[0])
            or path.name == root_app_names[1]
            or path.name.startswith(root_app_names[2])
            or path.name.startswith(root_app_names[3])
        )
    ]
    removed.extend(
        path
        for path in (root / "src" / "alpha" / "app").iterdir()
        if path.is_file() and path.name in {"loop_support.py", "run_loop_state.py"}
    )
    simulation_stages = root / "src" / "alpha" / "core" / "simulation_stages.py"
    if simulation_stages.is_file():
        removed.append(simulation_stages)
    domain_conversion = root / "src" / "alpha" / "models" / "domain_conversion.py"
    if domain_conversion.is_file():
        removed.append(domain_conversion)
    models_runtime = root / "src" / "alpha" / "models" / "runtime.py"
    if models_runtime.is_file():
        removed.append(models_runtime)
    facade_helper = root / "src" / "alpha" / "_facade.py"
    if facade_helper.is_file():
        removed.append(facade_helper)
    constants_facade = root / "src" / "alpha" / "config" / "constants.py"
    if constants_facade.is_file():
        removed.append(constants_facade)
    if removed:
        return [
            "[check] compatibility aggregate files were removed; import concrete modules",
            *(_relative(path, root) for path in sorted(removed)),
        ]
    return []


def compat_import_check(root: Path) -> list[str]:
    errors: list[str] = []
    tests_pattern = re.compile(
        r"from alpha\.models\.base|from alpha\.(bootstrap|run_loop|finalize|loop_)|"
        r"from alpha\.generators\.settings|from alpha\.models\.runtime import|"
        r"from alpha\.(analysis|core|config|generators|io|models|policy|runtime|utils) import"
    )
    errors.extend(
        f"[check] tests should import canonical modules instead of compatibility exports\n{match}"
        for match in _line_matches(root, _iter_files(root, "tests"), tests_pattern)
    )

    root_app_pattern = re.compile(
        r"from alpha\.(bootstrap|bootstrap_cleanup|bootstrap_fields|bootstrap_state|finalize|"
        r"loop_|run_loop)|import alpha\.(bootstrap|bootstrap_cleanup|bootstrap_fields|"
        r"bootstrap_state|finalize|loop_|run_loop)"
    )
    src_files = (
        path
        for path in _iter_files(root, "src/alpha")
        if not _relative(path, root).startswith("src/alpha/app/")
    )
    errors.extend(
        f"[check] internal code should import alpha.app modules instead of root exports\n{match}"
        for match in _line_matches(root, src_files, root_app_pattern)
    )

    settings_pattern = re.compile(
        r"from \.\.generators\.settings|from \.generators\.settings|"
        r"from alpha\.generators\.settings|import alpha\.generators\.settings"
    )
    errors.extend(
        f"[check] import generators.payload/fingerprint/variants instead of generators.settings\n{match}"
        for match in _line_matches(root, _iter_files(root, "src/alpha"), settings_pattern)
    )

    templates_pattern = re.compile(
        r"from \.\.generators\.templates import|from \.generators\.templates import|"
        r"from alpha\.generators\.templates import"
    )
    template_files = (
        path
        for path in _iter_files(root, "src/alpha")
        if _relative(path, root) != "src/alpha/generators/templates/__init__.py"
    )
    errors.extend(
        f"[check] import concrete generators.templates modules instead of compatibility exports\n{match}"
        for match in _line_matches(root, template_files, templates_pattern)
    )

    config_pattern = re.compile(r"from \. import get_yaml_config")
    config_files = (
        path for path in _iter_files(root, "src/alpha/config") if path.name != "__init__.py"
    )
    errors.extend(
        f"[check] internal config modules should import config.yaml instead of package facade\n{match}"
        for match in _line_matches(root, config_files, config_pattern)
    )
    constants_pattern = re.compile(
        r"from alpha\.config\.constants import|from \.{1,3}config\.constants import"
    )
    errors.extend(
        f"[check] import concrete _constants_* modules instead of constants facade\n{match}"
        for match in _line_matches(
            root,
            (*_iter_files(root, "src/alpha"), *_iter_files(root, "tests")),
            constants_pattern,
        )
    )
    errors.extend(
        f"[check] import concrete _constants_* modules instead of constants facade\n{match}"
        for match in _line_matches(
            root,
            _iter_files(root, "src/alpha/config"),
            re.compile(r"from \.constants import"),
        )
    )
    return errors


def arch_boundary_check(root: Path) -> list[str]:
    errors: list[str] = []
    io_analysis_pattern = re.compile(
        r"from \.\.analysis|from alpha\.analysis|import alpha\.analysis"
    )
    io_files = (path for path in _iter_files(root, "src/alpha/io") if path.name != "__init__.py")
    errors.extend(
        f"[check] alpha.io must remain below analysis and cannot import analysis modules\n{match}"
        for match in _line_matches(root, io_files, io_analysis_pattern)
    )

    app_import_pattern = re.compile(
        r"(from alpha\.app(\.| import)|import alpha\.app(\.|$)|from \.\.app(\.| import)|"
        r"from \.app(\.| import))"
    )
    lower_level_files = (
        path
        for path in _iter_files(root, "src/alpha")
        if not _relative(path, root).startswith("src/alpha/app/")
        and path.name not in {"main.py", "__main__.py"}
    )
    errors.extend(
        f"[check] lower-level modules must not import alpha.app orchestration modules\n{match}"
        for match in _line_matches(root, lower_level_files, app_import_pattern)
    )
    return errors


def todo_check(root: Path) -> list[str]:
    matches = _line_matches(root, _iter_files(root, "src", "tests"), re.compile(r"TODO|FIXME|HACK"))
    if matches:
        return [
            "[check] avoid stale TODO/FIXME/HACK comments; document follow-up work explicitly",
            *matches,
        ]
    return []


CHECKS: dict[str, Check] = {
    "scan-secrets": scan_secrets,
    "repo-boundary": repo_boundary_check,
    "removed-compat-file": removed_compat_file_check,
    "compat-import": compat_import_check,
    "arch-boundary": arch_boundary_check,
    "todo": todo_check,
}


def selected_checks(names: list[str]) -> list[str]:
    if not names or names == ["all"]:
        return list(CHECKS)
    unknown = sorted(set(names) - set(CHECKS))
    if unknown:
        raise SystemExit(f"unknown check(s): {', '.join(unknown)}")
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checks", nargs="*", help="checks to run; defaults to all")
    args = parser.parse_args()

    errors: list[str] = []
    for name in selected_checks(args.checks):
        errors.extend(CHECKS[name](ROOT))

    if errors:
        print("\n".join(errors))
        return 1
    print(f"[repo-check] passed {len(selected_checks(args.checks))} check(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
