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
    add_precheck_arguments,
    add_run_mode_arguments,
    add_search_arguments,
)


def collect_parser_defaults(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Collect argparse dest -> default value mapping."""
    defaults: dict[str, Any] = {}
    for action in parser._actions:
        dest = getattr(action, "dest", None)
        if not dest or dest == "help":
            continue
        defaults[dest] = action.default
    return defaults


def collect_explicit_cli_keys(parser: argparse.ArgumentParser, argv: list[str]) -> set[str]:
    """Collect argparse destination names explicitly provided on the command line."""
    explicit_keys: set[str] = set()
    option_to_dest = {
        option: action.dest
        for action in parser._actions
        for option in action.option_strings
    }
    for token in argv:
        option = token.split("=", 1)[0]
        dest = option_to_dest.get(option)
        if dest:
            explicit_keys.add(dest)
    return explicit_keys


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        prog="alpha",
        description="测试 WorldQuant Brain 数据集中的所有字段并筛选可提交的 Alpha。",
    )
    add_base_arguments(parser)
    add_credentials_arguments(parser)
    add_dataset_arguments(parser)
    add_run_mode_arguments(parser)
    add_search_arguments(parser)
    add_file_filter_arguments(parser)
    add_api_runtime_arguments(parser)
    add_precheck_arguments(parser)
    add_output_logging_arguments(parser)
    return parser
