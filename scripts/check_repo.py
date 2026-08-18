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
    domain_codecs = root / "src" / "alpha" / "models" / "domain_codecs.py"
    if domain_codecs.is_file():
        removed.append(domain_codecs)
    models_runtime = root / "src" / "alpha" / "models" / "runtime.py"
    if models_runtime.is_file():
        removed.append(models_runtime)
    facade_helper = root / "src" / "alpha" / "_facade.py"
    if facade_helper.is_file():
        removed.append(facade_helper)
    removed_constants = [
        root / "src" / "alpha" / "config" / name
        for name in (
            "_constants_api.py",
            "_constants_strings.py",
            "_constants_thresholds.py",
            "_constants_templates.py",
        )
    ]
    removed.extend(path for path in removed_constants if path.is_file())
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
        r"from alpha\.config\._constants_(api|strings|thresholds|templates)|"
        r"from \.{1,3}config\._constants_(api|strings|thresholds|templates)"
    )
    errors.extend(
        f"[check] import alpha.config.static_config instead of removed _constants_* modules\n{match}"
        for match in _line_matches(
            root,
            (*_iter_files(root, "src/alpha"), *_iter_files(root, "tests")),
            constants_pattern,
        )
    )
    errors.extend(
        f"[check] import alpha.config.static_config instead of removed _constants_* modules\n{match}"
        for match in _line_matches(
            root,
            _iter_files(root, "src/alpha/config"),
            re.compile(r"from \._constants_(api|strings|thresholds|templates)"),
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


def dead_symbols_check(root: Path) -> list[str]:
    """Flag module-level names defined in src/alpha that are never referenced.

    Counts real code references (Name nodes, attribute accesses, and import
    aliases) across src, tests, and scripts. Names listed in any ``__all__``
    are treated as an explicit re-export contract and skipped. Dynamic string
    references the AST cannot see (for example ``monkeypatch.setattr`` paths)
    must import the symbol instead so it remains visible to this check.
    """
    import ast
    from collections import Counter

    def _iter_py(*roots: str):
        for path in _iter_files(root, *roots):
            if path.suffix == ".py":
                yield path

    reference_counts: Counter[str] = Counter()
    for path in _iter_py("src", "tests", "scripts"):
        try:
            tree = ast.parse(_read_text(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                reference_counts[node.id] += 1
            elif isinstance(node, ast.Attribute):
                reference_counts[node.attr] += 1
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    reference_counts[alias.asname or alias.name.split(".")[0]] += 1
                    if alias.asname:
                        reference_counts[alias.name.split(".")[0]] += 1
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    reference_counts[alias.asname or alias.name] += 1
                    if alias.asname:
                        reference_counts[alias.name] += 1

    exported: set[str] = set()
    for path in _iter_py("src", "tests", "scripts"):
        try:
            tree = ast.parse(_read_text(path))
        except SyntaxError:
            continue
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
                and isinstance(node.value, (ast.List, ast.Tuple))
            ):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        exported.add(elt.value)

    errors: list[str] = []
    for path in _iter_py("src/alpha"):
        try:
            tree = ast.parse(_read_text(path))
        except SyntaxError:
            continue
        for node in tree.body:
            defined: list[str] = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined = [node.name]
            elif isinstance(node, ast.Assign):
                defined = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                defined = [node.target.id]
            for name in defined:
                if name.startswith("__") or name in exported:
                    continue
                definition_occurrences = 1 if isinstance(node, (ast.Assign, ast.AnnAssign)) else 0
                if reference_counts[name] <= definition_occurrences:
                    errors.append(
                        f"{_relative(path, root)}:{node.lineno}: {name} is defined "
                        "but never referenced"
                    )
    if errors:
        return ["[check] dead module-level symbols in src/alpha", *errors]
    return []


def acl_boundary_check(root: Path) -> list[str]:
    """Domain dataclasses may only be constructed in anti-corruption modules.

    Raw API/config payloads must enter the domain through the documented ACL
    (models/domain_parsers.py, core/simulation_parsing.py,
    analysis/results_loader.py, generators/templates/library_loader.py) plus the
    domain-owned factories. New raw-to-domain conversions must extend one of
    those modules instead of constructing domain types in arbitrary places.
    """
    import ast

    domain_types = {
        "FailedCheck",
        "FieldTestResult",
        "SettingsVariant",
        "TemplateField",
        "TemplateLibraryItem",
        "FieldTestContext",
        "TemplateCandidate",
    }
    allowed_modules = {
        "src/alpha/models/domain.py",
        "src/alpha/models/domain_parsers.py",
        "src/alpha/core/simulation_parsing.py",
        "src/alpha/core/simulation_results.py",
        "src/alpha/core/simulation.py",
        "src/alpha/analysis/results_loader.py",
        "src/alpha/generators/templates/library_loader.py",
        "src/alpha/generators/templates/candidates.py",
        "src/alpha/app/bootstrap_field_selection.py",
        "src/alpha/app/bootstrap_field_quality.py",
        "src/alpha/app/planning.py",
    }
    errors: list[str] = []
    for path in _iter_files(root, "src/alpha"):
        if not path.name.endswith(".py"):
            continue
        rel = _relative(path, root)
        if rel in allowed_modules:
            continue
        try:
            tree = ast.parse(_read_text(path))
        except SyntaxError:
            continue
        errors.extend(
            f"{rel}:{node.lineno}: {node.func.id} constructed outside the ACL; "
            "route raw payloads through models/domain_parsers.py or an existing ACL module"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in domain_types
        )
    if errors:
        return ["[check] domain types must only be constructed in ACL modules", *sorted(errors)]
    return []


def config_binding_check(root: Path) -> list[str]:
    """Only the CLI dispatcher may bind ``--config`` from raw argv.

    Import-time YAML-backed constants resolve against whichever config is active
    when their module first loads, so ``alpha.main.run_cli_entry`` binds the
    explicit settings file before dispatch imports the application modules.
    ``alpha.__main__`` must remain limited to interpreter/logging setup and
    delegation. Binding elsewhere re-introduces an import-order side effect.
    """
    binding_pattern = re.compile(r"activate_config_from_argv\(\)")
    entry_files = (
        path
        for path in _iter_files(root, "src/alpha")
        if path.name not in {"__main__.py", "main.py"} and path.suffix == ".py"
    )
    errors: list[str] = []
    matches = _line_matches(root, entry_files, binding_pattern)
    if matches:
        errors.append(
            "[check] --config binding must happen only in src/alpha/main.py; "
            "module-level activate_config_from_argv() re-introduces import side effects"
        )
        errors.extend(matches)

    main_import_pattern = re.compile(r"from alpha\.main import|import alpha\.main")
    non_entry_files = (
        path
        for path in _iter_files(root, "src/alpha")
        if path.name not in {"__main__.py", "main.py"} and path.suffix == ".py"
    )
    matches = _line_matches(root, non_entry_files, main_import_pattern)
    if matches:
        errors.append(
            "[check] alpha.main may only be imported from the CLI entrypoint src/alpha/__main__.py"
        )
        errors.extend(matches)
    return errors


def config_consistency_check(root: Path) -> list[str]:
    """Validate mirrored overrides and unique canonical default-section ownership.

    Import-time constants and runtime values resolve the same logical keys
    through different YAML layers (the global.* override wins over the flat
    defaults). Keys present in both layers must stay identical so the shadowed
    default cannot silently drift from the effective setting.
    """
    import yaml  # delayed import to keep check_repo.py self-contained

    def _flatten(d: object, prefix: str = "") -> dict[str, object]:
        out: dict[str, object] = {}
        if not isinstance(d, dict):
            return out
        for key, value in d.items():
            full_key = f"{prefix}{key}"
            if isinstance(value, dict):
                out.update(_flatten(value, f"{full_key}."))
            else:
                out[full_key] = value
        return out

    settings_leaves: dict[str, object] = {}
    settings_path = root / "config" / "settings.yaml"
    if settings_path.is_file():
        try:
            settings = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return [f"[check] failed to parse settings.yaml: {exc}"]
        global_section = settings.get("global")
        if isinstance(global_section, dict):
            settings_leaves = _flatten(global_section)

    defaults_leaves: dict[str, object] = {}
    default_section_owners: dict[str, list[str]] = {}
    for name in ("constants_defaults.yaml", "quality_feedback.yaml", "templates.yaml"):
        config_file = root / "config" / name
        if not config_file.is_file():
            continue
        try:
            data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            for section in data:
                default_section_owners.setdefault(str(section), []).append(name)
            defaults_leaves.update(_flatten(data))

    errors: list[str] = []
    errors.extend(
        f"[check] default YAML section '{section}' is defined by "
        f"{', '.join(owners)}; keep one canonical owner to avoid order-dependent overrides"
        for section, owners in sorted(default_section_owners.items())
        if len(owners) > 1
    )
    for key in sorted(settings_leaves.keys() & defaults_leaves.keys()):
        settings_value = settings_leaves[key]
        defaults_value = defaults_leaves[key]
        if settings_value != defaults_value:
            errors.append(
                f"[check] config key '{key}' differs between settings.yaml global.* "
                f"({settings_value!r}) and flat defaults ({defaults_value!r}); "
                "update both files to keep the effective value and fallback in sync"
            )
    return errors


def strategy_tuning_keys_check(root: Path) -> list[str]:
    """Validate that every tuning_key in strategy_profiles.yaml resolves to a real config path."""
    import yaml  # delayed import to keep check_repo.py self-contained for non-yaml checks

    errors: list[str] = []
    strategy_path = root / "config" / "strategy_profiles.yaml"
    if not strategy_path.is_file():
        return []

    try:
        strategies = yaml.safe_load(strategy_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"[check] failed to parse strategy_profiles.yaml: {exc}"]

    config_paths = {
        "expression_policies.yaml",
        "settings.yaml",
        "templates.yaml",
        "quality_feedback.yaml",
        "dataset_profiles.yaml",
        "constants_defaults.yaml",
    }
    merged: dict[str, object] = {}
    for name in config_paths:
        config_file = root / "config" / name
        if not config_file.is_file():
            continue
        try:
            data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            merged[name] = data

    def _flatten(d: object, prefix: str = "") -> set[str]:
        keys: set[str] = set()
        if not isinstance(d, dict):
            return keys
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else str(k)
            keys.add(full)
            if isinstance(v, dict):
                keys.update(_flatten(v, full))
        return keys

    all_config_keys: set[str] = set()
    for data in merged.values():
        all_config_keys.update(_flatten(data))

    for profile_name, profile in strategies.get("strategy_profiles", {}).items():
        tuning = profile.get("tuning_keys")
        if not isinstance(tuning, dict):
            continue
        for section, keys in tuning.items():
            if not isinstance(keys, list):
                continue
            for key in keys:
                if not isinstance(key, str):
                    continue
                # Check if key exists anywhere in the merged config
                # The lookup logic mirrors _yaml_val: global.<key> first, then flat <key>
                if key in all_config_keys:
                    continue
                if any(
                    k.endswith(f".{key}") or k.endswith(f".global.{key}") for k in all_config_keys
                ):
                    continue
                # Also check as a sub-path (e.g. quality.min_sharpe might be quality_feedback.quality.min_sharpe)
                found = False
                for ck in all_config_keys:
                    if ck.endswith(f".{key}"):
                        found = True
                        break
                if not found:
                    errors.append(
                        f"[check] strategy_profiles.yaml: {profile_name}.tuning_keys.{section}.{key} "
                        f"not found in any config file"
                    )
    return errors


CHECKS: dict[str, Check] = {
    "scan-secrets": scan_secrets,
    "repo-boundary": repo_boundary_check,
    "removed-compat-file": removed_compat_file_check,
    "compat-import": compat_import_check,
    "arch-boundary": arch_boundary_check,
    "todo": todo_check,
    "dead-symbols": dead_symbols_check,
    "acl-boundary": acl_boundary_check,
    "config-binding": config_binding_check,
    "config-consistency": config_consistency_check,
    "strategy-tuning-keys": strategy_tuning_keys_check,
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
