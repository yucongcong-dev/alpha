"""
命令行参数解析模块。

本模块的核心职责是解析 CLI 参数，并在解析完成后应用
YAML / dataset profile / smoke-test / full-run 等参数覆盖逻辑。

路径归一化、运行配置快照和过滤器/日志辅助逻辑已经拆到
`cli.path_resolution`、`cli.run_config`、`cli.filters`。
本模块仅保留薄兼容导出，避免旧调用方一次性失效。

模块内容：
    - parse_args() -> argparse.Namespace: 解析命令行参数
    - normalize_args_paths(args) -> RunPaths: 兼容导出路径归一化
    - build_run_config_snapshot(args, run_paths) -> Dict: 兼容导出运行配置快照
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ..models.io_types import RunPaths
from ..models.runtime import RunConfigArgs
from .arg_resolution import resolve_cli_args

# 过滤器/日志函数已提取到 cli.filters，此处保留重导出以兼容
from .filters import (  # noqa: F401
    load_line_set,
    load_run_filters,
    load_run_filters_extended,
    setup_runtime_logging,
)
from .parser_schema import (
    build_parser,
    collect_explicit_cli_keys,
    collect_parser_defaults,
)
from .path_resolution import normalize_args_paths as _normalize_args_paths
from .run_config import build_run_config_snapshot as _build_run_config_snapshot

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
    parser = build_parser()

    parser_defaults = collect_parser_defaults(parser)
    explicit_cli_keys = collect_explicit_cli_keys(parser, sys.argv[1:])
    args = parser.parse_args()
    return resolve_cli_args(
        args,
        parser_defaults=parser_defaults,
        explicit_cli_keys=explicit_cli_keys,
    )


# ============================================================================
# 路径标准化函数
# ============================================================================


def normalize_args_paths(args: argparse.Namespace) -> RunPaths:
    """兼容导出：归一化运行路径，但不修改 args。"""
    return _normalize_args_paths(args)


# ============================================================================
# 运行配置快照函数
# ============================================================================


def build_run_config_snapshot(args: RunConfigArgs, run_paths: RunPaths) -> dict[str, Any]:
    """兼容导出：构建运行配置快照。"""
    return _build_run_config_snapshot(args, run_paths)


# 过滤器函数和日志设置已提取到 cli/filters.py
# 通过顶部的 from .filters import ... 提供重导出兼容
