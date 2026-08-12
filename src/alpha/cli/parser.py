"""CLI parsing boundary."""

from __future__ import annotations

import argparse
import sys

from ..config.application import ApplicationConfig, CleanConfig, CommandConfig
from .arg_resolution import resolve_cli_args
from .parser_schema import (
    build_parser,
    collect_explicit_cli_keys,
    collect_explicit_cli_options,
    collect_parser_defaults,
)
from .path_resolution import normalize_args_paths as _normalize_args_paths


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments and apply YAML/profile/run-mode overrides."""
    parser = build_parser()

    parser_defaults = collect_parser_defaults(parser)
    explicit_cli_keys = collect_explicit_cli_keys(parser, sys.argv[1:])
    explicit_cli_options = collect_explicit_cli_options(parser, sys.argv[1:])
    args = parser.parse_args()
    args._explicit_cli_keys = frozenset(explicit_cli_keys)
    args._explicit_cli_options = frozenset(explicit_cli_options)
    if args.command == "clean":
        return args
    return resolve_cli_args(
        args,
        parser_defaults=parser_defaults,
        explicit_cli_keys=explicit_cli_keys,
        explicit_cli_options=explicit_cli_options,
    )


def parse_application_config() -> CommandConfig:
    """Parse CLI input and cross the boundary into immutable runtime config."""
    args = parse_args()
    if args.command == "clean":
        return CleanConfig.from_args(args)
    run_paths = _normalize_args_paths(args)
    return ApplicationConfig.from_args(args, run_paths)
