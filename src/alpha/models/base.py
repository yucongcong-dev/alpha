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
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import time
from typing import Any

# ============================================================================
# 类型别名定义
# ============================================================================

TemplateLibrary = dict[str, list[dict[str, Any]]]
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

SettingsVariant = dict[str, Any]
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
        ...     failed_checks=[{"name": "LOW_SHARPE", "value": 0.8, "limit": 1.0}],
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

    simulation_id: str | None = None
    """模拟任务的 ID"""

    alpha_id: str | None = None
    """Alpha 表达式的 ID"""

    status: str = "unknown"
    """当前状态"""

    submittable: bool | None = None
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

    failed_stage: str | None = None
    """失败的阶段名称"""

    failed_checks: list[dict[str, Any]] | None = None
    """失败的检查项列表"""

    def is_successful(self) -> bool:
        """
        判断测试是否成功（可提交）。

        Returns:
            bool: 如果字段可提交，返回 True；否则返回 False。
        """
        return self.submittable is True

    def to_dict(self) -> dict[str, Any]:
        """
        将结果对象转换为字典，用于 JSON 序列化。

        使用此方法替代直接访问 __dict__，确保未来如果改用 __slots__
        或其他存储方式时不会破坏序列化逻辑。

        Returns:
            dict[str, Any]: 包含所有字段值的字典。

        Example:
            >>> result = FieldTestResult(field_id="sales", ...)
            >>> data = result.to_dict()
            >>> print(data["field_id"])
            sales
        """
        return {
            "field_id": self.field_id,
            "field_type": self.field_type,
            "field_name": self.field_name,
            "template_name": self.template_name,
            "simulation_id": self.simulation_id,
            "alpha_id": self.alpha_id,
            "status": self.status,
            "submittable": self.submittable,
            "submitted": self.submitted,
            "message": self.message,
            "expression": self.expression,
            "settings_fingerprint": self.settings_fingerprint,
            "template_library_fingerprint": self.template_library_fingerprint,
            "failed_stage": self.failed_stage,
            "failed_checks": self.failed_checks,
        }

    def __str__(self) -> str:
        """
        返回结果的字符串表示。

        Returns:
            str: 格式化的结果字符串。
        """
        status_symbol = "✓" if self.submittable else "✗"
        return f"FieldTestResult({self.field_name}/{self.template_name}: {status_symbol})"


@dataclass
class FieldTestContext:
    """
    字段测试运行上下文数据类。

    封装 run_field_test 各阶段中反复传递的元数据，
    避免每个 build_failure_result / FieldTestResult 调用都重复 8+ 个参数。

    用于将 200+ 行的 run_field_test 拆分为独立的阶段函数。

    Attributes:
        field_id: 字段唯一标识符。
        field_type: 字段类型。
        field_name: 字段名称。
        template_name: 模板名称。
        expression: Alpha 表达式。
        settings_fingerprint: 设置配置指纹。
        template_library_fingerprint: 模板库指纹。
    """

    field_id: str
    field_type: str
    field_name: str
    template_name: str
    expression: str
    settings_fingerprint: str = ""
    template_library_fingerprint: str = ""

    def failure(
        self,
        *,
        failed_stage: str,
        message: str,
        simulation_id: str | None = None,
        alpha_id: str | None = None,
        status: str = "error",
        failed_checks: list[dict[str, Any]] | None = None,
    ) -> FieldTestResult:
        """构建与上下文绑定的失败结果对象。"""
        return FieldTestResult(
            field_id=self.field_id,
            field_type=self.field_type,
            field_name=self.field_name,
            template_name=self.template_name,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
            status=status,
            submittable=False,
            submitted=False,
            message=message,
            expression=self.expression,
            settings_fingerprint=self.settings_fingerprint,
            template_library_fingerprint=self.template_library_fingerprint,
            failed_stage=failed_stage,
            failed_checks=failed_checks,
        )

    def success(
        self,
        *,
        simulation_id: str | None,
        alpha_id: str | None,
        submittable: bool | None,
        submitted: bool,
        message: str,
        status: str = "simulated",
        failed_checks: list[dict[str, Any]] | None = None,
    ) -> FieldTestResult:
        """构建与上下文绑定的成功/正常结果对象。"""
        return FieldTestResult(
            field_id=self.field_id,
            field_type=self.field_type,
            field_name=self.field_name,
            template_name=self.template_name,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
            status=status,
            submittable=submittable,
            submitted=submitted,
            message=message,
            expression=self.expression,
            settings_fingerprint=self.settings_fingerprint,
            template_library_fingerprint=self.template_library_fingerprint,
            failed_checks=failed_checks,
        )


@dataclass
class TemplateBuildContext:
    """
    模板队列构建的只读上下文数据类。

    将 build_pending_templates_for_field 中反复透传的配置
    收敛为单个对象，从 11 个参数减少到 4 个。

    Attributes:
        args: 命令行参数命名空间。
        all_fields: 所有字段列表。
        template_library: 模板库字典。
        field_feedback: 按字段 ID 组织的反馈字典。
        global_failed_check_counts: 全局失败检查计数。
        include_templates: 包含模板集合。
        exclude_templates: 排除模板集合。
        use_dataset_heuristics: 是否使用数据集启发式。
    """

    args: Any = field(default=None)
    all_fields: Sequence[Any] = field(default_factory=list)
    template_library: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    field_feedback: dict[str, dict[str, Any]] = field(default_factory=dict)
    global_failed_check_counts: dict[str, int] = field(default_factory=dict)
    include_templates: set[str] = field(default_factory=set)
    exclude_templates: set[str] = field(default_factory=set)
    use_dataset_heuristics: bool = False


@dataclass
class FutureCompletionContext:
    """
    future 完成处理的不可变配置上下文。

    将 handle_completed_future 中透传的只读配置收敛，
    从 9 个参数减少到 6 个。

    Attributes:
        args: 命令行参数命名空间。
        settings_fingerprint: 设置配置指纹。
        template_library_fingerprint: 模板库指纹。
        run_config: 运行配置（可选）。
    """

    args: Any = field(default=None)
    settings_fingerprint: str = ""
    template_library_fingerprint: str = ""
    run_config: dict[str, Any] | None = None


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
        fields_cache_file (str): 字段缓存文件的绝对路径。
        template_library_file (str): 模板库文件的绝对路径。
        output (str): 结果输出文件的绝对路径。
        feedback_output (str): 反馈输出文件的绝对路径。
        creds_file (str): 凭证文件的绝对路径。
        creds_key_file (str): 凭证密钥文件的绝对路径。
        include_fields_file (str): 包含字段文件的绝对路径。
        exclude_fields_file (str): 排除字段文件的绝对路径。
        include_templates_file (str): 包含模板文件的绝对路径。
        exclude_templates_file (str): 排除模板文件的绝对路径。

    Example:
        >>> paths = RunPaths(
        ...     results_dir="/path/to/results",
        ...     log_file="/path/to/results/run.log",
        ...     state_file="/path/to/results/state.json",
        ...     checkpoint_file="/path/to/results/checkpoint.pkl",
        ...     fields_cache_file="/path/to/fields_cache.json",
        ...     template_library_file="/path/to/template_library.json",
        ...     output="/path/to/results.json",
        ...     feedback_output="/path/to/feedback.json",
        ...     creds_file="/path/to/creds.json",
        ...     creds_key_file="/path/to/creds.key",
        ...     include_fields_file="",
        ...     exclude_fields_file="",
        ...     include_templates_file="",
        ...     exclude_templates_file="",
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

    fields_cache_file: str = ""
    """字段缓存文件的绝对路径"""

    template_library_file: str = ""
    """模板库文件的绝对路径"""

    output: str = ""
    """结果输出文件的绝对路径"""

    feedback_output: str = ""
    """反馈输出文件的绝对路径"""

    creds_file: str = ""
    """凭证文件的绝对路径"""

    creds_key_file: str = ""
    """凭证密钥文件的绝对路径"""

    include_fields_file: str = ""
    """包含字段文件的绝对路径"""

    exclude_fields_file: str = ""
    """排除字段文件的绝对路径"""

    include_templates_file: str = ""
    """包含模板文件的绝对路径"""

    exclude_templates_file: str = ""
    """排除模板文件的绝对路径"""


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
        """判断是否正在冷却中（cooldown_until 大于当前时间）。"""
        return self.cooldown_until > 0 and time.monotonic() < self.cooldown_until

    def can_restore_concurrency(self) -> bool:
        """判断是否可以恢复正常的并发度（冷却已结束且当前并发不等于最大并发）。"""
        return (
            self.cooldown_until > 0
            and time.monotonic() >= self.cooldown_until
            and self.runtime_max_workers != self.max_workers
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

    region_filter: list[str] | None = None
    """地区过滤器列表"""

    delay_filter: list[int] | None = None
    """延迟过滤器列表"""

    min_sharpe: float | None = None
    """最小夏普比率阈值"""

    max_turnover: float | None = None
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
        ...     global_failed_check_counts={"LOW_SHARPE": 10},
        ... )
    """

    existing_results: list[FieldTestResult] = field(default_factory=list)
    """已存在的历史结果列表"""

    attempted_keys: set[tuple[str, str, str, str]] = field(default_factory=set)
    """已经尝试过的组合键集合"""

    template_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    """按模板名称聚合的历史统计信息"""

    field_feedback: dict[str, dict[str, Any]] = field(default_factory=dict)
    """按字段 ID 组织的优化反馈信息"""

    global_failed_check_counts: dict[str, int] = field(default_factory=dict)
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

    results: list[FieldTestResult]
    """已完成的测试结果列表"""

    attempted_keys: set[tuple[str, str, str, str]]
    """已尝试的模板键集合"""

    template_stats: dict[str, dict[str, int]]
    """模板统计数据字典"""

    pending_futures: dict[Any, dict[str, Any]]
    """待处理的异步任务字典"""

    field_queue_busy_counts: dict[str, int]
    """字段队列拥塞计数"""

    skipped_fields_due_to_queue: set[str]
    """因队列拥塞而跳过的字段集合"""

    last_submission_at: float = 0.0
    """上次提交时间（单调时钟）"""
