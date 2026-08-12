"""Grouped CLI argument section builders."""

from __future__ import annotations

import argparse
import os

from ..config._constants_thresholds import DEFAULT_DATASET_ID
from ..config.settings_spec import SettingSpec, get_setting, settings_by_yaml_section
from .constants import DEFAULT_CREDS_FILE, DEFAULT_CREDS_KEY_FILE


def add_bool_argument(
    parser: argparse.ArgumentParser,
    name: str,
    *,
    dest: str,
    default: bool = False,
    help_enable: str,
    help_disable: str,
) -> None:
    """Add a boolean CLI option pair that can both enable and disable YAML defaults."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(name, action="store_true", dest=dest, default=default, help=help_enable)
    positive_name = name[2:] if name.startswith("--") else name
    group.add_argument(
        f"--no-{positive_name}",
        action="store_false",
        dest=dest,
        default=default,
        help=help_disable,
    )


def add_settings(parser: argparse.ArgumentParser, specs: tuple[SettingSpec, ...]) -> None:
    """从声明式设置表生成一组 argparse 参数。"""
    for spec in specs:
        assert spec.cli is not None
        if spec.kind == "bool_pair":
            add_bool_argument(
                parser,
                spec.cli,
                dest=spec.dest,
                default=spec.default,
                help_enable=spec.help,
                help_disable=spec.help_disable,
            )
            continue
        parser.add_argument(
            spec.cli,
            dest=spec.dest,
            default=spec.default,
            type=spec.arg_type,
            choices=spec.choices or None,
            help=spec.help,
        )


def add_base_arguments(parser: argparse.ArgumentParser) -> None:
    """Add command and config arguments."""
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run", "clean"),
        default="run",
        help=("运行命令：run=执行 Alpha 流程（默认），clean=清理本地运行文件"),
    )
    parser.add_argument(
        "--config",
        default="",
        help="YAML 配置文件路径（留空自动搜索 config/settings.yaml）。所有参数可在此文件中配置。",
    )


def add_credentials_arguments(parser: argparse.ArgumentParser) -> None:
    """Add credential source arguments."""
    parser.add_argument("--creds-file", default=DEFAULT_CREDS_FILE, help="本地 JSON 凭证文件路径")
    parser.add_argument(
        "--creds-key-file",
        default=DEFAULT_CREDS_KEY_FILE,
        help="用于加密/解密凭证文件的密钥文件路径",
    )
    parser.add_argument("--email", default=os.getenv("WQB_EMAIL"), help="用户邮箱")
    parser.add_argument("--password", default=os.getenv("WQB_PASSWORD"), help="用户密码")


def add_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    """Add dataset and simulation settings arguments."""
    parser.add_argument(
        "--dataset-id",
        default=DEFAULT_DATASET_ID,
        help="数据集 ID；run/clean 命令必须显式指定",
    )
    add_settings(parser, settings_by_yaml_section("simulation"))


def add_run_mode_arguments(parser: argparse.ArgumentParser) -> None:
    """Add run-mode toggles."""
    add_settings(parser, (get_setting("strategy_profile"),))
    run_mode = get_setting("run_mode")
    run_mode_group = parser.add_mutually_exclusive_group()
    run_mode_group.add_argument(
        "--run-mode",
        choices=run_mode.choices,
        dest="run_mode",
        default=run_mode.default,
        help=run_mode.help,
    )
    # 兼容旧脚本的隐藏别名；新代码请使用 --run-mode。
    run_mode_group.add_argument(
        "--smoke-test",
        action="store_true",
        dest="smoke_test",
        default=False,
        help=argparse.SUPPRESS,
    )
    run_mode_group.add_argument(
        "--full-run",
        action="store_true",
        dest="full_run",
        default=False,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-smoke-test",
        action="store_false",
        dest="smoke_test",
        default=False,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-full-run",
        action="store_false",
        dest="full_run",
        default=False,
        help=argparse.SUPPRESS,
    )


def add_search_arguments(parser: argparse.ArgumentParser) -> None:
    """Add field/template search-space arguments."""
    add_settings(parser, settings_by_yaml_section("limits"))


def add_file_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """Add template/data file and include/exclude filter arguments."""
    parser.add_argument(
        "--template-library-file",
        default="",
        help="本地 JSON 模板库文件路径；留空则根据 dataset_id 自动选择",
    )
    parser.add_argument(
        "--feedback-output", default="", help="用于反馈排序的历史结果 JSON 文件；默认使用 --output"
    )
    parser.add_argument(
        "--fields-cache-file",
        default="",
        help="本地 JSON 字段缓存文件路径（留空则根据 dataset_id 自动生成）",
    )
    add_settings(parser, (get_setting("dry_run_plan"),))
    parser.add_argument(
        "--include-fields-file", default="", help="包含字段 ID/名称的文本文件，每行一个"
    )
    parser.add_argument(
        "--exclude-fields-file", default="", help="排除字段 ID/名称的文本文件，每行一个"
    )
    parser.add_argument(
        "--include-templates-file", default="", help="包含模板名称的文本文件，每行一个"
    )
    parser.add_argument(
        "--exclude-templates-file", default="", help="排除模板名称的文本文件，每行一个"
    )
    add_settings(parser, settings_by_yaml_section("filters"))


def add_api_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    """Add API retry/concurrency/runtime wait arguments."""
    add_settings(parser, settings_by_yaml_section("concurrency"))
    add_settings(parser, settings_by_yaml_section("retries"))


def add_precheck_arguments(parser: argparse.ArgumentParser) -> None:
    """Add local metric diagnostic threshold arguments."""
    add_settings(parser, settings_by_yaml_section("quality"))
    add_settings(parser, settings_by_yaml_section("expression"))


def add_output_logging_arguments(parser: argparse.ArgumentParser) -> None:
    """Add output, logging, and clean arguments."""
    parser.add_argument(
        "--output", default="", help="结果 JSON 输出文件路径（留空则根据 dataset_id 自动生成）"
    )
    parser.add_argument(
        "--run-name",
        default="default",
        help="默认运行目录名；仅在未显式传入 --output 时生效",
    )
    add_settings(parser, (get_setting("verbose"), get_setting("quiet")))
    parser.add_argument("--log-file", default="", help="日志文件路径")
    parser.add_argument(
        "--include-credentials",
        action="store_true",
        help="全局 clean 同时删除 .credentials/；必须与 --all-datasets 一起使用",
    )
    parser.add_argument(
        "--all-datasets",
        action="store_true",
        help="clean 命令覆盖所有数据集和遗留根目录运行产物",
    )
    parser.add_argument(
        "--confirm-clean",
        action="store_true",
        help="确认执行 clean；未提供时只预览将删除的路径",
    )
    parser.add_argument(
        "--dry-run-clean",
        action="store_true",
        help="显式预览 clean 命令会删除的路径，不实际删除",
    )
