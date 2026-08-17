"""CLI parser schema assembly."""

from __future__ import annotations

import argparse
from typing import Any

from .parser_sections import (
    add_api_runtime_arguments,
    add_base_arguments,
    add_credentials_arguments,
    add_dataset_arguments,
    add_file_filter_arguments,
    add_output_logging_arguments,
    add_pending_check_refresh_arguments,
    add_precheck_arguments,
    add_run_mode_arguments,
    add_search_arguments,
)

_COMMANDS = frozenset({"run", "clean", "check-submissions"})
_CLEAN_HELP_DESTS = frozenset(
    {
        "command",
        "config",
        "dataset_id",
        "include_credentials",
        "all_datasets",
        "confirm_clean",
        "dry_run_clean",
    }
)
_CHECK_SUBMISSIONS_HELP_DESTS = frozenset(
    {
        "command",
        "config",
        "creds_file",
        "creds_key_file",
        "email",
        "password",
        "dataset_id",
        "min_request_interval",
        "rate_limit_max_retries",
        "login_retries",
        "check_submission_retries",
        "pending_check_limit",
        "pending_check_max_seconds",
        "pending_check_workers",
        "feedback_output",
        "output",
        "run_name",
        "verbose",
        "quiet",
        "log_file",
    }
)


class _CommandHelpProxy:
    """Apply command-specific help visibility while preserving parse compatibility."""

    def __init__(
        self,
        container: Any,
        visible_dests: frozenset[str] | None,
    ) -> None:
        self._container = container
        self._visible_dests = visible_dests

    def _destination(self, args: tuple[object, ...], kwargs: dict[str, object]) -> str:
        explicit_dest = kwargs.get("dest")
        if isinstance(explicit_dest, str):
            return explicit_dest
        for argument in args:
            if isinstance(argument, str) and not argument.startswith("-"):
                return argument
        for argument in args:
            if isinstance(argument, str) and argument.startswith("--"):
                return argument[2:].split("=", 1)[0].replace("-", "_")
        return ""

    def add_argument(self, *args: object, **kwargs: object) -> object:
        if (
            self._visible_dests is not None
            and self._destination(args, kwargs) not in self._visible_dests
        ):
            kwargs["help"] = argparse.SUPPRESS
        return self._container.add_argument(*args, **kwargs)

    def add_argument_group(self, *args: object, **kwargs: object) -> _CommandHelpProxy:
        group = self._container.add_argument_group(*args, **kwargs)
        return _CommandHelpProxy(group, self._visible_dests)

    def add_mutually_exclusive_group(
        self,
        **kwargs: object,
    ) -> _CommandHelpProxy | _ConditionalMutexProxy:
        if self._visible_dests is None:
            group = self._container.add_mutually_exclusive_group(**kwargs)
            return _CommandHelpProxy(group, self._visible_dests)
        return _ConditionalMutexProxy(self._container, self._visible_dests, kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._container, name)


class _ConditionalMutexProxy:
    """Avoid empty hidden mutex groups in command-specific help output."""

    def __init__(
        self,
        container: Any,
        visible_dests: frozenset[str],
        kwargs: dict[str, object],
    ) -> None:
        self._container = container
        self._visible_dests = visible_dests
        self._kwargs = kwargs
        self._group: _CommandHelpProxy | None = None

    def add_argument(self, *args: object, **kwargs: object) -> object:
        destination = _CommandHelpProxy(self._container, self._visible_dests)._destination(
            args,
            kwargs,
        )
        if destination not in self._visible_dests:
            kwargs["help"] = argparse.SUPPRESS
            return self._container.add_argument(*args, **kwargs)
        if self._group is None:
            group = self._container.add_mutually_exclusive_group(**self._kwargs)
            self._group = _CommandHelpProxy(group, self._visible_dests)
        return self._group.add_argument(*args, **kwargs)


def collect_parser_defaults(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Collect argparse dest -> default value mapping."""
    defaults: dict[str, Any] = {}
    for action in parser._actions:
        dest = getattr(action, "dest", None)
        if not dest or dest == "help":
            continue
        defaults[dest] = action.default
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


def command_from_argv(
    argv: list[str],
    *,
    parser: argparse.ArgumentParser | None = None,
) -> str:
    """Return the selected positional command while preserving implicit ``run``.

    Scan using argparse's action metadata so option values such as
    ``--run-name clean`` are not mistaken for the command token.
    """
    parser = parser or build_parser()
    option_actions = {
        option: action for action in parser._actions for option in action.option_strings
    }
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


def build_parser(*, command: str | None = None) -> argparse.ArgumentParser:
    """Build the compatibility parser with command-specific help visibility.

    Options outside the active command's help remain accepted temporarily so
    existing scripts keep working while the typed configuration boundary is
    shared by all commands.
    """
    parser = argparse.ArgumentParser(
        prog="alpha",
        description=(
            "测试 WorldQuant Brain 数据集中的所有字段并筛选可提交的 Alpha。"
            "使用 `alpha <command> --help` 查看该命令的参数。"
        ),
        allow_abbrev=False,
    )
    visible_dests = (
        _CLEAN_HELP_DESTS
        if command == "clean"
        else _CHECK_SUBMISSIONS_HELP_DESTS
        if command == "check-submissions"
        else None
    )
    command_parser = _CommandHelpProxy(parser, visible_dests)
    add_base_arguments(command_parser)
    add_credentials_arguments(command_parser)
    add_dataset_arguments(command_parser)
    add_run_mode_arguments(command_parser)
    add_search_arguments(command_parser)
    add_file_filter_arguments(command_parser)
    add_api_runtime_arguments(command_parser)
    add_pending_check_refresh_arguments(command_parser)
    add_precheck_arguments(command_parser)
    add_output_logging_arguments(command_parser)
    return parser
