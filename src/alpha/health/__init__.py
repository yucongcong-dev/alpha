"""
健康检查模块

提供系统状态监控和健康报告功能。

核心功能：
- HealthChecker: 健康检查管理器
- HealthCheck: 健康检查基类（可扩展）
- 内置检查: PythonVersionCheck, DiskSpaceCheck, MemoryCheck, CPULoadCheck, ConfigCheck, NetworkCheck
- HealthStatus: 健康状态枚举（HEALTHY/DEGRADED/UNHEALTHY/UNKNOWN）

使用示例：
    from alpha.health import get_health_checker, run_health_checks, get_health_report

    # 获取健康检查器
    checker = get_health_checker()

    # 运行所有检查
    results = run_health_checks()

    # 获取健康报告
    report = get_health_report()

    # 注册自定义检查
    from alpha.health.checks import CustomHealthCheck, HealthStatus

    def my_check():
        return HealthStatus.HEALTHY, "自定义检查通过", {}

    checker.register_check(CustomHealthCheck("my_check", my_check))
"""

from __future__ import annotations

from .checks import (
    CheckType,
    ConfigCheck,
    CPULoadCheck,
    CustomHealthCheck,
    DiskSpaceCheck,
    HealthCheck,
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    MemoryCheck,
    NetworkCheck,
    PythonVersionCheck,
    get_health_checker,
    get_health_report,
    run_health_checks,
    set_health_checker,
)

__all__ = [
    "CPULoadCheck",
    "CheckType",
    "ConfigCheck",
    "CustomHealthCheck",
    "DiskSpaceCheck",
    "HealthCheck",
    "HealthCheckResult",
    "HealthChecker",
    "HealthStatus",
    "MemoryCheck",
    "NetworkCheck",
    "PythonVersionCheck",
    "get_health_checker",
    "get_health_report",
    "run_health_checks",
    "set_health_checker",
]
