"""CLI parsing boundary."""

from __future__ import annotations

import argparse
import sys

from ..config.application import ApplicationConfig, CleanConfig, CommandConfig
from .arg_resolution import resolve_cli_args
from .parser_schema import (
    build_legacy_options_parser,
    build_parser,
    collect_explicit_cli_keys,
    collect_explicit_cli_options,
    collect_parser_defaults,
    command_from_argv,
    warn_deprecated_options,
)
from .path_resolution import normalize_args_paths as _normalize_args_paths


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments and apply YAML/profile/run-mode overrides."""
    argv = sys.argv[1:]
    command = command_from_argv(argv)
    parser = build_parser(command=command)

    parser_defaults = collect_parser_defaults(parser)
    explicit_cli_keys = collect_explicit_cli_keys(parser, argv)
    explicit_cli_options = collect_explicit_cli_options(parser, argv)
    args, legacy_argv = parser.parse_known_args(argv)
    if legacy_argv:
        if command != "run":
            parser.error(f"unrecognized arguments for {command}: {' '.join(legacy_argv)}")
        legacy_parser = build_legacy_options_parser()
        legacy_args = legacy_parser.parse_args(legacy_argv)
        legacy_keys = collect_explicit_cli_keys(legacy_parser, legacy_argv)
        legacy_options = collect_explicit_cli_options(legacy_parser, legacy_argv)
        for key in legacy_keys:
            setattr(args, key, getattr(legacy_args, key))
        explicit_cli_keys.update(legacy_keys)
        explicit_cli_options.update(legacy_options)
    warn_deprecated_options(explicit_cli_options)
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
