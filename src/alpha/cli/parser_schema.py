"""Command-specific CLI parser assembly and compatibility handling."""

from __future__ import annotations

import argparse
from typing import Any
import warnings

from .parser_sections import (
    add_api_runtime_arguments,
    add_base_arguments,
    add_clean_arguments,
    add_credentials_arguments,
    add_dataset_arguments,
    add_dataset_context_arguments,
    add_dataset_selector_arguments,
    add_feedback_output_argument,
    add_file_filter_arguments,
    add_output_logging_arguments,
    add_pending_check_refresh_arguments,
    add_precheck_arguments,
    add_run_mode_arguments,
    add_search_arguments,
    add_submission_check_api_arguments,
)

_COMMANDS = frozenset({"run", "clean", "check-submissions"})
_DEPRECATED_OPTIONS = {
    "--smoke-test": "--run-mode smoke",
    "--no-smoke-test": "--run-mode normal",
    "--full-run": "--run-mode full",
    "--no-full-run": "--run-mode normal",
    "--legacy-similarity-penalty": "--similarity-penalty",
}


def _new_parser(*, description: str, add_help: bool = True) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="alpha",
        description=description,
        allow_abbrev=False,
        add_help=add_help,
    )


def _build_parser_for_command(command: str) -> argparse.ArgumentParser:
    """Build the strict parser for exactly one command.

    The command is represented by a one-choice positional argument instead of
    an argparse subparser.  This keeps the long-standing ``alpha --limit 10``
    implicit-run form while making each explicit command's accepted options
    and help output independent.
    """
    if command not in _COMMANDS:
        raise ValueError(f"unsupported command: {command}")

    parser = _new_parser(
        description=(
            "测试 WorldQuant Brain 数据集中的所有字段并筛选可提交的 Alpha。"
            "可用命令：run（默认）、clean、check-submissions。"
            if command == "run"
            else (
                "清理 Alpha Runner 的本地运行产物。"
                if command == "clean"
                else "刷新已有 Alpha 的 Submission Check，不创建新的 simulation。"
            )
        )
    )
    add_base_arguments(parser, command=command)

    if command == "run":
        add_credentials_arguments(parser)
        add_dataset_arguments(parser)
        add_run_mode_arguments(parser)
        add_search_arguments(parser)
        add_file_filter_arguments(parser)
        add_api_runtime_arguments(parser)
        add_pending_check_refresh_arguments(parser)
        add_precheck_arguments(parser)
        add_output_logging_arguments(parser)
        return parser

    if command == "clean":
        add_dataset_selector_arguments(parser)
        add_clean_arguments(parser)
        return parser

    # check-submissions intentionally exposes only controls that affect the
    # refresh request. Its namespace still receives run defaults below so the
    # shared ApplicationConfig boundary remains stable for old callers.
    add_credentials_arguments(parser)
    add_dataset_context_arguments(parser)
    add_submission_check_api_arguments(parser)
    add_pending_check_refresh_arguments(parser)
    add_feedback_output_argument(parser)
    add_output_logging_arguments(parser)
    return parser


def _run_parser_defaults() -> dict[str, Any]:
    """Return defaults for fields consumed by the shared config boundary."""
    return collect_parser_defaults(_build_parser_for_command("run"))


def _add_compatibility_defaults(parser: argparse.ArgumentParser) -> None:
    """Seed non-run parsers with non-CLI runtime defaults.

    These are parser defaults, not hidden options: a clean/check command cannot
    accidentally configure a run-only setting, but typed config construction
    can still rely on one complete namespace shape.
    """
    existing = collect_parser_defaults(parser)
    parser.set_defaults(
        **{key: value for key, value in _run_parser_defaults().items() if key not in existing}
    )


def build_legacy_options_parser() -> argparse.ArgumentParser:
    """Build an option-only parser for old scripts using cross-command flags.

    It is deliberately not used for help or normal parsing. ``parse_args``
    invokes it only for options rejected by the active command parser, then
    preserves their historical values while emitting a deprecation warning.
    """
    parser = _new_parser(description="兼容旧版 alpha 参数", add_help=False)
    add_credentials_arguments(parser)
    add_dataset_arguments(parser)
    add_run_mode_arguments(parser)
    add_search_arguments(parser)
    add_file_filter_arguments(parser)
    add_api_runtime_arguments(parser)
    add_pending_check_refresh_arguments(parser)
    add_precheck_arguments(parser)
    add_output_logging_arguments(parser)
    add_clean_arguments(parser)
    return parser


def build_parser(*, command: str | None = None) -> argparse.ArgumentParser:
    """Build a strict parser for ``command`` (implicit ``run`` by default)."""
    active_command = command or "run"
    parser = _build_parser_for_command(active_command)
    if active_command != "run":
        _add_compatibility_defaults(parser)
    return parser


def collect_parser_defaults(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Collect the values argparse produces when no options are supplied."""
    # argparse keeps parser-level defaults separately and applies the first
    # action for a destination. Using setdefault preserves that behavior for
    # aliases, whose later action defaults are commonly ``None``.
    defaults: dict[str, Any] = dict(parser._defaults)
    for action in parser._actions:
        if not action.dest or action.dest == "help" or action.default is argparse.SUPPRESS:
            continue
        defaults.setdefault(action.dest, action.default)
    return defaults


def collect_explicit_cli_options(parser: argparse.ArgumentParser, argv: list[str]) -> set[str]:
    """Collect raw option strings explicitly provided on the command line."""
    known_options = {option for action in parser._actions for option in action.option_strings}
    return {token.split("=", 1)[0] for token in argv if token.split("=", 1)[0] in known_options}


def collect_explicit_cli_keys(parser: argparse.ArgumentParser, argv: list[str]) -> set[str]:
    """Collect argparse destination names explicitly provided on the command line."""
    explicit_keys: set[str] = set()
    option_to_dest = {
        option: action.dest for action in parser._actions for option in action.option_strings
    }
    for token in argv:
        option = token.split("=", 1)[0]
        dest = option_to_dest.get(option)
        if dest:
            explicit_keys.add(dest)
    return explicit_keys


def _option_actions(parser: argparse.ArgumentParser) -> dict[str, argparse.Action]:
    return {option: action for action in parser._actions for option in action.option_strings}


def command_from_argv(
    argv: list[str],
    *,
    parser: argparse.ArgumentParser | None = None,
) -> str:
    """Return the selected command while preserving implicit ``run``.

    ``parser`` remains an optional compatibility hook. The default scanner
    uses the option-only compatibility schema so values such as
    ``--run-name clean`` can never be mistaken for a command token.
    """
    parser = parser or build_legacy_options_parser()
    option_actions = _option_actions(parser)
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--":
            remaining = argv[index + 1 :]
            return next((item for item in remaining if item in _COMMANDS), "run")
        if not token.startswith("-"):
            if token in _COMMANDS:
                return token
            index += 1
            continue

        option, has_inline_value, _inline_value = token.partition("=")
        action = option_actions.get(option)
        if has_inline_value or action is None:
            if (
                not has_inline_value
                and index + 1 < len(argv)
                and not argv[index + 1].startswith("-")
            ):
                index += 2
            else:
                index += 1
            continue
        if action.nargs == 0:
            index += 1
        elif action.nargs in (None, 1, "?"):
            index += 2 if index + 1 < len(argv) and not argv[index + 1].startswith("-") else 1
        else:
            index += 1
            while index < len(argv) and not argv[index].startswith("-"):
                index += 1
    return "run"


def warn_deprecated_options(options: set[str]) -> None:
    """Emit one actionable warning for each legacy option used."""
    for option in sorted(options & _DEPRECATED_OPTIONS.keys()):
        replacement = _DEPRECATED_OPTIONS[option]
        warnings.warn(
            f"{option} 已废弃，请改用 {replacement}。",
            DeprecationWarning,
            stacklevel=3,
        )
