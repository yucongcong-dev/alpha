"""Runtime mode and logging setting declarations."""

from __future__ import annotations

from .settings_spec_types import SettingSpec
from .strategy_profiles import STRATEGY_PROFILE_CHOICES

RUN_MODE_CHOICES = ("smoke", "normal", "full")

RUNTIME_SETTINGS = (
    SettingSpec(
        "strategy_profile",
        ("runtime", "strategy_profile"),
        "explore",
        "--strategy-profile",
        section="runtime_flags",
        fallback="explore",
        choices=STRATEGY_PROFILE_CHOICES,
        help="运行策略标签：explore=广覆盖探索，refine=反馈邻域优化，candidate-focused=候选质量收敛",
    ),
    SettingSpec(
        "run_mode",
        None,
        "",
        "--run-mode",
        choices=RUN_MODE_CHOICES,
        help="运行模式：smoke=冒烟测试（1 字段/1 模板），normal=常规（默认），full=全量搜索（受 --max-new-simulations 预算限制）；传 normal 可覆盖 YAML runtime.smoke_test/full_run=true",
        kind="run_mode",
    ),
    SettingSpec("smoke_test", ("runtime", "smoke_test"), False, section="planning", fallback=False),
    SettingSpec(
        "dry_run_plan",
        ("runtime", "dry_run_plan"),
        False,
        "--dry-run-plan",
        section="planning",
        fallback=False,
        kind="bool_pair",
        help="仅打印计划，不创建模拟",
        help_disable="关闭干运行模式（覆盖 YAML runtime.dry_run_plan=true）",
    ),
    SettingSpec("full_run", ("runtime", "full_run"), False, section="planning", fallback=False),
    SettingSpec(
        "verbose",
        ("runtime", "verbose"),
        False,
        "--verbose",
        section="runtime_flags",
        fallback=False,
        kind="bool_pair",
        help="详细日志模式",
        help_disable="关闭详细日志模式（覆盖 YAML runtime.verbose=true）",
    ),
    SettingSpec(
        "quiet",
        ("runtime", "quiet"),
        False,
        "--quiet",
        section="runtime_flags",
        fallback=False,
        kind="bool_pair",
        help="安静模式",
        help_disable="关闭安静模式（覆盖 YAML runtime.quiet=true）",
    ),
)
