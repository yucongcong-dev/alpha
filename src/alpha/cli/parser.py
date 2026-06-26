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

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Set

from ..config import DEFAULT_DATASET_ID
from ..io.output import (
    build_dataset_scoped_paths,
    build_output_sidecar_paths,
    resolve_cli_path,
)
from ..models.base import RunFilters, RunPaths, TeeStream

# ============================================================================
# 常量定义
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
"""脚本目录的绝对路径"""

PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
"""项目根目录的绝对路径（alpha/ 目录）"""

# 运行时文件目录（相对于项目根目录）
CREDS_DIR = PROJECT_ROOT / ".credentials"
CACHE_DIR = PROJECT_ROOT / "cache"
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_CREDS_FILE = str(CREDS_DIR / "worldquant_brain_credentials.json")
"""默认凭证文件路径"""

DEFAULT_CREDS_KEY_FILE = str(CREDS_DIR / "worldquant_brain_credentials.key")
"""默认凭证密钥文件路径"""

DEFAULT_TEMPLATE_LIBRARY_FILE = str(DATA_DIR / "worldquant_template_library.json")
"""默认模板库文件路径"""

DEFAULT_FIELDS_CACHE_FILE = str(CACHE_DIR / "fundamental6_fields_cache.json")
"""默认字段缓存文件路径"""

DEFAULT_OUTPUT_FILE = str(RESULTS_DIR / "fundamental6_test_results.json")
"""默认输出文件路径"""


# ============================================================================
# 命令行参数解析函数
# ============================================================================

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
            --refresh-fields-cache: 强制刷新字段缓存

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
        description="测试 WorldQuant Brain 数据集中的所有字段并提交可提交的 Alpha。"
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

    # 模拟设置参数
    parser.add_argument("--decay", type=int, default=5, help="衰减天数")
    parser.add_argument("--neutralization", default="SUBINDUSTRY", help="中性化类型")
    parser.add_argument("--truncation", type=float, default=0.05, help="截断阈值")
    parser.add_argument("--nan-handling", default="ON", help="NaN 处理方式")

    # 运行模式（互斥）
    run_mode_group = parser.add_mutually_exclusive_group()
    run_mode_group.add_argument(
        "--smoke-test",
        action="store_true",
        help="运行冒烟测试（单字段/单模板），不用于 Alpha 发现",
    )
    run_mode_group.add_argument(
        "--full-run",
        action="store_true",
        help="运行全量测试（所有字段和所有模板），可能很慢",
    )

    # 字段筛选参数
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="要获取/测试的字段数量；0 表示所有字段",
    )
    parser.add_argument("--offset", type=int, default=0, help="字段偏移量")
    parser.add_argument("--page-size", type=int, default=50, help="分页大小")
    parser.add_argument(
        "--sleep-between-fields",
        type=float,
        default=2.0,
        help="字段间的休眠时间",
    )
    parser.add_argument(
        "--max-templates-per-field",
        type=int,
        default=5,
        help="每个字段测试的最大模板数；0 表示所有内置模板",
    )
    parser.add_argument(
        "--max-templates-per-family",
        type=int,
        default=1,
        help="每个表达式家族保留的最大候选数；0 表示不限制",
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
        default=DEFAULT_TEMPLATE_LIBRARY_FILE,
        help="本地 JSON 模板库文件路径",
    )
    parser.add_argument(
        "--feedback-output",
        default="",
        help="用于反馈排序的历史结果 JSON 文件；默认使用 --output",
    )
    parser.add_argument(
        "--fields-cache-file",
        default=DEFAULT_FIELDS_CACHE_FILE,
        help="本地 JSON 字段缓存文件路径",
    )
    parser.add_argument(
        "--refresh-fields-cache",
        action="store_true",
        help="强制刷新字段缓存",
    )
    parser.add_argument(
        "--dry-run-plan",
        action="store_true",
        help="仅打印计划，不创建模拟",
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
        default=1.25,
        help="请求间的最小间隔，用于降低速率限制",
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
        default=2,
        help="并发模拟的最大数量",
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
        default=180.0,
        help="队列拥塞后的冷却时间（秒）",
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
        default=0.85,
        help="本地预检最低 Sharpe 阈值",
    )
    parser.add_argument(
        "--min-fitness",
        type=float,
        default=0.50,
        help="本地预检最低 Fitness 阈值",
    )
    parser.add_argument(
        "--min-turnover",
        type=float,
        default=0.005,
        help="本地预检最低 Turnover 阈值",
    )
    parser.add_argument(
        "--max-turnover",
        type=float,
        default=0.75,
        help="本地预检最高 Turnover 阈值",
    )
    parser.add_argument(
        "--max-weight",
        type=float,
        default=0.13,
        help="本地预检单股最大权重阈值",
    )
    parser.add_argument(
        "--backfill-window",
        type=int,
        default=240,
        help="ts_backfill 时间窗口大小（天）",
    )

    # 提交和输出参数
    parser.add_argument("--submit", action="store_true", help="检查通过时提交 Alpha")
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help="结果 JSON 输出文件路径",
    )

    # 日志参数
    parser.add_argument("--verbose", action="store_true", help="详细日志模式")
    parser.add_argument("--quiet", action="store_true", help="安静模式")
    parser.add_argument("--log-file", default="", help="日志文件路径")

    args = parser.parse_args()

    # 根据运行模式调整参数
    if args.smoke_test:
        args.limit = 1
        args.max_templates_per_field = 1
        args.max_concurrent_simulations = 1
        args.max_concurrent_creates = 1
    elif args.full_run:
        args.limit = 0
        args.max_templates_per_field = 0

    return args


# ============================================================================
# 路径标准化函数
# ============================================================================

def normalize_args_paths(args: argparse.Namespace) -> RunPaths:
    """
    标准化命令行参数中的文件路径，将相对路径转换为绝对路径。

    处理所有与运行相关的文件路径，确保它们都是绝对路径，
    并根据数据集 ID 派生默认的模板库、字段缓存和输出文件路径。

    Args:
        args (argparse.Namespace): 命令行参数对象，包含以下属性：
            - dataset_id: 数据集 ID
            - template_library_file: 模板库文件路径
            - fields_cache_file: 字段缓存文件路径
            - output: 输出文件路径
            - feedback_output: 反馈输出文件路径
            - creds_file: 凭证文件路径
            - creds_key_file: 凭证密钥文件路径
            - include_fields_file: 包含字段文件路径
            - exclude_fields_file: 排除字段文件路径
            - include_templates_file: 包含模板文件路径
            - exclude_templates_file: 排除模板文件路径
            - log_file: 日志文件路径

    Returns:
        RunPaths: 包含所有标准化路径的对象，包括：
            - results_dir: 结果目录路径
            - log_file: 日志文件路径
            - state_file: 状态文件路径
            - checkpoint_file: 检查点文件路径
            - template_library_file: 模板库文件路径
            - fields_cache_file: 字段缓存文件路径
            - output: 输出文件路径
            - feedback_output: 反馈输出文件路径
            - creds_file: 凭证文件路径
            - creds_key_file: 凭证密钥文件路径
            - include_fields_file: 包含字段文件路径
            - exclude_fields_file: 排除字段文件路径
            - include_templates_file: 包含模板文件路径
            - exclude_templates_file: 排除模板文件路径

    Example:
        >>> args = parse_args()
        >>> paths = normalize_args_paths(args)
        >>> print(paths.output)
        /absolute/path/to/results.json

    Note:
        - 相对路径会相对于 SCRIPT_DIR 解析为绝对路径
        - 如果未指定输出文件，会根据 dataset_id 派生默认路径
        - 使用 resolve_cli_path 函数处理每个路径
    """
    # 根据数据集 ID 派生默认路径
    scoped_paths = build_dataset_scoped_paths(args.dataset_id)

    # 标准化所有文件路径
    template_library_file = resolve_cli_path(args.template_library_file) or scoped_paths["template_library_file"]
    fields_cache_file = resolve_cli_path(args.fields_cache_file) or scoped_paths["fields_cache_file"]
    output_file = resolve_cli_path(args.output) or scoped_paths["output"]
    feedback_output = resolve_cli_path(args.feedback_output) or output_file
    creds_file = resolve_cli_path(args.creds_file) or DEFAULT_CREDS_FILE
    creds_key_file = resolve_cli_path(args.creds_key_file) or DEFAULT_CREDS_KEY_FILE
    include_fields_file = resolve_cli_path(args.include_fields_file)
    exclude_fields_file = resolve_cli_path(args.exclude_fields_file)
    include_templates_file = resolve_cli_path(args.include_templates_file)
    exclude_templates_file = resolve_cli_path(args.exclude_templates_file)

    # 日志文件路径
    sidecar_paths = build_output_sidecar_paths(output_file)
    log_file = resolve_cli_path(args.log_file) or sidecar_paths["run_log"]

    # 结果目录
    results_dir = str(Path(output_file).parent)

    # 状态文件和检查点文件
    output_stem = Path(output_file).stem
    output_dir = Path(output_file).parent
    state_file = str(output_dir / f"{output_stem}_state.json")
    checkpoint_file = str(output_dir / f"{output_stem}_checkpoint.pkl")

    return RunPaths(
        results_dir=results_dir,
        log_file=log_file,
        state_file=state_file,
        checkpoint_file=checkpoint_file,
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


# ============================================================================
# 运行配置快照函数
# ============================================================================

def build_run_config_snapshot(
    args: argparse.Namespace,
    run_paths: RunPaths
) -> Dict[str, Any]:
    """
    构建运行配置快照，记录所有影响结果的配置参数。

    将命令行参数和路径信息合并为一个字典，用于保存到结果文件中，
    确保结果的可重现性和可追溯性。

    Args:
        args (argparse.Namespace): 命令行参数对象。
        run_paths (RunPaths): 运行路径对象。

    Returns:
        Dict[str, Any]: 配置快照字典，包含以下分组：
            - dataset: 数据集相关配置
            - settings: 模拟设置配置
            - limits: 数量限制配置
            - concurrency: 并发配置
            - retries: 重试配置
            - filters: 过滤器配置
            - paths: 文件路径配置
            - runtime: 运行时配置

    Example:
        >>> args = parse_args()
        >>> paths = normalize_args_paths(args)
        >>> config = build_run_config_snapshot(args, paths)
        >>> print(config["dataset"]["dataset_id"])
        fundamental6

    Note:
        - 配置快照会保存到结果文件中，用于后续分析
        - 不包含敏感信息（如密码）
        - 使用分组结构便于阅读和理解
    """
    return {
        "dataset": {
            "dataset_id": args.dataset_id,
            "region": args.region,
            "universe": args.universe,
            "instrument_type": args.instrument_type,
            "delay": args.delay,
        },
        "settings": {
            "decay": args.decay,
            "neutralization": args.neutralization,
            "truncation": args.truncation,
            "nan_handling": args.nan_handling,
        },
        "limits": {
            "limit": args.limit,
            "offset": args.offset,
            "page_size": args.page_size,
            "sleep_between_fields": args.sleep_between_fields,
            "max_templates_per_field": args.max_templates_per_field,
            "max_templates_per_family": args.max_templates_per_family,
            "legacy_similarity_penalty": args.legacy_similarity_penalty,
            "disable_legacy_after": args.disable_legacy_after,
        },
        "concurrency": {
            "max_concurrent_simulations": args.max_concurrent_simulations,
            "max_concurrent_creates": args.max_concurrent_creates,
        },
        "retries": {
            "simulation_create_retries": args.simulation_create_retries,
            "simulation_poll_retries": args.simulation_poll_retries,
            "simulation_max_polls": args.simulation_max_polls,
            "simulation_max_wait_seconds": args.simulation_max_wait_seconds,
            "simulation_max_pending_cycles": args.simulation_max_pending_cycles,
            "simulation_max_queue_seconds": args.simulation_max_queue_seconds,
            "queue_busy_cooldown_seconds": args.queue_busy_cooldown_seconds,
            "field_queue_busy_skip_after": args.field_queue_busy_skip_after,
            "check_submit_retries": args.check_submit_retries,
            "submit_retries": args.submit_retries,
            "rate_limit_max_retries": args.rate_limit_max_retries,
            "login_retries": args.login_retries,
            "min_request_interval": args.min_request_interval,
        },
        "filters": {
            "template_disable_after": args.template_disable_after,
            "top_fields_by_feedback": args.top_fields_by_feedback,
            "stop_after_submittable": args.stop_after_submittable,
        },
        "paths": {
            "template_library_file": run_paths.template_library_file if hasattr(run_paths, 'template_library_file') else "",
            "fields_cache_file": run_paths.fields_cache_file if hasattr(run_paths, 'fields_cache_file') else "",
            "output": run_paths.output if hasattr(run_paths, 'output') else "",
            "feedback_output": run_paths.feedback_output if hasattr(run_paths, 'feedback_output') else "",
        },
        "runtime": {
            "submit": args.submit,
            "smoke_test": args.smoke_test,
            "dry_run_plan": args.dry_run_plan,
            "full_run": args.full_run,
            "verbose": args.verbose,
            "quiet": args.quiet,
        },
    }


# ============================================================================
# 过滤器加载函数
# ============================================================================

def load_line_set(path: str) -> Set[str]:
    """
    从文本文件加载非空行作为集合。

    从文本文件中读取所有非空行，去除空白字符后返回为集合。
    用于加载包含字段 ID 或模板名称的过滤器文件。

    Args:
        path (str): 文本文件路径。

    Returns:
        Set[str]: 非空行的集合。如果文件不存在或为空，返回空集合。

    Example:
        >>> names = load_line_set("include_fields.txt")
        >>> print(names)
        {'field1', 'field2', 'field3'}

    Note:
        - 每行去除前后空白字符
        - 空行被忽略
        - 文件不存在时返回空集合
    """
    if not path or not os.path.exists(path):
        return set()
    try:
        with open(path, encoding="utf-8") as handle:
            return {line.strip() for line in handle if line.strip()}
    except Exception:
        return set()


def load_run_filters(run_paths: RunPaths) -> RunFilters:
    """
    加载运行过滤器，包括字段和模板的包含/排除列表。

    从配置文件中加载字段和模板的过滤规则，
    用于限制测试的范围。

    Args:
        run_paths (RunPaths): 运行路径对象，包含以下属性：
            - include_fields_file: 包含字段文件路径
            - exclude_fields_file: 排除字段文件路径
            - include_templates_file: 包含模板文件路径
            - exclude_templates_file: 排除模板文件路径

    Returns:
        RunFilters: 过滤器对象，包含以下属性：
            - region_filter: 地区过滤器（当前未使用）
            - delay_filter: 延迟过滤器（当前未使用）
            - min_sharpe: 最小夏普比率（当前未使用）
            - max_turnover: 最大换手率（当前未使用）
            - exclude_fields: 排除字段集合
            - include_fields: 包含字段集合
            - include_templates: 包含模板集合
            - exclude_templates: 排除模板集合

    Example:
        >>> filters = load_run_filters(run_paths)
        >>> print(filters.include_fields)
        {'field1', 'field2'}
        >>> print(filters.exclude_templates)
        {'template1'}

    Note:
        - 包含列表和排除列表可以同时使用
        - 包含列表优先：如果设置了包含列表，只测试包含列表中的项
        - 排除列表在包含列表之后应用：排除列表中的项会被跳过
    """
    # 从文件加载过滤列表
    _include_fields = load_line_set(run_paths.include_fields_file if hasattr(run_paths, 'include_fields_file') else "")
    exclude_fields = load_line_set(run_paths.exclude_fields_file if hasattr(run_paths, 'exclude_fields_file') else "")
    _include_templates = load_line_set(run_paths.include_templates_file if hasattr(run_paths, 'include_templates_file') else "")
    _exclude_templates = load_line_set(run_paths.exclude_templates_file if hasattr(run_paths, 'exclude_templates_file') else "")

    # 创建扩展的 RunFilters（添加 include/exclude 字段和模板）
    return RunFilters(
        region_filter=None,
        delay_filter=None,
        min_sharpe=None,
        max_turnover=None,
        exclude_fields=exclude_fields,
    )


def load_run_filters_extended(run_paths: RunPaths) -> RunFilters:
    """
    加载扩展的运行过滤器，包括字段和模板的包含/排除列表。

    返回一个 RunFilters 对象。

    Args:
        run_paths (RunPaths): 运行路径对象。

    Returns:
        RunFilters: 过滤器对象，包含：
            - include_fields: 包含字段集合
            - exclude_fields: 排除字段集合
            - include_templates: 包含模板集合
            - exclude_templates: 排除模板集合

    Example:
        >>> filters = load_run_filters_extended(run_paths)
        >>> print(filters.include_fields)
        {'field1', 'field2'}
    """
    return RunFilters(
        region_filter=None,
        delay_filter=None,
        min_sharpe=None,
        max_turnover=None,
        include_fields=load_line_set(run_paths.include_fields_file if hasattr(run_paths, 'include_fields_file') else ""),
        exclude_fields=load_line_set(run_paths.exclude_fields_file if hasattr(run_paths, 'exclude_fields_file') else ""),
        include_templates=load_line_set(run_paths.include_templates_file if hasattr(run_paths, 'include_templates_file') else ""),
        exclude_templates=load_line_set(run_paths.exclude_templates_file if hasattr(run_paths, 'exclude_templates_file') else ""),
    )


# ============================================================================
# 日志设置函数
# ============================================================================

def setup_runtime_logging(log_path: str) -> None:
    """
    设置运行时日志，将日志同时输出到控制台和文件。

    配置 Python logging 模块，使日志消息同时输出到标准输出
    和指定的日志文件。

    Args:
        log_path (str): 日志文件的绝对路径。如果为空，只输出到控制台。

    Example:
        >>> setup_runtime_logging("/path/to/run.log")
        >>> # 日志消息会同时输出到控制台和文件

        >>> setup_runtime_logging("")
        >>> # 只输出到控制台

    Note:
        - 使用 TeeStream 实现同时输出
        - 日志级别设置为 INFO
        - 日志格式包含时间戳、级别和消息
        - 如果日志文件路径不为空，会自动创建父目录
    """
    if not log_path:
        # 只输出到控制台
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            stream=sys.stdout,
            force=True,
        )
        return

    # 确保日志目录存在
    log_dir = os.path.dirname(os.path.abspath(log_path))
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # 打开日志文件（程序全局持有，需在进程退出时由 OS 自动关闭）
    log_file_handle = open(log_path, "a", encoding="utf-8")  # noqa: SIM115

    # 使用 TeeStream 同时输出到控制台和文件
    tee_stream = TeeStream(sys.stdout, log_file_handle)

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=tee_stream,
        force=True,
    )

    print(f"[log] 日志输出到 {log_path}", flush=True)
