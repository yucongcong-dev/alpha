"""
输入输出边界对象。

本模块聚合路径配置与过滤条件等边界数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RunPaths:
    """运行文件路径集合数据类（不可变）。"""

    results_dir: str
    log_file: str
    state_file: str
    checkpoint_file: str
    blacklists_dir: str = ""
    fields_cache_file: str = ""
    template_library_file: str = ""
    output: str = ""
    feedback_output: str = ""
    creds_file: str = ""
    creds_key_file: str = ""
    include_fields_file: str = ""
    exclude_fields_file: str = ""
    include_templates_file: str = ""
    exclude_templates_file: str = ""


@dataclass(frozen=True)
class RunFilters:
    """运行过滤器集合数据类（不可变）。"""

    region_filter: list[str] | None = None
    delay_filter: list[int] | None = None
    min_sharpe: float | None = None
    max_turnover: float | None = None
    include_fields: set[str] = field(default_factory=set)
    exclude_fields: set[str] = field(default_factory=set)
    include_templates: set[str] = field(default_factory=set)
    exclude_templates: set[str] = field(default_factory=set)
