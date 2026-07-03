#!/usr/bin/env python3
"""
性能监控工具
提供关键操作的性能监控和指标收集
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import functools
import statistics
import threading
import time
from typing import Any, Dict, List, Optional


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"      # 计数器，只增不减
    GAUGE = "gauge"          # 测量值，可增可减
    HISTOGRAM = "histogram"  # 直方图，统计分布
    TIMER = "timer"          # 计时器


@dataclass
class Metric:
    """性能指标"""
    name: str
    type: MetricType
    value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
        }


@dataclass
class TimerStats:
    """计时器统计"""
    count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0

    def update(self, duration: float) -> None:
        """更新统计"""
        self.count += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.avg_time = self.total_time / self.count

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "count": self.count,
            "total_time": self.total_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "avg_time": self.avg_time,
            "p50": self.p50,
            "p90": self.p90,
            "p95": self.p95,
            "p99": self.p99,
        }


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.metrics: List[Metric] = []
        self.timers: Dict[str, List[float]] = {}
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self._lock = threading.RLock()

    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """增加计数器"""
        with self._lock:
            if name not in self.counters:
                self.counters[name] = 0
            self.counters[name] += value

            metric = Metric(
                name=name,
                type=MetricType.COUNTER,
                value=self.counters[name],
                tags=tags or {}
            )
            self.metrics.append(metric)

    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """设置测量值"""
        with self._lock:
            self.gauges[name] = value

            metric = Metric(
                name=name,
                type=MetricType.GAUGE,
                value=value,
                tags=tags or {}
            )
            self.metrics.append(metric)

    def record_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None) -> None:
        """记录计时器"""
        with self._lock:
            if name not in self.timers:
                self.timers[name] = []
            self.timers[name].append(duration)

            metric = Metric(
                name=name,
                type=MetricType.TIMER,
                value=duration,
                tags=tags or {}
            )
            self.metrics.append(metric)

    @contextmanager
    def timer(self, name: str, tags: Optional[Dict[str, str]] = None):
        """计时器上下文管理器"""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start_time
            self.record_timer(name, duration, tags)

    def timer_decorator(self, name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
        """计时器装饰器"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                timer_name = name or f"{func.__module__}.{func.__name__}"
                with self.timer(timer_name, tags):
                    return func(*args, **kwargs)
            return wrapper
        return decorator

    def get_timer_stats(self, name: str) -> Optional[TimerStats]:
        """获取计时器统计"""
        with self._lock:
            if name not in self.timers or not self.timers[name]:
                return None

            durations = self.timers[name]
            stats = TimerStats()

            for duration in durations:
                stats.update(duration)

            # 计算百分位数
            if durations:
                sorted_durations = sorted(durations)
                stats.p50 = sorted_durations[int(len(sorted_durations) * 0.5)]
                stats.p90 = sorted_durations[int(len(sorted_durations) * 0.9)]
                stats.p95 = sorted_durations[int(len(sorted_durations) * 0.95)]
                stats.p99 = sorted_durations[int(len(sorted_durations) * 0.99)]

            return stats

    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        with self._lock:
            summary = {
                "timestamp": datetime.now().isoformat(),
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "timers": {},
                "recent_metrics": [],
            }

            # 添加计时器统计
            for timer_name in self.timers:
                stats = self.get_timer_stats(timer_name)
                if stats:
                    summary["timers"][timer_name] = stats.to_dict()

            # 添加最近指标（最后100个）
            recent_metrics = self.metrics[-100:] if self.metrics else []
            summary["recent_metrics"] = [metric.to_dict() for metric in recent_metrics]

            return summary

    def clear_metrics(self) -> None:
        """清除指标"""
        with self._lock:
            self.metrics.clear()
            self.timers.clear()
            self.counters.clear()
            self.gauges.clear()

    def export_metrics(self, format: str = "json") -> Dict[str, Any]:
        """导出指标"""
        summary = self.get_metrics_summary()

        if format == "json":
            return summary
        else:
            raise ValueError(f"Unsupported format: {format}")


# 全局性能监控器
_global_monitor: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor

def monitor_performance(name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """性能监控装饰器"""
    monitor = get_performance_monitor()
    return monitor.timer_decorator(name, tags)

def record_metric(name: str, value: Any, metric_type: MetricType | str = MetricType.GAUGE,
                  tags: Optional[Dict[str, str]] = None) -> None:
    """记录指标"""
    monitor = get_performance_monitor()

    if isinstance(metric_type, str):
        metric_type = MetricType(metric_type)

    if metric_type == MetricType.COUNTER:
        monitor.increment_counter(name, value, tags)
    elif metric_type == MetricType.GAUGE:
        monitor.set_gauge(name, value, tags)
    elif metric_type == MetricType.TIMER:
        monitor.record_timer(name, value, tags)
    else:
        raise ValueError(f"Unsupported metric type: {metric_type}")


# 关键操作监控
class CriticalOperations:
    """关键操作监控"""

    @staticmethod
    @monitor_performance("api.call")
    def api_call(api_name: str, **kwargs):
        """API调用监控"""
        pass

    @staticmethod
    @monitor_performance("simulation.run")
    def simulation_run(simulation_type: str, **kwargs):
        """模拟运行监控"""
        pass

    @staticmethod
    @monitor_performance("expression.generate")
    def expression_generation(expression_type: str, **kwargs):
        """表达式生成监控"""
        pass

    @staticmethod
    @monitor_performance("data.load")
    def data_loading(data_source: str, **kwargs):
        """数据加载监控"""
        pass


# 示例使用
if __name__ == "__main__":
    # 获取性能监控器
    monitor = get_performance_monitor()

    # 示例：监控API调用
    @monitor_performance("example.api_call")
    def example_api_call(url: str):
        """示例API调用"""
        time.sleep(0.1)  # 模拟API调用延迟
        return f"Response from {url}"

    # 执行测试
    for i in range(5):
        example_api_call(f"https://api.example.com/endpoint/{i}")

    # 增加计数器
    monitor.increment_counter("api.calls.total")
    monitor.increment_counter("api.calls.successful")

    # 设置测量值
    monitor.set_gauge("memory.usage", 123.45)
    monitor.set_gauge("cpu.usage", 78.9)

    # 查看统计
    summary = monitor.get_metrics_summary()
    print("性能指标摘要:")
    print(f"API调用次数: {summary['counters'].get('api.calls.total', 0)}")

    if "example.api_call" in summary["timers"]:
        timer_stats = summary["timers"]["example.api_call"]
        print("示例API调用统计:")
        print(f"  调用次数: {timer_stats['count']}")
        print(f"  平均耗时: {timer_stats['avg_time']:.3f}s")
        print(f"  最小耗时: {timer_stats['min_time']:.3f}s")
        print(f"  最大耗时: {timer_stats['max_time']:.3f}s")
