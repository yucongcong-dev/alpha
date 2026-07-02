"""
命令行参数解析模块

本模块负责解析命令行参数、标准化路径、构建配置快照、
加载运行过滤器和设置日志等初始化工作。

模块内容：
    - parse_args() -> argparse.Namespace: 解析命令行参数
    - normalize_args_paths(args) -> RunPaths: 标准化参数中的文件路径
    - build_run_config_snapshot(args, run_paths) -> Dict: 构建运行配置快照
    - load_run_filters(run_paths) -> RunFilters: 加载运行过滤器
    - setup_runtime_logging(log_path) -> None: 设置运行时日志
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from ..config import (
    DEFAULT_DATASET_ID,
    apply_yaml_global_defaults,
    get_dataset_profile,
    get_yaml_config,
)
from ..models.base import RunPaths
from .constants import (
    CACHE_DIR,
    CREDS_DIR,
    DATA_DIR,
    DEFAULT_CREDS_FILE,
    DEFAULT_CREDS_KEY_FILE,
    DEFAULT_FIELDS_CACHE_FILE,
    DEFAULT_OUTPUT_FILE,
    DEFAULT_TEMPLATE_LIBRARY_FILE,
    PROJECT_ROOT,
    RESULTS_DIR,
    SCRIPT_DIR,
)

# 过滤器/日志函数已提取到 cli.filters，此处保留重导出以兼容
from .filters import (  # noqa: F401
    load_line_set,
    load_run_filters,
    load_run_filters_extended,
    setup_runtime_logging,
)
from .path_resolution import normalize_args_paths as _normalize_args_paths
from .run_config import build_run_config_snapshot as _build_run_config_snapshot

# ============================================================================
# 命令行参数解析函数
# ============================================================================


def collect_parser_defaults(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """收集 argparse dest -> 默认值映射。"""
    defaults: dict[str, Any] = {}
    for action in parser._actions:  # noqa: SLF001 - argparse exposes no public action iterator.
        dest = getattr(action, "dest", None)
        if not dest or dest == "help":
            continue
        defaults[dest] = action.default
    return defaults


def collect_explicit_cli_keys(parser: argparse.ArgumentParser, argv: list[str]) -> set[str]:
    """收集命令行中显式传入的 argparse dest 名称。
    Collect argparse destination names explicitly provided on the command line.
    """
    explicit_keys: set[str] = set()
    option_to_dest = {
        option: action.dest
        for action in parser._actions  # noqa: SLF001 - argparse exposes no public action iterator.
        for option in action.option_strings
    }
    for token in argv:
        option = token.split("=", 1)[0]
        dest = option_to_dest.get(option)
        if dest:
            explicit_keys.add(dest)
    return explicit_keys


def add_bool_argument(
    parser: argparse.ArgumentParser,
    name: str,
    *,
    dest: str,
    default: bool = False,
    help_enable: str,
    help_disable: str,
) -> None:
    """添加支持 --flag / --no-flag 的布尔参数。
    Add a boolean CLI option pair that can both enable and disable YAML defaults.
    """
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


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数，包括数据集、搜索策略和本地文件配置。

    解析用于配置 Brain API 客户端、数据集选择、搜索策略和
    本地文件路径的所有命令行参数。

    Returns:
        argparse.Namespace: 解析后的命令行参数对象。

    参数分组：
        凭证参数：
            --creds-file: 凭证文件路径
            --creds-key-file: 凭证密钥文件路径
            --email: 用户邮箱
            --password: 用户密码

        数据集参数：
            --dataset-id: 数据集 ID
            --region: 地区代码
            --universe: 宇宙代码
            --instrument-type: 工具类型
            --delay: 延迟天数

        模拟设置参数：
            --decay: 衰减天数
            --neutralization: 中性化类型
            --truncation: 截断阈值
            --nan-handling: NaN 处理方式

        字段筛选参数：
            --limit: 字段数量限制
            --offset: 字段偏移量
            --page-size: 分页大小
            --sleep-between-fields: 字段间休眠时间
            --max-templates-per-field: 每字段最大模板数
            --max-templates-per-family: 每家族最大模板数
            --legacy-similarity-penalty: legacy 相似度惩罚
            --disable-legacy-after: 禁用 legacy 的阈值

        模板参数：
            --template-library-file: 模板库文件路径
            --fields-cache-file: 字段缓存文件路径
            --feedback-output: 反馈输出文件路径
        过滤器参数：
            --include-fields-file: 包含字段文件
            --exclude-fields-file: 排除字段文件
            --include-templates-file: 包含模板文件
            --exclude-templates-file: 排除模板文件
            --template-disable-after: 模板禁用阈值
            --top-fields-by-feedback: 按反馈排序的字段数

        重试参数：
            --simulation-create-retries: 模拟创建重试次数
            --simulation-poll-retries: 模拟轮询重试次数
            --simulation-max-polls: 最大轮询次数
            --simulation-max-wait-seconds: 最大等待时间
            --simulation-max-pending-cycles: 最大等待周期
            --simulation-max-queue-seconds: 最大队列时间
            --queue-busy-cooldown-seconds: 队列冷却时间
            --field-queue-busy-skip-after: 字段队列跳过阈值
            --check-submit-retries: 检查提交重试次数
            --submit-retries: 提交重试次数
            --rate-limit-max-retries: 速率限制重试次数
            --login-retries: 登录重试次数
            --min-request-interval: 最小请求间隔

        输出参数：
            --output: 输出文件路径
            --submit: 是否提交可提交的 Alpha
            --stop-after-submittable: 达到目标后停止
            --target-submittable: 目标可提交数量

        运行模式参数：
            --smoke-test: 冒烟测试模式
            --dry-run-plan: 干运行模式（仅打印计划）
            --full-run: 全量运行模式

        日志参数：
            --verbose: 详细日志模式
            --quiet: 安静模式
            --log-file: 日志文件路径

    Example:
        >>> args = parse_args()
        >>> print(args.dataset_id)
        fundamental6
        >>> print(args.region)
        USA

    Note:
        - smoke_test 和 full_run 是互斥的运行模式
        - smoke_test 会自动设置 limit=1, max_templates_per_field=1
        - full_run 会自动设置 limit=0, max_templates_per_field=0
        - 默认使用 fundamental6 数据集和 USA 地区
    """
    parser = argparse.ArgumentParser(
        prog="alpha",
        description="测试 WorldQuant Brain 数据集中的所有字段并提交可提交的 Alpha。"
    )

    # 配置文件参数
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
        help="YAML 配置文件路径（留空自动搜索 settings.yaml）。所有参数可在此文件中配置。",
    )

    # 凭证参数
    parser.add_argument(
        "--creds-file",
        default=DEFAULT_CREDS_FILE,
        help="本地 JSON 凭证文件路径",
    )
    parser.add_argument(
        "--creds-key-file",
        default=DEFAULT_CREDS_KEY_FILE,
        help="用于加密/解密凭证文件的密钥文件路径",
    )
    parser.add_argument("--email", default=os.getenv("WQB_EMAIL"), help="用户邮箱")
    parser.add_argument("--password", default=os.getenv("WQB_PASSWORD"), help="用户密码")

    # 数据集参数
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID, help="数据集 ID")
    parser.add_argument("--region", default="USA", help="地区代码")
    parser.add_argument("--universe", default="TOP3000", help="宇宙代码")
    parser.add_argument("--instrument-type", default="EQUITY", help="工具类型")
    parser.add_argument("--delay", type=int, default=1, help="延迟天数")

    # 模拟设置参数 —— 与官网 Simulation Settings 一一对应
    parser.add_argument("--decay", type=int, default=0, help="衰减天数 (Decay)")
    parser.add_argument("--neutralization", default="SUBINDUSTRY", help="中性化类型 (Neutralization)")
    parser.add_argument("--truncation", type=float, default=0.05, help="截断阈值 (Truncation)")
    parser.add_argument("--nan-handling", default="ON", help="NaN 处理方式 (NaN Handling)")
    parser.add_argument("--pasteurization", default="ON", help="Pasteurization 开关 (ON/OFF)")
    parser.add_argument("--unit-handling", default="VERIFY", help="单位验证 (Unit Handling)")
    parser.add_argument("--language", default="FASTEXPR", help="表达式语言 (Language)")
    parser.add_argument(
        "--start-date", default=None, help="模拟开始日期 (Start Date, YYYY-MM-DD)，默认使用 config 中的值"
    )
    parser.add_argument(
        "--end-date", default=None, help="模拟结束日期 (End Date, YYYY-MM-DD)，默认使用 config 中的值"
    )

    # 运行模式（互斥）
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

    # 字段筛选参数
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="要获取/测试的字段数量；0 表示所有字段",
    )
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

    # 模板参数
    parser.add_argument(
        "--template-library-file",
        default="",
        help="本地 JSON 模板库文件路径；留空则根据 dataset_id 自动选择",
    )
    parser.add_argument(
        "--feedback-output",
        default="",
        help="用于反馈排序的历史结果 JSON 文件；默认使用 --output",
    )
    parser.add_argument(
        "--fields-cache-file",
        default="",
        help="本地 JSON 字段缓存文件路径（留空则根据 dataset_id 自动生成）",
    )
    add_bool_argument(
        parser,
        "--dry-run-plan",
        dest="dry_run_plan",
        help_enable="仅打印计划，不创建模拟",
        help_disable="关闭干运行模式（覆盖 YAML runtime.dry_run_plan=true）",
    )

    # 过滤器参数
    parser.add_argument(
        "--include-fields-file",
        default="",
        help="包含字段 ID/名称的文本文件，每行一个",
    )
    parser.add_argument(
        "--exclude-fields-file",
        default="",
        help="排除字段 ID/名称的文本文件，每行一个",
    )
    parser.add_argument(
        "--include-templates-file",
        default="",
        help="包含模板名称的文本文件，每行一个",
    )
    parser.add_argument(
        "--exclude-templates-file",
        default="",
        help="排除模板名称的文本文件，每行一个",
    )
    parser.add_argument(
        "--template-disable-after",
        type=int,
        default=12,
        help="在多少次尝试后禁用模板；0 表示不自动剪枝",
    )
    parser.add_argument(
        "--top-fields-by-feedback",
        type=int,
        default=0,
        help="如果大于 0，仅测试按反馈排序的前 N 个字段",
    )
    parser.add_argument(
        "--stop-after-submittable",
        type=int,
        default=0,
        help="如果大于 0，在找到指定数量的可提交 Alpha 后停止",
    )

    # 重试参数
    parser.add_argument(
        "--min-request-interval",
        type=float,
        default=2.5,
        help="请求间的最小间隔，用于降低速率限制（增大以应对 API 429）",
    )
    parser.add_argument(
        "--rate-limit-max-retries",
        type=int,
        default=5,
        help="速率限制时的最大重试次数",
    )
    parser.add_argument("--login-retries", type=int, default=3, help="登录重试次数")
    parser.add_argument("--simulation-create-retries", type=int, default=3, help="模拟创建重试次数")
    parser.add_argument("--simulation-poll-retries", type=int, default=3, help="模拟轮询重试次数")
    parser.add_argument(
        "--max-concurrent-simulations",
        type=int,
        default=1,
        help="并发模拟的最大数量（降低以避免 API 限流）",
    )
    parser.add_argument(
        "--max-concurrent-creates",
        type=int,
        default=1,
        help="并发模拟创建请求的最大数量",
    )
    parser.add_argument(
        "--simulation-max-polls",
        type=int,
        default=240,
        help="单个模拟的最大轮询次数",
    )
    parser.add_argument(
        "--simulation-max-wait-seconds",
        type=float,
        default=1800.0,
        help="单个模拟的最大等待时间（秒）",
    )
    parser.add_argument(
        "--simulation-max-pending-cycles",
        type=int,
        default=120,
        help="最大等待周期数",
    )
    parser.add_argument(
        "--simulation-max-queue-seconds",
        type=float,
        default=600.0,
        help="最大队列等待时间（秒）",
    )
    parser.add_argument(
        "--queue-busy-cooldown-seconds",
        type=float,
        default=300.0,
        help="队列拥塞后的冷却时间（秒，增大以避免重复触发限流）",
    )
    parser.add_argument(
        "--field-queue-busy-skip-after",
        type=int,
        default=2,
        help="字段队列拥塞后跳过阈值；0 表示不跳过",
    )
    parser.add_argument("--check-submit-retries", type=int, default=3, help="检查提交重试次数")
    parser.add_argument("--submit-retries", type=int, default=3, help="提交重试次数")

    # 质量阈值参数
    parser.add_argument(
        "--min-sharpe",
        type=float,
        default=1.25,
        help="本地预检最低 Sharpe 阈值",
    )
    parser.add_argument(
        "--min-fitness",
        type=float,
        default=1.00,
        help="本地预检最低 Fitness 阈值",
    )
    parser.add_argument(
        "--min-turnover",
        type=float,
        default=0.01,
        help="本地预检最低 Turnover 阈值",
    )
    parser.add_argument(
        "--max-turnover",
        type=float,
        default=0.70,
        help="本地预检最高 Turnover 阈值",
    )
    parser.add_argument(
        "--max-weight",
        type=float,
        default=0.10,
        help="本地预检单股最大权重阈值",
    )
    parser.add_argument(
        "--backfill-window",
        type=int,
        default=240,
        help="ts_backfill 时间窗口大小（天）",
    )

    # 提交和输出参数
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
    parser.add_argument(
        "--output",
        default="",
        help="结果 JSON 输出文件路径（留空则根据 dataset_id 自动生成）",
    )

    # 日志参数
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
    parser.add_argument(
        "--include-credentials",
        action="store_true",
        help="clean 命令同时删除 .credentials/（默认不会删除凭据）",
    )
    parser.add_argument(
        "--dry-run-clean",
        action="store_true",
        help="预览 clean 命令会删除的路径，不实际删除",
    )

    parser_defaults = collect_parser_defaults(parser)
    explicit_cli_keys = collect_explicit_cli_keys(parser, sys.argv[1:])
    args = parser.parse_args()

    # 加载 YAML 配置文件（优先级：CLI --config > 自动搜索 > 无）
    yaml_config = get_yaml_config(args.config if args.config else "")

    # 应用 YAML global 默认值（在 dataset profile 之前，profile 可覆盖）
    apply_yaml_global_defaults(args, yaml_config, explicit_cli_keys)

    # 根据数据集自动适配运行参数
    # 优先级：CLI > YAML dataset_profiles > YAML global > DEFAULT_PROFILE > argparse
    profile = get_dataset_profile(args.dataset_id, yaml_config)
    _dataset_profile_keys = (
        "min_request_interval",
        "sleep_between_fields",
        "max_concurrent_simulations",
        "max_concurrent_creates",
        "max_templates_per_field",
        "field_template_batch_size",
        "simulation_max_wait_seconds",
        "simulation_max_queue_seconds",
        "queue_busy_cooldown_seconds",
        "template_disable_after",
    )
    # dataset_profiles 显式键始终覆盖 YAML global；其余情况下仅当 args 仍为 argparse 默认值时，
    # 才让 DEFAULT_PROFILE / profile 回退值生效，避免覆盖 YAML global。
    yaml_profiles = (yaml_config or {}).get("dataset_profiles", {})
    yaml_dataset_cfg = yaml_profiles.get(args.dataset_id, {}) if isinstance(yaml_profiles, dict) else {}
    for key in _dataset_profile_keys:
        if key in explicit_cli_keys or key not in profile:
            continue
        if key in yaml_dataset_cfg:
            setattr(args, key, profile[key])
            continue
        if getattr(args, key, None) == parser_defaults.get(key):
            setattr(args, key, profile[key])

    # 根据运行模式调整参数
    if args.smoke_test:
        args.limit = 1
        args.max_templates_per_field = 1
        args.max_concurrent_simulations = 1
        args.max_concurrent_creates = 1
        args.simulation_max_pending_cycles = min(args.simulation_max_pending_cycles, 60)
        args.simulation_max_queue_seconds = min(args.simulation_max_queue_seconds, 300)
    elif args.full_run:
        args.limit = 0
        args.max_templates_per_field = 0

    return args


# ============================================================================
# 路径标准化函数
# ============================================================================


def normalize_args_paths(args: argparse.Namespace) -> RunPaths:
    """兼容导出：归一化运行路径，但不修改 args。"""
    return _normalize_args_paths(args)


# ============================================================================
# 运行配置快照函数
# ============================================================================


def build_run_config_snapshot(args: argparse.Namespace, run_paths: RunPaths) -> dict[str, Any]:
    """兼容导出：构建运行配置快照。"""
    return _build_run_config_snapshot(args, run_paths)


# 过滤器函数和日志设置已提取到 cli/filters.py
# 通过顶部的 from .filters import ... 提供重导出兼容
