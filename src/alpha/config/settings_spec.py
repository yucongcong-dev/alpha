"""声明式设置表：CLI 参数 / YAML key / 默认值单一来源。

每个 YAML 镜像设置只声明一次：dest、YAML 路径、CLI 名称、类型、默认值、帮助与
dataset profile 标记。消费方：

- ``cli.parser_sections`` 用它生成 argparse 参数；
- ``config.defaults`` 用它做 ``global`` YAML 合并；
- ``cli.arg_resolution`` 用它派生 dataset profile keys。

运行时窄配置 dataclass（``config.application_sections``）仍按 dest 消费，契约由
``tests/unit/test_settings_spec.py`` 的一致性检查锁定。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .strategy_profiles import STRATEGY_PROFILE_CHOICES

RUN_MODE_CHOICES = ("smoke", "normal", "full")


@dataclass(frozen=True, slots=True)
class SettingSpec:
    """一条可被 CLI 与 YAML 共同消费的设置声明。"""

    dest: str
    yaml: tuple[str, ...] | None
    default: Any
    cli: str | None = None
    arg_type: Callable[[str], Any] | type = str
    help: str = ""
    help_disable: str = ""
    choices: tuple[str, ...] = ()
    kind: str = "plain"
    dataset_profile: bool = False


SETTINGS: tuple[SettingSpec, ...] = (
    # ---- global.simulation ----
    SettingSpec("region", ("simulation", "region"), None, "--region", help="地区代码"),
    SettingSpec("universe", ("simulation", "universe"), None, "--universe", help="宇宙代码"),
    SettingSpec(
        "instrument_type",
        ("simulation", "instrumentType"),
        None,
        "--instrument-type",
        help="工具类型",
    ),
    SettingSpec("delay", ("simulation", "delay"), None, "--delay", int, help="延迟天数"),
    SettingSpec("decay", ("simulation", "decay"), None, "--decay", int, help="衰减天数 (Decay)"),
    SettingSpec(
        "neutralization",
        ("simulation", "neutralization"),
        None,
        "--neutralization",
        help="中性化类型 (Neutralization)",
    ),
    SettingSpec(
        "truncation",
        ("simulation", "truncation"),
        None,
        "--truncation",
        float,
        help="截断阈值 (Truncation)",
    ),
    SettingSpec(
        "nan_handling",
        ("simulation", "nanHandling"),
        None,
        "--nan-handling",
        help="NaN 处理方式 (NaN Handling)",
    ),
    SettingSpec(
        "pasteurization",
        ("simulation", "pasteurization"),
        None,
        "--pasteurization",
        help="Pasteurization 开关 (ON/OFF)",
    ),
    SettingSpec(
        "unit_handling",
        ("simulation", "unitHandling"),
        None,
        "--unit-handling",
        help="单位验证 (Unit Handling)",
    ),
    SettingSpec(
        "max_trade",
        ("simulation", "maxTrade"),
        None,
        "--max-trade",
        help="可交易性约束 (Max Trade, ON/OFF)",
    ),
    SettingSpec(
        "language",
        ("simulation", "language"),
        None,
        "--language",
        help="表达式语言 (Language)",
    ),
    SettingSpec(
        "start_date",
        ("simulation", "startDate"),
        None,
        "--start-date",
        help="模拟开始日期 (Start Date, YYYY-MM-DD)，默认使用 config 中的值",
    ),
    SettingSpec(
        "end_date",
        ("simulation", "endDate"),
        None,
        "--end-date",
        help="模拟结束日期 (End Date, YYYY-MM-DD)，默认使用 config 中的值",
    ),
    # ---- global.limits ----
    SettingSpec(
        "limit",
        ("limits", "limit"),
        200,
        "--limit",
        int,
        help="要获取/测试的字段数量；0 表示所有字段",
    ),
    SettingSpec("offset", ("limits", "offset"), 0, "--offset", int, help="字段偏移量"),
    SettingSpec(
        "page_size",
        ("limits", "page_size"),
        50,
        "--page-size",
        int,
        help="分页大小",
        dataset_profile=True,
    ),
    SettingSpec(
        "sleep_between_fields",
        ("limits", "sleep_between_fields"),
        5.0,
        "--sleep-between-fields",
        float,
        help="字段间的休眠时间（增大以降低 API 限流）",
        dataset_profile=True,
    ),
    SettingSpec(
        "max_templates_per_field",
        ("limits", "max_templates_per_field"),
        6,
        "--max-templates-per-field",
        int,
        help="每个字段测试的最大模板数；0 表示所有内置模板",
        dataset_profile=True,
    ),
    SettingSpec(
        "max_templates_per_family",
        ("limits", "max_templates_per_family"),
        1,
        "--max-templates-per-family",
        int,
        help="每个表达式家族保留的最大候选数；0 表示不限制",
    ),
    SettingSpec(
        "max_total_simulations",
        ("limits", "max_total_simulations"),
        0,
        "--max-total-simulations",
        int,
        help="本次启动最多调度的 simulation 数量；0 表示不限制",
    ),
    SettingSpec(
        "field_template_batch_size",
        ("limits", "field_template_batch_size"),
        2,
        "--field-template-batch-size",
        int,
        help="每轮每个字段最多发出的模板/setting 组合数；最小为 1，默认 2",
        dataset_profile=True,
    ),
    SettingSpec(
        "legacy_similarity_penalty",
        ("limits", "legacy_similarity_penalty"),
        42,
        "--legacy-similarity-penalty",
        int,
        help="应用于 raw/group-rank/simple-ratio 等模板的优先级惩罚",
    ),
    # ---- global.concurrency ----
    SettingSpec(
        "max_concurrent_simulations",
        ("concurrency", "max_concurrent_simulations"),
        1,
        "--max-concurrent-simulations",
        int,
        help="并发模拟的最大数量（降低以避免 API 限流）",
        dataset_profile=True,
    ),
    SettingSpec(
        "max_concurrent_creates",
        ("concurrency", "max_concurrent_creates"),
        1,
        "--max-concurrent-creates",
        int,
        help="并发模拟创建请求的最大数量",
        dataset_profile=True,
    ),
    # ---- global.retries ----
    SettingSpec(
        "min_request_interval",
        ("retries", "min_request_interval"),
        2.5,
        "--min-request-interval",
        float,
        help="请求间的最小间隔，用于降低速率限制（增大以应对 API 429）",
        dataset_profile=True,
    ),
    SettingSpec(
        "rate_limit_max_retries",
        ("retries", "rate_limit_max_retries"),
        5,
        "--rate-limit-max-retries",
        int,
        help="速率限制时的最大重试次数",
    ),
    SettingSpec(
        "login_retries",
        ("retries", "login_retries"),
        3,
        "--login-retries",
        int,
        help="登录重试次数",
    ),
    SettingSpec(
        "simulation_create_retries",
        ("retries", "simulation_create_retries"),
        3,
        "--simulation-create-retries",
        int,
        help="模拟创建重试次数",
    ),
    SettingSpec(
        "simulation_poll_retries",
        ("retries", "simulation_poll_retries"),
        3,
        "--simulation-poll-retries",
        int,
        help="模拟轮询重试次数",
    ),
    SettingSpec(
        "simulation_max_polls",
        ("retries", "simulation_max_polls"),
        240,
        "--simulation-max-polls",
        int,
        help="单个模拟的最大轮询次数",
    ),
    SettingSpec(
        "simulation_max_wait_seconds",
        ("retries", "simulation_max_wait_seconds"),
        1800.0,
        "--simulation-max-wait-seconds",
        float,
        help="单个模拟的最大等待时间（秒）",
        dataset_profile=True,
    ),
    SettingSpec(
        "simulation_max_pending_cycles",
        ("retries", "simulation_max_pending_cycles"),
        120,
        "--simulation-max-pending-cycles",
        int,
        help="最大等待周期数",
    ),
    SettingSpec(
        "simulation_max_queue_seconds",
        ("retries", "simulation_max_queue_seconds"),
        600.0,
        "--simulation-max-queue-seconds",
        float,
        help="最大队列等待时间（秒）",
        dataset_profile=True,
    ),
    SettingSpec(
        "queue_busy_cooldown_seconds",
        ("retries", "queue_busy_cooldown_seconds"),
        300.0,
        "--queue-busy-cooldown-seconds",
        float,
        help="队列拥塞后的冷却时间（秒，增大以避免重复触发限流）",
        dataset_profile=True,
    ),
    SettingSpec(
        "queue_busy_retry_limit",
        ("retries", "queue_busy_retry_limit"),
        2,
        "--queue-busy-retry-limit",
        int,
        help="单候选队列拥塞重试上限；0 表示不限制",
    ),
    SettingSpec(
        "check_submission_retries",
        ("retries", "check_submission_retries"),
        3,
        "--check-submission-retries",
        int,
        help="Check Submission 状态轮询次数",
    ),
    # ---- global.filters ----
    SettingSpec(
        "top_fields_by_feedback",
        ("filters", "top_fields_by_feedback"),
        0,
        "--top-fields-by-feedback",
        int,
        help="如果大于 0，仅测试按反馈排序的前 N 个字段",
    ),
    # ---- global.quality ----
    SettingSpec(
        "min_sharpe",
        ("quality", "min_sharpe"),
        1.25,
        "--min-sharpe",
        float,
        help="本地诊断最低 Sharpe 阈值",
    ),
    SettingSpec(
        "min_fitness",
        ("quality", "min_fitness"),
        1.00,
        "--min-fitness",
        float,
        help="本地诊断最低 Fitness 阈值",
    ),
    SettingSpec(
        "min_turnover",
        ("quality", "min_turnover"),
        0.01,
        "--min-turnover",
        float,
        help="本地诊断最低 Turnover 阈值",
    ),
    SettingSpec(
        "max_turnover",
        ("quality", "max_turnover"),
        0.70,
        "--max-turnover",
        float,
        help="本地诊断最高 Turnover 阈值",
    ),
    SettingSpec(
        "max_weight",
        ("quality", "max_weight"),
        0.10,
        "--max-weight",
        float,
        help="本地诊断单股最大权重阈值",
    ),
    # ---- global.expression ----
    SettingSpec(
        "backfill_window",
        ("expression", "backfill_window"),
        240,
        "--backfill-window",
        int,
        help="ts_backfill 时间窗口大小（天）",
    ),
    # ---- global.runtime ----
    SettingSpec(
        "strategy_profile",
        ("runtime", "strategy_profile"),
        "explore",
        "--strategy-profile",
        choices=STRATEGY_PROFILE_CHOICES,
        help="运行策略标签：explore=广覆盖探索，refine=反馈邻域优化，candidate-focused=候选质量收敛",
    ),
    SettingSpec(
        "run_mode",
        None,
        "",
        "--run-mode",
        choices=RUN_MODE_CHOICES,
        help=(
            "运行模式：smoke=冒烟测试（1 字段/1 模板），normal=常规（默认），"
            "full=全量搜索（受 --max-total-simulations 预算限制）；"
            "传 normal 可覆盖 YAML runtime.smoke_test/full_run=true"
        ),
        kind="run_mode",
    ),
    SettingSpec("smoke_test", ("runtime", "smoke_test"), False),
    SettingSpec(
        "dry_run_plan",
        ("runtime", "dry_run_plan"),
        False,
        "--dry-run-plan",
        kind="bool_pair",
        help="仅打印计划，不创建模拟",
        help_disable="关闭干运行模式（覆盖 YAML runtime.dry_run_plan=true）",
    ),
    SettingSpec("full_run", ("runtime", "full_run"), False),
    SettingSpec(
        "verbose",
        ("runtime", "verbose"),
        False,
        "--verbose",
        kind="bool_pair",
        help="详细日志模式",
        help_disable="关闭详细日志模式（覆盖 YAML runtime.verbose=true）",
    ),
    SettingSpec(
        "quiet",
        ("runtime", "quiet"),
        False,
        "--quiet",
        kind="bool_pair",
        help="安静模式",
        help_disable="关闭安静模式（覆盖 YAML runtime.quiet=true）",
    ),
)


def get_setting(dest: str) -> SettingSpec:
    """按 dest 查找设置；未知 dest 抛 KeyError。"""
    for spec in SETTINGS:
        if spec.dest == dest:
            return spec
    raise KeyError(dest)


def yaml_default_settings() -> tuple[SettingSpec, ...]:
    """返回带 YAML 默认值路径的设置。"""
    return tuple(spec for spec in SETTINGS if spec.yaml is not None)


def cli_settings() -> tuple[SettingSpec, ...]:
    """返回暴露 CLI 参数的设置（bool_pair 与 run_mode 由各自 section 处理）。"""
    return tuple(
        spec for spec in SETTINGS if spec.cli is not None and spec.kind in ("plain", "bool_pair")
    )


def dataset_profile_keys() -> tuple[str, ...]:
    """返回可被 dataset profile 覆盖的设置 dest（保持声明顺序）。"""
    return tuple(spec.dest for spec in SETTINGS if spec.dataset_profile)


def settings_by_yaml_section(section: str) -> tuple[SettingSpec, ...]:
    """返回属于指定 global YAML section 的设置。"""
    return tuple(spec for spec in SETTINGS if spec.yaml is not None and spec.yaml[0] == section)
