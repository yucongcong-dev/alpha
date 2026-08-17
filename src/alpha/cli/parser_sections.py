"""Grouped CLI argument section builders."""

from __future__ import annotations

import argparse
import os
from typing import Any

from ..config._constants_thresholds import DEFAULT_DATASET_ID
from ..config.settings_spec import (
    SettingSpec,
    get_setting,
    section_settings,
    settings_by_yaml_section,
)
from .constants import DEFAULT_CREDS_FILE, DEFAULT_CREDS_KEY_FILE


def add_bool_argument(
    parser: Any,
    name: str,
    *,
    dest: str,
    default: bool = False,
    help_enable: str,
    help_disable: str,
    hide_help: bool = False,
) -> None:
    """Add a boolean CLI option pair that can both enable and disable YAML defaults."""
    visible_help = argparse.SUPPRESS if hide_help else help_enable
    visible_disable_help = argparse.SUPPRESS if hide_help else help_disable
    group = parser.add_mutually_exclusive_group()
    group.add_argument(name, action="store_true", dest=dest, default=default, help=visible_help)
    positive_name = name[2:] if name.startswith("--") else name
    group.add_argument(
        f"--no-{positive_name}",
        action="store_false",
        dest=dest,
        default=default,
        help=visible_disable_help,
    )


def add_settings(
    parser: Any,
    specs: tuple[SettingSpec, ...],
    *,
    hide_help: bool = False,
) -> None:
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
                hide_help=hide_help,
            )
            continue
        parser.add_argument(
            spec.cli,
            dest=spec.dest,
            default=spec.default,
            type=spec.arg_type,
            choices=spec.choices or None,
            help=argparse.SUPPRESS if hide_help else spec.help,
        )


def add_base_arguments(parser: Any, *, command: str = "run") -> None:
    """Add one command parser's positional command and shared config option."""
    arguments = parser.add_argument_group("命令与配置")
    arguments.add_argument(
        "command",
        nargs="?",
        choices=(command,),
        default=command,
        help=("执行 Alpha 流程（默认）" if command == "run" else f"执行 {command} 命令"),
    )
    arguments.add_argument(
        "--config",
        default="",
        help="YAML 配置文件路径（留空自动搜索 config/settings.yaml）。所有参数可在此文件中配置。",
    )


def add_credentials_arguments(parser: Any) -> None:
    """Add credential source arguments."""
    arguments = parser.add_argument_group("凭证")
    arguments.add_argument(
        "--creds-file", default=DEFAULT_CREDS_FILE, help="本地 JSON 凭证文件路径"
    )
    arguments.add_argument(
        "--creds-key-file",
        default=DEFAULT_CREDS_KEY_FILE,
        help="用于加密/解密凭证文件的密钥文件路径",
    )
    arguments.add_argument("--email", default=os.getenv("WQB_EMAIL"), help="用户邮箱")
    arguments.add_argument("--password", default=os.getenv("WQB_PASSWORD"), help="用户密码")


def _add_dataset_id_argument(arguments: Any) -> None:
    arguments.add_argument(
        "--dataset-id",
        default=DEFAULT_DATASET_ID,
        help="数据集 ID；run/clean 命令必须显式指定",
    )


def add_dataset_selector_arguments(parser: Any) -> None:
    """Add the dataset selector used by clean and submission-check commands."""
    arguments = parser.add_argument_group("数据集")
    _add_dataset_id_argument(arguments)


def add_dataset_context_arguments(parser: Any) -> None:
    """Add a dataset selector plus path-affecting platform context options."""
    arguments = parser.add_argument_group("数据集与运行上下文")
    _add_dataset_id_argument(arguments)
    add_settings(arguments, section_settings("dataset"))


def add_dataset_arguments(parser: Any) -> None:
    """Add the full dataset and simulation surface for the run command."""
    arguments = parser.add_argument_group("数据集与模拟设置")
    _add_dataset_id_argument(arguments)
    add_settings(arguments, settings_by_yaml_section("simulation"))


def add_run_mode_arguments(parser: Any) -> None:
    """Add run-mode toggles."""
    arguments = parser.add_argument_group("运行模式")
    add_settings(arguments, (get_setting("strategy_profile"),))
    run_mode = get_setting("run_mode")
    run_mode_group = arguments.add_mutually_exclusive_group()
    run_mode_group.add_argument(
        "--run-mode",
        choices=run_mode.choices,
        dest="run_mode",
        default=run_mode.default,
        help=run_mode.help,
    )


def add_search_arguments(parser: Any) -> None:
    """Add field/template search-space arguments."""
    arguments = parser.add_argument_group("搜索范围")
    add_settings(arguments, settings_by_yaml_section("limits"))


def add_file_filter_arguments(parser: Any) -> None:
    """Add template/data file and include/exclude filter arguments."""
    arguments = parser.add_argument_group("研究输入与过滤")
    arguments.add_argument(
        "--template-library-file",
        default="",
        help="本地 JSON 模板库文件路径；留空则根据 dataset_id 自动选择",
    )
    arguments.add_argument(
        "--feedback-output", default="", help="用于反馈排序的历史结果 JSON 文件；默认使用 --output"
    )
    arguments.add_argument(
        "--fields-cache-file",
        default="",
        help="本地 JSON 字段缓存文件路径（留空则根据 dataset_id 自动生成）",
    )
    add_settings(arguments, (get_setting("dry_run_plan"),))
    arguments.add_argument(
        "--include-fields-file", default="", help="包含字段 ID/名称的文本文件，每行一个"
    )
    arguments.add_argument(
        "--exclude-fields-file", default="", help="排除字段 ID/名称的文本文件，每行一个"
    )
    arguments.add_argument(
        "--include-templates-file", default="", help="包含模板名称的文本文件，每行一个"
    )
    arguments.add_argument(
        "--exclude-templates-file", default="", help="排除模板名称的文本文件，每行一个"
    )
    add_settings(arguments, settings_by_yaml_section("filters"))


def add_feedback_output_argument(parser: Any) -> None:
    """Add the feedback aggregate path used by submission-check refresh."""
    arguments = parser.add_argument_group("反馈结果")
    arguments.add_argument(
        "--feedback-output", default="", help="历史结果 JSON 文件；默认使用 --output"
    )


def add_api_runtime_arguments(parser: Any, *, visible: bool = True) -> None:
    """Add API retry/concurrency/runtime wait arguments."""
    arguments = parser.add_argument_group(
        "API、并发与重试（高级）" if visible else argparse.SUPPRESS
    )
    add_settings(arguments, settings_by_yaml_section("concurrency"), hide_help=not visible)
    add_settings(arguments, settings_by_yaml_section("retries"), hide_help=not visible)


def add_submission_check_api_arguments(parser: Any) -> None:
    """Add only the API controls used while refreshing submission checks."""
    arguments = parser.add_argument_group("API 与重试")
    add_settings(
        arguments,
        (
            get_setting("min_request_interval"),
            get_setting("rate_limit_max_retries"),
            get_setting("login_retries"),
            get_setting("check_submission_retries"),
        ),
    )


def add_pending_check_refresh_arguments(parser: Any, *, visible: bool = True) -> None:
    """Add bounded polling controls for the check-submissions command."""
    arguments = parser.add_argument_group("Submission Check 刷新" if visible else argparse.SUPPRESS)
    arguments.add_argument(
        "--pending-check-limit",
        type=int,
        default=0,
        help=(
            "每轮最多刷新多少条待处理 Check；0 表示所有待处理结果" if visible else argparse.SUPPRESS
        ),
    )
    arguments.add_argument(
        "--pending-check-max-seconds",
        type=float,
        default=900.0,
        help="check-submissions 的最长轮询时间（秒，默认 900）" if visible else argparse.SUPPRESS,
    )
    arguments.add_argument(
        "--pending-check-workers",
        type=int,
        default=1,
        help="并发 Submission Check 查询数（默认 1）" if visible else argparse.SUPPRESS,
    )


def add_precheck_arguments(parser: Any, *, visible: bool = True) -> None:
    """Add local metric diagnostic threshold arguments."""
    arguments = parser.add_argument_group("质量与表达式诊断" if visible else argparse.SUPPRESS)
    add_settings(arguments, settings_by_yaml_section("quality"), hide_help=not visible)
    add_settings(arguments, settings_by_yaml_section("expression"), hide_help=not visible)


def add_output_logging_arguments(parser: Any) -> None:
    """Add output and logging arguments used by run/check-submissions."""
    output_arguments = parser.add_argument_group("输出与日志")
    output_arguments.add_argument(
        "--output", default="", help="结果 JSON 输出文件路径（留空则根据 dataset_id 自动生成）"
    )
    output_arguments.add_argument(
        "--run-name",
        default="default",
        help="默认运行目录名；仅在未显式传入 --output 时生效",
    )
    add_settings(output_arguments, (get_setting("verbose"), get_setting("quiet")))
    output_arguments.add_argument("--log-file", default="", help="日志文件路径")


def add_clean_arguments(parser: Any) -> None:
    """Add the destructive-operation controls exclusive to clean."""
    clean_arguments = parser.add_argument_group("clean 命令")
    clean_arguments.add_argument(
        "--include-credentials",
        action="store_true",
        help="全局 clean 同时删除 .credentials/；必须与 --all-datasets 一起使用",
    )
    clean_arguments.add_argument(
        "--all-datasets",
        action="store_true",
        help="clean 命令覆盖所有数据集和遗留根目录运行产物",
    )
    clean_arguments.add_argument(
        "--confirm-clean",
        action="store_true",
        help="确认执行 clean；未提供时只预览将删除的路径",
    )
    clean_arguments.add_argument(
        "--dry-run-clean",
        action="store_true",
        help="显式预览 clean 命令会删除的路径，不实际删除",
    )
