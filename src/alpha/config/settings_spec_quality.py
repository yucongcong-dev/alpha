"""Quality setting declarations."""

from __future__ import annotations

from .settings_spec_types import SettingSpec

QUALITY_SETTINGS = (
    SettingSpec(
        "min_sharpe",
        ("quality", "min_sharpe"),
        1.25,
        "--min-sharpe",
        float,
        section="quality",
        fallback=0.0,
        help="本地诊断最低 Sharpe 阈值",
    ),
    SettingSpec(
        "min_fitness",
        ("quality", "min_fitness"),
        1.00,
        "--min-fitness",
        float,
        section="quality",
        fallback=0.0,
        help="本地诊断最低 Fitness 阈值",
    ),
    SettingSpec(
        "min_turnover",
        ("quality", "min_turnover"),
        0.01,
        "--min-turnover",
        float,
        section="quality",
        fallback=0.0,
        help="本地诊断最低 Turnover 阈值",
    ),
    SettingSpec(
        "max_turnover",
        ("quality", "max_turnover"),
        0.70,
        "--max-turnover",
        float,
        section="quality",
        fallback=1.0,
        help="本地诊断最高 Turnover 阈值",
    ),
    SettingSpec(
        "max_weight",
        ("quality", "max_weight"),
        0.10,
        "--max-weight",
        float,
        section="quality",
        fallback=1.0,
        help="本地诊断单股最大权重阈值",
    ),
)
