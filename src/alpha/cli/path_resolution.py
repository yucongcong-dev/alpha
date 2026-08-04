"""
CLI 运行路径归一化与应用辅助模块。
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from ..config.profiles import get_dataset_profile
from ..config.yaml import get_yaml_config
from ..io.common import resolve_datasets_root
from ..io.output_paths import (
    build_dataset_scoped_paths,
    build_output_sidecar_paths,
    resolve_cli_path,
)
from ..models.io_types import RunPaths
from .constants import DEFAULT_CREDS_FILE, DEFAULT_CREDS_KEY_FILE

FILTER_FILE_OPTIONS = {
    "include_fields_file": "--include-fields-file",
    "exclude_fields_file": "--exclude-fields-file",
    "include_templates_file": "--include-templates-file",
    "exclude_templates_file": "--exclude-templates-file",
}
PRESET_CONTROLLED_PATH_KEYS = frozenset(
    {
        "template_library_file",
        "include_fields_file",
        "include_templates_file",
    }
)
RESEARCH_ENTRY_FILE_OPTIONS = {
    "template_library_file": "--template-library-file",
    "include_fields_file": "--include-fields-file",
    "include_templates_file": "--include-templates-file",
}


def _explicit_cli_keys(args: argparse.Namespace) -> frozenset[str]:
    return frozenset(getattr(args, "_explicit_cli_keys", frozenset()))


def _validate_explicit_filter_files(args: argparse.Namespace, paths_by_key: dict[str, str]) -> None:
    explicit_keys = _explicit_cli_keys(args)
    for key, option in FILTER_FILE_OPTIONS.items():
        if key not in explicit_keys:
            continue
        path = paths_by_key.get(key, "")
        if path and not Path(path).is_file():
            raise ValueError(f"{option} does not exist or is not a file: {path}")


def _default_dataset_preset_paths(
    args: argparse.Namespace,
    *,
    datasets_root: str,
) -> dict[str, str]:
    explicit_keys = _explicit_cli_keys(args)
    if explicit_keys & PRESET_CONTROLLED_PATH_KEYS:
        return {}
    if any(str(getattr(args, key, "") or "").strip() for key in PRESET_CONTROLLED_PATH_KEYS):
        return {}

    profile = get_dataset_profile(args.dataset_id, get_yaml_config())
    preset_name = str(profile.get("default_preset", "") or "").strip()
    if not preset_name:
        return {}

    preset_dir = Path(datasets_root) / args.dataset_id / "presets" / preset_name
    paths = {
        "template_library_file": str(preset_dir / "template.json"),
        "include_fields_file": str(preset_dir / "fields.txt"),
        "include_templates_file": str(preset_dir / "templates.txt"),
    }
    missing = [path for path in paths.values() if not Path(path).is_file()]
    if missing:
        raise ValueError(
            f"dataset preset {args.dataset_id}/{preset_name} is incomplete: {', '.join(missing)}"
        )
    return paths


def _validate_paused_dataset(args: argparse.Namespace) -> None:
    """Require an explicit research entry before running a paused dataset."""
    if str(getattr(args, "command", "") or "") == "clean":
        return

    profile = get_dataset_profile(args.dataset_id, get_yaml_config())
    if not bool(profile.get("paused", False)):
        return
    explicit_keys = _explicit_cli_keys(args)
    explicit_research_paths = explicit_keys & PRESET_CONTROLLED_PATH_KEYS
    if explicit_research_paths:
        for key in explicit_research_paths:
            option = RESEARCH_ENTRY_FILE_OPTIONS[key]
            raw_path = str(getattr(args, key, "") or "").strip()
            resolved_path = resolve_cli_path(raw_path, base_dir=os.getcwd())
            if not resolved_path or not Path(resolved_path).is_file():
                raise ValueError(f"{option} must reference an existing file for a paused dataset")
        return

    if "full_run" in explicit_keys and bool(getattr(args, "full_run", False)):
        budget_is_explicit = "max_total_simulations" in explicit_keys
        budget = int(getattr(args, "max_total_simulations", 0) or 0)
        if budget_is_explicit and budget > 0:
            return
        raise ValueError(
            f"dataset {args.dataset_id} is paused; --full-run requires an explicit positive "
            "--max-total-simulations budget"
        )

    raise ValueError(
        f"dataset {args.dataset_id} is paused; provide an explicit template/include file, "
        "or use --full-run with a positive --max-total-simulations budget"
    )


def normalize_args_paths(args: argparse.Namespace) -> RunPaths:
    """按 dataset 上下文解析运行文件路径，但不修改 args 本身。"""
    _validate_paused_dataset(args)
    scoped_paths = build_dataset_scoped_paths(
        args.dataset_id,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
        run_name=str(getattr(args, "run_name", "default") or "default"),
    )
    datasets_root = scoped_paths["datasets_root"] or str(resolve_datasets_root())
    preset_paths = _default_dataset_preset_paths(args, datasets_root=datasets_root)

    template_library_file = (
        resolve_cli_path(args.template_library_file, base_dir=os.getcwd())
        or preset_paths.get("template_library_file", "")
        or scoped_paths["template_library_file"]
    )
    fields_cache_file = (
        resolve_cli_path(args.fields_cache_file, base_dir=os.getcwd())
        or scoped_paths["fields_cache_file"]
    )
    output_file = resolve_cli_path(args.output, base_dir=os.getcwd()) or scoped_paths["output"]
    feedback_output = (
        resolve_cli_path(args.feedback_output, base_dir=os.getcwd())
        or scoped_paths["feedback_output"]
    )
    creds_file = resolve_cli_path(args.creds_file, base_dir=os.getcwd()) or DEFAULT_CREDS_FILE
    creds_key_file = (
        resolve_cli_path(args.creds_key_file, base_dir=os.getcwd()) or DEFAULT_CREDS_KEY_FILE
    )
    include_fields_file = resolve_cli_path(
        args.include_fields_file, base_dir=os.getcwd()
    ) or preset_paths.get("include_fields_file", "")
    exclude_fields_file = resolve_cli_path(args.exclude_fields_file, base_dir=os.getcwd())
    include_templates_file = resolve_cli_path(
        args.include_templates_file, base_dir=os.getcwd()
    ) or preset_paths.get("include_templates_file", "")
    exclude_templates_file = resolve_cli_path(args.exclude_templates_file, base_dir=os.getcwd())
    _validate_explicit_filter_files(
        args,
        {
            "include_fields_file": include_fields_file,
            "exclude_fields_file": exclude_fields_file,
            "include_templates_file": include_templates_file,
            "exclude_templates_file": exclude_templates_file,
        },
    )

    sidecar_paths = build_output_sidecar_paths(output_file)
    log_file = resolve_cli_path(args.log_file, base_dir=os.getcwd()) or sidecar_paths["run_log"]
    results_dir = str(Path(output_file).parent)
    output_dir = Path(output_file).parent
    if Path(output_file).name.lower() == "summary.json":
        state_file = str(output_dir / "state.json")
        checkpoint_file = str(output_dir / "interrupt_report.json")
    else:
        output_stem = Path(output_file).stem
        state_file = str(output_dir / f"{output_stem}_state.json")
        checkpoint_file = str(output_dir / f"{output_stem}_interrupt_report.json")

    return RunPaths(
        results_dir=results_dir,
        log_file=log_file,
        state_file=state_file,
        checkpoint_file=checkpoint_file,
        datasets_root=datasets_root,
        fields_cache_file=fields_cache_file,
        template_library_file=template_library_file,
        output=output_file,
        feedback_output=feedback_output,
        creds_file=creds_file,
        creds_key_file=creds_key_file,
        include_fields_file=include_fields_file,
        exclude_fields_file=exclude_fields_file,
        include_templates_file=include_templates_file,
        exclude_templates_file=exclude_templates_file,
    )


def apply_run_paths(args: argparse.Namespace, run_paths: RunPaths) -> None:
    """把归一化后的关键路径显式同步回 args，供旧调用链兼容使用。"""
    args.output = run_paths.output
    args.log_file = run_paths.log_file
    args.state_file = run_paths.state_file
    args.checkpoint_file = run_paths.checkpoint_file
    args.fields_cache_file = run_paths.fields_cache_file
    args.template_library_file = run_paths.template_library_file
    args.feedback_output = run_paths.feedback_output
    args.creds_file = run_paths.creds_file
    args.creds_key_file = run_paths.creds_key_file
    args.include_fields_file = run_paths.include_fields_file
    args.exclude_fields_file = run_paths.exclude_fields_file
    args.include_templates_file = run_paths.include_templates_file
    args.exclude_templates_file = run_paths.exclude_templates_file
