# -*- coding: utf-8 -*-
"""
数据类模块

本模块定义了 Brain API 客户端使用的各种数据类和类型别名，
用于表示字段测试结果、模板库、运行配置等数据结构。

模块内容：
    - FieldTestResult: 字段测试结果数据类
    - TemplateLibrary: 模板库类型别名
    - SettingsVariant: 设置变体类型别名
    - RunPaths: 运行文件路径集合数据类
    - RuntimeConcurrencyState: 并发调度状态数据类
    - RunFilters: 运行过滤器集合数据类
    - HistoricalRunState: 历史运行状态数据类
    - ExecutionState: 执行状态数据类
    - TeeStream: 日志分流输出类
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TextIO, Tuple


# ============================================================================
# 类型别名定义
# ============================================================================

TemplateLibrary = Dict[str, List[Dict[str, Any]]]
"""
模板库类型别名。

表示一个字典，键为模板类别名称，值为该类别下的模板列表。
每个模板是一个字典，包含模板的各种属性和配置。

Example:
    {
        "momentum": [
            {"name": "ts_momentum", "expression": "ts_delta(close, 5)"},
            {"name": "roc", "expression": "close / ts_lag(close, 10) - 1"}
        ]
    }
"""

SettingsVariant = Dict[str, Any]
"""
设置变体类型别名。

表示一个字典，包含 Alpha 表达式的各种设置参数。
设置变体用于定义不同的运行配置，如不同的地区、延迟等。

Example:
    {
        "region": "USA",
        "delay": 1,
        "decay": 6,
        "neutralization": "MARKET"
    }
"""


# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class FieldTestResult:
    """
    字段模板测试结果数据类。

    用于存储单个字段与模板组合在 API 中的测试结果信息，
    包括字段信息、模拟结果、提交状态、失败检查等详细信息。

    Attributes:
        field_id (str): 字段的唯一标识符。
        field_type (str): 字段类型（如 MATRIX、VECTOR、GROUP 等）。
        field_name (str): 字段名称。
        template_name (str): 使用的模板名称。
        simulation_id (Optional[str]): 模拟任务的 ID。默认为 None。
        alpha_id (Optional[str]): Alpha 表达式的 ID。默认为 None。
        status (str): 当前状态（如 simulated、submitted、error 等）。
        submittable (Optional[bool]): 是否可提交。默认为 None。
        submitted (bool): 是否已提交。默认为 False。
        message (str): 结果消息或错误信息。
        expression (str): 实际使用的 Alpha 表达式。
        settings_fingerprint (str): 设置参数的指纹标识。默认为空字符串。
        template_library_fingerprint (str): 模板库的指纹标识。默认为空字符串。
        failed_stage (Optional[str]): 失败的阶段名称。默认为 None。
        failed_checks (Optional[List[Dict[str, Any]]]): 失败的检查项列表。
            每个检查项包含 name、value、limit 等字段。默认为 None。

    Example:
        >>> result = FieldTestResult(
        ...     field_id="fnd6_sales",
        ...     field_type="MATRIX",
        ...     field_name="sales",
        ...     template_name="ts_mean_20",
        ...     simulation_id="sim_123",
        ...     alpha_id="alpha_456",
        ...     status="simulated",
        ...     submittable=False,
        ...     submitted=False,
        ...     message="LOW_SHARPE",
        ...     expression="rank(ts_mean(sales, 20))",
        ...     failed_checks=[{"name": "LOW_SHARPE", "value": 0.8, "limit": 1.0}]
        ... )
        >>> print(result.field_name)
        sales
        >>> print(result.status)
        simulated
    """

    field_id: str
    """字段的唯一标识符"""

    field_type: str
    """字段类型"""

    field_name: str
    """字段名称"""

    template_name: str
    """使用的模板名称"""

    simulation_id: Optional[str] = None
    """模拟任务的 ID"""

    alpha_id: Optional[str] = None
    """Alpha 表达式的 ID"""

    status: str = "unknown"
    """当前状态"""

    submittable: Optional[bool] = None
    """是否可提交"""

    submitted: bool = False
    """是否已提交"""

    message: str = ""
    """结果消息或错误信息"""

    expression: str = ""
    """实际使用的 Alpha 表达式"""

    settings_fingerprint: str = ""
    """设置参数的指纹标识"""

    template_library_fingerprint: str = ""
    """模板库的指纹标识"""

    failed_stage: Optional[str] = None
    """失败的阶段名称"""

    failed_checks: Optional[List[Dict[str, Any]]] = None
    """失败的检查项列表"""

    def is_successful(self) -> bool:
        """
        判断测试是否成功（可提交）。

        Returns:
            bool: 如果字段可提交，返回 True；否则返回 False。
        """
        return self.submittable is True

    def __str__(self) -> str:
        """
        返回结果的字符串表示。

        Returns:
            str: 格式化的结果字符串。
        """
        status_symbol = "✓" if self.submittable else "✗"
        return f"FieldTestResult({self.field_name}/{self.template_name}: {status_symbol})"


@dataclass(frozen=True)
class RunPaths:
    """
    运行文件路径集合数据类（不可变）。

    用于存储一次运行所需的所有文件路径，
    包括结果目录、日志文件、状态文件等。

    由于是 frozen=True，实例创建后不可修改，
    确保路径配置的一致性。

    Attributes:
        results_dir (str): 结果输出目录的绝对路径。
        log_file (str): 日志文件的绝对路径。
        state_file (str): 状态文件的绝对路径，用于保存运行状态。
        checkpoint_file (str): 检查点文件的绝对路径，用于断点续传。

    Example:
        >>> paths = RunPaths(
        ...     results_dir="/path/to/results",
        ...     log_file="/path/to/results/run.log",
        ...     state_file="/path/to/results/state.json",
        ...     checkpoint_file="/path/to/results/checkpoint.pkl"
        ... )
    """

    results_dir: str
    """结果输出目录的绝对路径"""

    log_file: str
    """日志文件的绝对路径"""

    state_file: str
    """状态文件的绝对路径"""

    checkpoint_file: str
    """检查点文件的绝对路径"""


@dataclass
class RuntimeConcurrencyState:
    """
    并发调度状态数据类。

    用于跟踪和管理运行时的并发任务状态，
    包括最大并发数、当前运行并发数和冷却时间等信息。

    Attributes:
        max_workers (int): 最大并发数限制。默认为 2。
        runtime_max_workers (int): 当前运行时使用的并发数，
            可能会因为拥塞控制而临时降低。默认为 2。
        cooldown_until (float): 冷却结束时间（单调时钟）。
            如果大于 0，表示正在冷却中。默认为 0.0。

    Example:
        >>> state = RuntimeConcurrencyState(max_workers=5, runtime_max_workers=5)
        >>> print(state.max_workers)
        5
        >>> # 检测到拥塞后
        >>> state.runtime_max_workers = 1
        >>> state.cooldown_until = time.monotonic() + 180
    """

    max_workers: int = 2
    """最大并发数限制"""

    runtime_max_workers: int = 2
    """当前运行时使用的并发数"""

    cooldown_until: float = 0.0
    """冷却结束时间（单调时钟），0 表示未冷却"""

    def is_cooling_down(self) -> bool:
        """
        判断是否正在冷却中。

        Returns:
            bool: 如果 cooldown_until 大于当前时间，返回 True；
                否则返回 False。
        """
        import time
        return self.cooldown_until > 0 and time.monotonic() < self.cooldown_until

    def can_restore_concurrency(self) -> bool:
        """
        判断是否可以恢复正常的并发度。

        Returns:
            bool: 如果冷却时间已结束且当前并发数不等于最大并发数，
                返回 True；否则返回 False。
        """
        import time
        return (
            self.cooldown_until > 0 and
            time.monotonic() >= self.cooldown_until and
            self.runtime_max_workers != self.max_workers
        )


@dataclass(frozen=True)
class RunFilters:
    """
    运行过滤器集合数据类（不可变）。

    用于定义运行时的各种过滤条件，
    确保只处理符合条件的数据或 Alpha。

    由于是 frozen=True，实例创建后不可修改。

    Attributes:
        region_filter (Optional[List[str]]): 地区过滤器列表。
            如果指定，只处理这些地区的 Alpha。默认为 None。
        delay_filter (Optional[List[int]]): 延迟过滤器列表。
            如果指定，只处理这些延迟值的 Alpha。默认为 None。
        min_sharpe (Optional[float]): 最小夏普比率阈值。
            如果指定，过滤掉夏普比率低于此值的 Alpha。默认为 None。
        max_turnover (Optional[float]): 最大换手率阈值。
            如果指定，过滤掉换手率高于此值的 Alpha。默认为 None。
        include_fields (set[str]): 包含字段集合。
            如果指定，只处理这些字段。默认为空集合。
        exclude_fields (set[str]): 排除字段集合。
            如果指定，不处理这些字段。默认为空集合。
        include_templates (set[str]): 包含模板集合。
            如果指定，只测试这些模板。默认为空集合。
        exclude_templates (set[str]): 排除模板集合。
            如果指定，不测试这些模板。默认为空集合。

    Example:
        >>> filters = RunFilters(
        ...     region_filter=["USA", "CHN"],
        ...     min_sharpe=1.0,
        ...     max_turnover=0.5,
        ...     include_fields={"sales", "ebitda"},
        ...     exclude_templates={"legacy_raw"},
        ... )
    """

    region_filter: Optional[List[str]] = None
    """地区过滤器列表"""

    delay_filter: Optional[List[int]] = None
    """延迟过滤器列表"""

    min_sharpe: Optional[float] = None
    """最小夏普比率阈值"""

    max_turnover: Optional[float] = None
    """最大换手率阈值"""

    include_fields: set[str] = field(default_factory=set)
    """包含字段集合"""

    exclude_fields: set[str] = field(default_factory=set)
    """排除字段集合"""

    include_templates: set[str] = field(default_factory=set)
    """包含模板集合"""

    exclude_templates: set[str] = field(default_factory=set)
    """排除模板集合"""


@dataclass
class HistoricalRunState:
    """
    历史运行状态数据类。

    用于记录和管理历史运行的详细信息，
    包括已存在的结果、模板统计、字段反馈等派生信号，
    用于续跑和优化迭代。

    Attributes:
        existing_results (List[FieldTestResult]): 已存在的历史结果列表。
        attempted_keys (set[Tuple[str, str, str, str]]): 已经尝试过的
            字段-模板-表达式-设置组合键集合，用于去重。
        template_stats (Dict[str, Dict[str, int]]): 按模板名称聚合的
            历史统计信息，包含 attempted、submittable、errors 等计数。
        field_feedback (Dict[str, Dict[str, Any]]): 按字段 ID 组织的
            优化反馈信息，包含最佳分数、最佳表达式、失败检查计数等。
        global_failed_check_counts (Dict[str, int]): 全局失败检查计数，
            用于指导整体搜索方向。

    Example:
        >>> state = HistoricalRunState(
        ...     existing_results=[result1, result2],
        ...     attempted_keys={("field1", "template1", "expr1", "settings1")},
        ...     template_stats={"template1": {"attempted": 5, "submittable": 2}},
        ...     field_feedback={"field1": {"best_score": 0.5}},
        ...     global_failed_check_counts={"LOW_SHARPE": 10}
        ... )
    """

    existing_results: List[FieldTestResult] = field(default_factory=list)
    """已存在的历史结果列表"""

    attempted_keys: set[Tuple[str, str, str, str]] = field(default_factory=set)
    """已经尝试过的组合键集合"""

    template_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    """按模板名称聚合的历史统计信息"""

    field_feedback: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    """按字段 ID 组织的优化反馈信息"""

    global_failed_check_counts: Dict[str, int] = field(default_factory=dict)
    """全局失败检查计数"""


@dataclass
class ExecutionState:
    """
    执行过程中可变的待运行、跳过与累计结果状态。

    用于跟踪执行过程中的各种状态信息，包括已完成的测试结果、
    待处理的任务、队列拥塞计数等。

    Attributes:
        results (List[FieldTestResult]): 已完成的测试结果列表。
        attempted_keys (set[Tuple[str, str, str, str]]): 已尝试的模板键集合。
        template_stats (Dict[str, Dict[str, int]]): 模板统计数据字典。
        pending_futures (Dict[Future[FieldTestResult], Dict[str, Any]]): 待处理的异步任务字典。
        field_queue_busy_counts (Dict[str, int]): 字段队列拥塞计数。
        skipped_fields_due_to_queue (set[str]): 因队列拥塞而跳过的字段集合。
        last_submission_at (float): 上次提交时间（单调时钟）。默认为 0.0。

    Example:
        >>> state = ExecutionState(
        ...     results=[],
        ...     attempted_keys=set(),
        ...     template_stats={},
        ...     pending_futures={},
        ...     field_queue_busy_counts={},
        ...     skipped_fields_due_to_queue=set(),
        ... )
    """

    results: List[FieldTestResult]
    """已完成的测试结果列表"""

    attempted_keys: set[Tuple[str, str, str, str]]
    """已尝试的模板键集合"""

    template_stats: Dict[str, Dict[str, int]]
    """模板统计数据字典"""

    pending_futures: Dict[Any, Dict[str, Any]]
    """待处理的异步任务字典"""

    field_queue_busy_counts: Dict[str, int]
    """字段队列拥塞计数"""

    skipped_fields_due_to_queue: set[str]
    """因队列拥塞而跳过的字段集合"""

    last_submission_at: float = 0.0
    """上次提交时间（单调时钟）"""


# ============================================================================
# 辅助类定义
# ============================================================================

class TeeStream:
    """
    日志分流输出类。

    将输出同时写入多个文件流，类似于 Unix 的 tee 命令。
    常用于同时将日志输出到控制台和文件。

    Attributes:
        streams (List[TextIO]): 输出流列表。

    Args:
        *streams: 可变数量的输出流对象。
            所有流都必须实现 write() 和 flush() 方法。

    Example:
        >>> import sys
        >>> with open("output.log", "w") as log_file:
        ...     tee = TeeStream(sys.stdout, log_file)
        ...     print("Hello, World!", file=tee)
        ... # "Hello, World!" 会同时输出到控制台和文件

    Note:
        使用完毕后，调用 close() 方法关闭非标准流。
        但不要关闭 sys.stdout 或 sys.stderr。
    """

    def __init__(self, *streams: TextIO) -> None:
        """
        初始化 TeeStream 实例。

        Args:
            *streams: 可变数量的输出流对象。
                所有流都必须实现 write() 和 flush() 方法。
        """
        self.streams: List[TextIO] = list(streams)

    def write(self, message: str) -> int:
        """
        将消息写入所有流。

        Args:
            message: 要写入的消息字符串。

        Returns:
            int: 写入的字节数（返回最后一个流的写入结果）。
        """
        result = 0
        for stream in self.streams:
            result = stream.write(message)
        return result

    def flush(self) -> None:
        """
        刷新所有流的缓冲区。
        """
        for stream in self.streams:
            stream.flush()

    def add_stream(self, stream: TextIO) -> None:
        """
        添加新的输出流。

        Args:
            stream: 要添加的输出流对象。
        """
        self.streams.append(stream)

    def remove_stream(self, stream: TextIO) -> bool:
        """
        移除指定的输出流。

        Args:
            stream: 要移除的输出流对象。

        Returns:
            bool: 如果流存在并被移除，返回 True；否则返回 False。
        """
        try:
            self.streams.remove(stream)
            return True
        except ValueError:
            return False

    def close(self) -> None:
        """
        关闭所有非标准流。

        关闭除 sys.stdout、sys.stderr 和 sys.stdin 之外的所有流。
        这可以避免意外关闭标准输入输出流。
        """
        standard_streams = {sys.stdout, sys.stderr, sys.stdin}
        for stream in self.streams[:]:
            if stream not in standard_streams:
                stream.close()
                self.streams.remove(stream)