"""Grouped CLI argument section builders."""

from __future__ import annotations

import argparse
import os

from ..config.constants import DEFAULT_DATASET_ID, NEUTRALIZATION_SUBINDUSTRY
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


def add_base_arguments(parser: argparse.ArgumentParser) -> None:
    """Add command and config arguments."""
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run", "clean"),
        default="run",
        help="运行命令：run=执行 Alpha 流程（默认），clean=清理本地运行文件",
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
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID, help="数据集 ID")
    parser.add_argument("--region", default="USA", help="地区代码")
    parser.add_argument("--universe", default="TOP3000", help="宇宙代码")
    parser.add_argument("--instrument-type", default="EQUITY", help="工具类型")
    parser.add_argument("--delay", type=int, default=1, help="延迟天数")
    parser.add_argument("--decay", type=int, default=0, help="衰减天数 (Decay)")
    parser.add_argument("--neutralization", default=NEUTRALIZATION_SUBINDUSTRY, help="中性化类型 (Neutralization)")
    parser.add_argument("--truncation", type=float, default=0.05, help="截断阈值 (Truncation)")
    parser.add_argument("--nan-handling", default="ON", help="NaN 处理方式 (NaN Handling)")
    parser.add_argument("--pasteurization", default="ON", help="Pasteurization 开关 (ON/OFF)")
    parser.add_argument("--unit-handling", default="VERIFY", help="单位验证 (Unit Handling)")
    parser.add_argument("--language", default="FASTEXPR", help="表达式语言 (Language)")
    parser.add_argument(
        "--start-date",
        default=None,
        help="模拟开始日期 (Start Date, YYYY-MM-DD)，默认使用 config 中的值",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="模拟结束日期 (End Date, YYYY-MM-DD)，默认使用 config 中的值",
    )


def add_run_mode_arguments(parser: argparse.ArgumentParser) -> None:
    """Add run-mode toggles."""
    run_mode_group = parser.add_mutually_exclusive_group()
    run_mode_group.add_argument(
        "--smoke-test",
        action="store_true",
        default=False,
        help="运行冒烟测试（单字段/单模板），不用于 Alpha 发现",
    )
    run_mode_group.add_argument(
        "--full-run",
        action="store_true",
        default=False,
        help="运行全量测试（所有字段和所有模板），可能很慢",
    )
    parser.add_argument(
        "--no-smoke-test",
        action="store_false",
        dest="smoke_test",
        default=False,
        help="关闭冒烟测试模式（覆盖 YAML runtime.smoke_test=true）",
    )
    parser.add_argument(
        "--no-full-run",
        action="store_false",
        dest="full_run",
        default=False,
        help="关闭全量运行模式（覆盖 YAML runtime.full_run=true）",
    )
    add_bool_argument(
        parser,
        "--recheck-pending-self-correlation-only",
        dest="recheck_pending_self_correlation_only",
        help_enable="仅复查历史结果中仍为 SELF_CORRELATION=PENDING 的候选，不发起新的字段探索",
        help_disable="关闭仅复查 pending self-correlation 模式（覆盖 YAML runtime.recheck_pending_self_correlation_only=true）",
    )
    add_bool_argument(
        parser,
        "--finalize-recheck-pending-self-correlation",
        dest="finalize_recheck_pending_self_correlation",
        help_enable="在 finalize 阶段同步复查 pending self-correlation 候选",
        help_disable="关闭 finalize 阶段的 pending self-correlation 同步复查（覆盖 YAML runtime.finalize_recheck_pending_self_correlation=true）",
    )


def add_search_arguments(parser: argparse.ArgumentParser) -> None:
    """Add field/template search-space arguments."""
    parser.add_argument("--limit", type=int, default=200, help="要获取/测试的字段数量；0 表示所有字段")
    parser.add_argument("--offset", type=int, default=0, help="字段偏移量")
    parser.add_argument("--page-size", type=int, default=50, help="分页大小")
    parser.add_argument(
        "--sleep-between-fields",
        type=float,
        default=5.0,
        help="字段间的休眠时间（增大以降低 API 限流）",
    )
    parser.add_argument(
        "--max-templates-per-field",
        type=int,
        default=6,
        help="每个字段测试的最大模板数；0 表示所有内置模板",
    )
    parser.add_argument(
        "--max-templates-per-family",
        type=int,
        default=1,
        help="每个表达式家族保留的最大候选数；0 表示不限制",
    )
    parser.add_argument(
        "--field-template-batch-size",
        type=int,
        default=2,
        help="每轮每个字段最多发出的模板/setting 组合数；默认 2，启用 breadth-first 浅层轮转",
    )
    parser.add_argument(
        "--legacy-similarity-penalty",
        type=int,
        default=42,
        help="应用于 raw/group-rank/simple-ratio 等模板的优先级惩罚",
    )
    parser.add_argument(
        "--disable-legacy-after",
        type=int,
        default=8,
        help="在多少次零可提交尝试后全局禁用 legacy 家族；0 表示不启用",
    )


def add_file_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """Add template/data file and include/exclude filter arguments."""
    parser.add_argument("--template-library-file", default="", help="本地 JSON 模板库文件路径；留空则根据 dataset_id 自动选择")
    parser.add_argument("--feedback-output", default="", help="用于反馈排序的历史结果 JSON 文件；默认使用 --output")
    parser.add_argument("--fields-cache-file", default="", help="本地 JSON 字段缓存文件路径（留空则根据 dataset_id 自动生成）")
    add_bool_argument(
        parser,
        "--dry-run-plan",
        dest="dry_run_plan",
        help_enable="仅打印计划，不创建模拟",
        help_disable="关闭干运行模式（覆盖 YAML runtime.dry_run_plan=true）",
    )
    parser.add_argument("--include-fields-file", default="", help="包含字段 ID/名称的文本文件，每行一个")
    parser.add_argument("--exclude-fields-file", default="", help="排除字段 ID/名称的文本文件，每行一个")
    parser.add_argument("--include-templates-file", default="", help="包含模板名称的文本文件，每行一个")
    parser.add_argument("--exclude-templates-file", default="", help="排除模板名称的文本文件，每行一个")
    parser.add_argument("--template-disable-after", type=int, default=12, help="在多少次尝试后禁用模板；0 表示不自动剪枝")
    parser.add_argument("--top-fields-by-feedback", type=int, default=0, help="如果大于 0，仅测试按反馈排序的前 N 个字段")
    parser.add_argument("--stop-after-submittable", type=int, default=0, help="如果大于 0，在找到指定数量的可提交 Alpha 后停止")


def add_api_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    """Add API retry/concurrency/runtime wait arguments."""
    parser.add_argument("--min-request-interval", type=float, default=2.5, help="请求间的最小间隔，用于降低速率限制（增大以应对 API 429）")
    parser.add_argument("--rate-limit-max-retries", type=int, default=5, help="速率限制时的最大重试次数")
    parser.add_argument("--login-retries", type=int, default=3, help="登录重试次数")
    parser.add_argument("--simulation-create-retries", type=int, default=3, help="模拟创建重试次数")
    parser.add_argument("--simulation-poll-retries", type=int, default=3, help="模拟轮询重试次数")
    parser.add_argument("--max-concurrent-simulations", type=int, default=1, help="并发模拟的最大数量（降低以避免 API 限流）")
    parser.add_argument("--max-concurrent-creates", type=int, default=1, help="并发模拟创建请求的最大数量")
    parser.add_argument("--simulation-max-polls", type=int, default=240, help="单个模拟的最大轮询次数")
    parser.add_argument("--simulation-max-wait-seconds", type=float, default=1800.0, help="单个模拟的最大等待时间（秒）")
    parser.add_argument("--simulation-max-pending-cycles", type=int, default=120, help="最大等待周期数")
    parser.add_argument("--simulation-max-queue-seconds", type=float, default=600.0, help="最大队列等待时间（秒）")
    parser.add_argument("--queue-busy-cooldown-seconds", type=float, default=300.0, help="队列拥塞后的冷却时间（秒，增大以避免重复触发限流）")
    parser.add_argument("--field-queue-busy-skip-after", type=int, default=2, help="字段队列拥塞后跳过阈值；0 表示不跳过")
    parser.add_argument("--check-submit-retries", type=int, default=3, help="检查提交重试次数")
    parser.add_argument(
        "--self-correlation-max-polls",
        type=int,
        default=30,
        help="checksubmit 后额外轮询 SELF_CORRELATION 终态的最大次数；0 表示不等待",
    )
    parser.add_argument(
        "--self-correlation-poll-seconds",
        type=float,
        default=10.0,
        help="SELF_CORRELATION 仍为 PENDING 时，两次 alpha detail 轮询之间的等待秒数",
    )
    parser.add_argument("--submit-retries", type=int, default=3, help="提交重试次数")


def add_precheck_arguments(parser: argparse.ArgumentParser) -> None:
    """Add local precheck threshold arguments."""
    parser.add_argument("--min-sharpe", type=float, default=1.25, help="本地预检最低 Sharpe 阈值")
    parser.add_argument("--min-fitness", type=float, default=1.00, help="本地预检最低 Fitness 阈值")
    parser.add_argument("--min-turnover", type=float, default=0.01, help="本地预检最低 Turnover 阈值")
    parser.add_argument("--max-turnover", type=float, default=0.70, help="本地预检最高 Turnover 阈值")
    parser.add_argument("--max-weight", type=float, default=0.10, help="本地预检单股最大权重阈值")
    parser.add_argument("--backfill-window", type=int, default=240, help="ts_backfill 时间窗口大小（天）")


def add_output_logging_arguments(parser: argparse.ArgumentParser) -> None:
    """Add submit, output, logging, and clean arguments."""
    add_bool_argument(
        parser,
        "--submit",
        dest="submit",
        help_enable="检查通过时提交 Alpha",
        help_disable="不提交 Alpha（覆盖 YAML runtime.submit=true）",
    )
    add_bool_argument(
        parser,
        "--auto-update-blacklist",
        dest="auto_update_blacklist",
        help_enable="根据本次结果自动追加低质量模板到 data/blacklists/<dataset>/blacklist.json",
        help_disable="不自动更新模板黑名单（覆盖 YAML runtime.auto_update_blacklist=true）",
    )
    parser.add_argument("--output", default="", help="结果 JSON 输出文件路径（留空则根据 dataset_id 自动生成）")
    add_bool_argument(
        parser,
        "--verbose",
        dest="verbose",
        help_enable="详细日志模式",
        help_disable="关闭详细日志模式（覆盖 YAML runtime.verbose=true）",
    )
    add_bool_argument(
        parser,
        "--quiet",
        dest="quiet",
        help_enable="安静模式",
        help_disable="关闭安静模式（覆盖 YAML runtime.quiet=true）",
    )
    parser.add_argument("--log-file", default="", help="日志文件路径")
    parser.add_argument("--include-credentials", action="store_true", help="clean 命令同时删除 .credentials/（默认不会删除凭据）")
    parser.add_argument("--dry-run-clean", action="store_true", help="预览 clean 命令会删除的路径，不实际删除")
