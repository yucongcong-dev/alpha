#!/usr/bin/env python3
"""
健康检查系统
提供系统状态监控和健康报告功能
"""

from __future__ import annotations

import os
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"      # 健康
    DEGRADED = "degraded"    # 降级
    UNHEALTHY = "unhealthy"  # 不健康
    UNKNOWN = "unknown"      # 未知


class CheckType(Enum):
    """检查类型"""
    SYSTEM = "system"        # 系统级别检查
    SERVICE = "service"      # 服务级别检查
    RESOURCE = "resource"    # 资源级别检查
    CUSTOM = "custom"        # 自定义检查


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    name: str
    status: HealthStatus
    check_type: CheckType
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency: float = 0.0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "type": self.check_type.value,
            "message": self.message,
            "details": self.details,
            "latency_ms": round(self.latency * 1000, 2),
            "timestamp": self.timestamp,
        }
    
    def __str__(self) -> str:
        return f"[{self.status.value}] {self.name}: {self.message}"


class HealthCheck(ABC):
    """健康检查基类"""
    
    def __init__(self, name: str, check_type: CheckType = CheckType.CUSTOM):
        self.name = name
        self.check_type = check_type
    
    @abstractmethod
    def check(self) -> HealthCheckResult:
        """执行检查"""
        pass
    
    def get_name(self) -> str:
        """获取检查名称"""
        return self.name
    
    def get_type(self) -> CheckType:
        """获取检查类型"""
        return self.check_type


class DiskSpaceCheck(HealthCheck):
    """磁盘空间检查"""
    
    def __init__(self, path: str = "/", min_free_gb: float = 1.0):
        super().__init__("disk_space", CheckType.RESOURCE)
        self.path = path
        self.min_free_gb = min_free_gb
    
    def check(self) -> HealthCheckResult:
        start_time = time.time()
        
        try:
            if not os.path.exists(self.path):
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    check_type=self.check_type,
                    message=f"路径不存在: {self.path}"
                )
            
            free_bytes, total_bytes = self._get_disk_space(self.path)
            free_gb = free_bytes / (1024 ** 3)
            total_gb = total_bytes / (1024 ** 3)
            
            details = {
                "path": self.path,
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "min_required_gb": self.min_free_gb,
                "free_percent": round((free_bytes / total_bytes) * 100, 2) if total_bytes > 0 else 0,
            }
            
            if free_gb < self.min_free_gb:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    check_type=self.check_type,
                    message=f"磁盘空间不足: {free_gb:.2f}GB < {self.min_free_gb}GB",
                    details=details,
                    latency=time.time() - start_time
                )
            elif free_gb < self.min_free_gb * 2:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    check_type=self.check_type,
                    message=f"磁盘空间偏低: {free_gb:.2f}GB",
                    details=details,
                    latency=time.time() - start_time
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    check_type=self.check_type,
                    message=f"磁盘空间充足: {free_gb:.2f}GB",
                    details=details,
                    latency=time.time() - start_time
                )
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                check_type=self.check_type,
                message=f"检查失败: {e}",
                latency=time.time() - start_time
            )
    
    def _get_disk_space(self, path: str) -> Tuple[int, int]:
        """获取磁盘空间（跨平台兼容）"""
        if os.name == 'nt':
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(path),
                None,
                ctypes.pointer(total_bytes),
                ctypes.pointer(free_bytes)
            )
            return (free_bytes.value, total_bytes.value)
        else:
            stat = os.statvfs(path)
            return (stat.f_bavail * stat.f_frsize, stat.f_blocks * stat.f_frsize)


class MemoryCheck(HealthCheck):
    """内存检查"""
    
    def __init__(self, min_free_percent: float = 10.0):
        super().__init__("memory", CheckType.RESOURCE)
        self.min_free_percent = min_free_percent
    
    def check(self) -> HealthCheckResult:
        start_time = time.time()
        
        try:
            import psutil
            
            mem = psutil.virtual_memory()
            free_percent = mem.available / mem.total * 100
            
            details = {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "used_percent": round(mem.percent, 2),
                "free_percent": round(free_percent, 2),
            }
            
            if free_percent < self.min_free_percent:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    check_type=self.check_type,
                    message=f"内存不足: {free_percent:.1f}% < {self.min_free_percent}%",
                    details=details,
                    latency=time.time() - start_time
                )
            elif free_percent < self.min_free_percent * 2:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    check_type=self.check_type,
                    message=f"内存偏低: {free_percent:.1f}%",
                    details=details,
                    latency=time.time() - start_time
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    check_type=self.check_type,
                    message=f"内存充足: {free_percent:.1f}%",
                    details=details,
                    latency=time.time() - start_time
                )
        
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                check_type=self.check_type,
                message="psutil 未安装，无法检查内存",
                latency=time.time() - start_time
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                check_type=self.check_type,
                message=f"检查失败: {e}",
                latency=time.time() - start_time
            )


class CPULoadCheck(HealthCheck):
    """CPU负载检查"""
    
    def __init__(self, max_load_percent: float = 90.0, interval: float = 1.0):
        super().__init__("cpu_load", CheckType.RESOURCE)
        self.max_load_percent = max_load_percent
        self.interval = interval
    
    def check(self) -> HealthCheckResult:
        start_time = time.time()
        
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=self.interval)
            
            details = {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": round(cpu_percent, 2),
                "max_allowed_percent": self.max_load_percent,
            }
            
            if cpu_percent > self.max_load_percent:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    check_type=self.check_type,
                    message=f"CPU负载过高: {cpu_percent:.1f}%",
                    details=details,
                    latency=time.time() - start_time
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    check_type=self.check_type,
                    message=f"CPU负载正常: {cpu_percent:.1f}%",
                    details=details,
                    latency=time.time() - start_time
                )
        
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                check_type=self.check_type,
                message="psutil 未安装，无法检查CPU",
                latency=time.time() - start_time
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                check_type=self.check_type,
                message=f"检查失败: {e}",
                latency=time.time() - start_time
            )


class PythonVersionCheck(HealthCheck):
    """Python版本检查"""
    
    def __init__(self, min_version: Tuple[int, int] = (3, 8)):
        super().__init__("python_version", CheckType.SYSTEM)
        self.min_version = min_version
    
    def check(self) -> HealthCheckResult:
        start_time = time.time()
        
        try:
            current_version = sys.version_info[:2]
            
            details = {
                "current_version": f"{current_version[0]}.{current_version[1]}",
                "min_required_version": f"{self.min_version[0]}.{self.min_version[1]}",
                "full_version": sys.version,
            }
            
            if current_version < self.min_version:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    check_type=self.check_type,
                    message=f"Python版本过低: {current_version[0]}.{current_version[1]} < {self.min_version[0]}.{self.min_version[1]}",
                    details=details,
                    latency=time.time() - start_time
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    check_type=self.check_type,
                    message=f"Python版本符合要求: {current_version[0]}.{current_version[1]}",
                    details=details,
                    latency=time.time() - start_time
                )
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                check_type=self.check_type,
                message=f"检查失败: {e}",
                latency=time.time() - start_time
            )


class ConfigCheck(HealthCheck):
    """配置检查"""
    
    def __init__(self):
        super().__init__("configuration", CheckType.SYSTEM)
    
    def check(self) -> HealthCheckResult:
        start_time = time.time()
        
        try:
            from alpha.config.unified_manager import UnifiedConfigManager
            
            manager = UnifiedConfigManager.get_instance()
            errors = manager.validate()
            
            details = {
                "config_sources": [s.value for s in manager.get_sources()],
                "has_schema": manager.has_schema(),
                "validation_errors": errors,
            }
            
            if errors:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED if len(errors) < 5 else HealthStatus.UNHEALTHY,
                    check_type=self.check_type,
                    message=f"配置验证失败: {len(errors)} 个错误",
                    details=details,
                    latency=time.time() - start_time
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    check_type=self.check_type,
                    message="配置验证通过",
                    details=details,
                    latency=time.time() - start_time
                )
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                check_type=self.check_type,
                message=f"检查失败: {e}",
                latency=time.time() - start_time
            )


class NetworkCheck(HealthCheck):
    """网络连接检查"""
    
    def __init__(self, url: str = "https://api.worldquantbrain.com", timeout: float = 5.0):
        super().__init__("network", CheckType.SERVICE)
        self.url = url
        self.timeout = timeout
    
    def check(self) -> HealthCheckResult:
        start_time = time.time()
        
        try:
            import urllib.request
            
            try:
                response = urllib.request.urlopen(self.url, timeout=self.timeout)
                status_code = response.getcode()
                
                details = {
                    "url": self.url,
                    "status_code": status_code,
                    "response_time_ms": round((time.time() - start_time) * 1000, 2),
                }
                
                if 200 <= status_code < 300:
                    return HealthCheckResult(
                        name=self.name,
                        status=HealthStatus.HEALTHY,
                        check_type=self.check_type,
                        message=f"网络连接正常: {status_code}",
                        details=details,
                        latency=time.time() - start_time
                    )
                else:
                    return HealthCheckResult(
                        name=self.name,
                        status=HealthStatus.DEGRADED,
                        check_type=self.check_type,
                        message=f"网络响应异常: {status_code}",
                        details=details,
                        latency=time.time() - start_time
                    )
            except urllib.error.HTTPError as e:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    check_type=self.check_type,
                    message=f"HTTP错误: {e.code}",
                    latency=time.time() - start_time
                )
            except urllib.error.URLError as e:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    check_type=self.check_type,
                    message=f"网络连接失败: {e.reason}",
                    latency=time.time() - start_time
                )
        
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                check_type=self.check_type,
                message=f"检查失败: {e}",
                latency=time.time() - start_time
            )


class CustomHealthCheck(HealthCheck):
    """自定义健康检查"""
    
    def __init__(self, name: str, check_func: Callable[[], Tuple[HealthStatus, str, Dict[str, Any]]]):
        super().__init__(name, CheckType.CUSTOM)
        self.check_func = check_func
    
    def check(self) -> HealthCheckResult:
        start_time = time.time()
        
        try:
            status, message, details = self.check_func()
            return HealthCheckResult(
                name=self.name,
                status=status,
                check_type=self.check_type,
                message=message,
                details=details,
                latency=time.time() - start_time
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                check_type=self.check_type,
                message=f"检查失败: {e}",
                latency=time.time() - start_time
            )


class HealthChecker:
    """健康检查管理器"""
    
    def __init__(self):
        self._checks: Dict[str, HealthCheck] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._last_check_time: float = 0.0
    
    def register_check(self, check: HealthCheck) -> None:
        """注册健康检查"""
        self._checks[check.get_name()] = check
    
    def unregister_check(self, name: str) -> None:
        """注销健康检查"""
        self._checks.pop(name, None)
    
    def get_checks(self) -> List[HealthCheck]:
        """获取所有检查"""
        return list(self._checks.values())
    
    def run_all_checks(self) -> List[HealthCheckResult]:
        """运行所有健康检查"""
        results = []
        
        for check in self._checks.values():
            try:
                result = check.check()
                results.append(result)
                self._last_results[check.get_name()] = result
            except Exception as e:
                results.append(HealthCheckResult(
                    name=check.get_name(),
                    status=HealthStatus.UNKNOWN,
                    check_type=check.get_type(),
                    message=f"检查执行失败: {e}"
                ))
        
        self._last_check_time = time.time()
        return results
    
    def run_check(self, name: str) -> Optional[HealthCheckResult]:
        """运行单个检查"""
        check = self._checks.get(name)
        if check:
            result = check.check()
            self._last_results[name] = result
            return result
        return None
    
    def get_overall_status(self) -> HealthStatus:
        """获取总体健康状态"""
        if not self._last_results:
            return HealthStatus.UNKNOWN
        
        statuses = [r.status for r in self._last_results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
    
    def generate_report(self) -> Dict[str, Any]:
        """生成健康报告"""
        results = self.run_all_checks()
        overall_status = self.get_overall_status()
        
        report = {
            "timestamp": time.time(),
            "overall_status": overall_status.value,
            "check_count": len(results),
            "healthy_count": sum(1 for r in results if r.status == HealthStatus.HEALTHY),
            "degraded_count": sum(1 for r in results if r.status == HealthStatus.DEGRADED),
            "unhealthy_count": sum(1 for r in results if r.status == HealthStatus.UNHEALTHY),
            "unknown_count": sum(1 for r in results if r.status == HealthStatus.UNKNOWN),
            "total_latency_ms": round(sum(r.latency for r in results) * 1000, 2),
            "checks": [r.to_dict() for r in results],
        }
        
        return report
    
    def get_last_results(self) -> Dict[str, HealthCheckResult]:
        """获取上次检查结果"""
        return dict(self._last_results)
    
    def reset(self) -> None:
        """重置状态"""
        self._last_results.clear()
        self._last_check_time = 0.0


# 全局健康检查器
_global_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器"""
    global _global_health_checker
    if _global_health_checker is None:
        _global_health_checker = HealthChecker()
        
        _global_health_checker.register_check(PythonVersionCheck())
        _global_health_checker.register_check(DiskSpaceCheck())
        _global_health_checker.register_check(MemoryCheck())
        _global_health_checker.register_check(CPULoadCheck())
        _global_health_checker.register_check(ConfigCheck())
    
    return _global_health_checker


def set_health_checker(checker: HealthChecker) -> None:
    """设置全局健康检查器"""
    global _global_health_checker
    _global_health_checker = checker


def run_health_checks() -> List[HealthCheckResult]:
    """运行所有健康检查"""
    return get_health_checker().run_all_checks()


def get_health_report() -> Dict[str, Any]:
    """获取健康报告"""
    return get_health_checker().generate_report()