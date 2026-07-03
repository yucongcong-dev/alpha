#!/usr/bin/env python3
"""
测试短期改进的集成功能
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_error_handling_integration():
    """测试错误处理集成"""
    print("=== 测试错误处理集成 ===")
    
    try:
        from alpha.error_handling import get_error_handler, ErrorHandler
        from alpha.error_handling import error_handler, ErrorSeverity, ErrorCategory
        
        # 获取错误处理器
        handler = get_error_handler()
        print(f"错误处理器: {type(handler).__name__}")
        print(f"已注册策略数量: {len(handler.strategies)}")
        
        # 测试装饰器
        @error_handler(
            severity=ErrorSeverity.WARNING,
            category=ErrorCategory.API,
            operation="test_api_call"
        )
        def test_function():
            """测试函数"""
            raise ValueError("测试错误")
        
        try:
            test_function()
            print("错误处理装饰器测试: [失败] - 应该抛出异常")
            return False
        except ValueError as e:
            print(f"错误处理装饰器测试: [成功] - 捕获到预期异常: {e}")
        
        # 检查错误记录
        recent_errors = handler.get_recent_errors(5)
        print(f"最近错误记录: {len(recent_errors)} 条")
        
        return True
        
    except Exception as e:
        print(f"错误处理集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_performance_monitoring_integration():
    """测试性能监控集成"""
    print("\n=== 测试性能监控集成 ===")
    
    try:
        from alpha.performance_monitor import get_performance_monitor, monitor_performance
        from alpha.performance_monitor import record_metric, MetricType
        
        # 获取性能监控器
        monitor = get_performance_monitor()
        print(f"性能监控器: {type(monitor).__name__}")
        
        # 测试装饰器
        @monitor_performance("test.operation")
        def monitored_function():
            """被监控的函数"""
            import time
            time.sleep(0.1)
            return "测试结果"
        
        result = monitored_function()
        print(f"监控函数执行结果: {result}")
        
        # 记录指标
        record_metric("test.counter", 1, MetricType.COUNTER)
        record_metric("test.gauge", 42.5, MetricType.GAUGE)
        # 记录单个计时器值而不是列表
        record_metric("test.timer", 0.1, MetricType.TIMER)
        record_metric("test.timer", 0.2, MetricType.TIMER)
        record_metric("test.timer", 0.3, MetricType.TIMER)
        
        # 获取性能报告
        report = monitor.export_metrics("json")
        print(f"性能报告包含 {len(report.get('timers', []))} 个计时器指标")
        
        # 显示一些指标
        timers = report.get('timers', [])
        if timers:
            print("采样计时器指标:")
            for i, timer in enumerate(timers[:3]):
                print(f"  {timer.get('name')}: {timer.get('count')} 次调用")
        
        return True
        
    except Exception as e:
        print(f"性能监控集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_manager_integration():
    """测试配置管理器集成"""
    print("\n=== 测试配置管理器集成 ===")
    
    try:
        from alpha.config import get_config_manager, get_config, set_config, ConfigSource
        
        # 获取配置管理器
        config_manager = get_config_manager()
        print(f"配置管理器: {type(config_manager).__name__}")
        print(f"项目根目录: {config_manager.project_root}")
        
        # 重新加载配置
        config_manager.reload()
        
        # 测试配置访问
        all_sources = config_manager.get_all_sources()
        print(f"配置源数量: {len(all_sources)}")
        
        # 测试快捷函数
        test_key = "integration_test_value"
        test_value = "integration_test_123"
        
        set_config(test_key, test_value, ConfigSource.RUNTIME_OVERRIDE)
        
        retrieved = get_config(test_key)
        if retrieved == test_value:
            print(f"配置访问测试: [成功] - {test_key} = {retrieved}")
        else:
            print(f"配置访问测试: [失败] - 期望 {test_value}, 实际 {retrieved}")
            return False
        
        # 测试配置合并
        merged_config = config_manager.get_merged_config()
        print(f"合并配置包含 {len(merged_config)} 个配置项")
        
        return True
        
    except Exception as e:
        print(f"配置管理器集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_error_handling():
    """测试API错误处理"""
    print("\n=== 测试API错误处理 ===")
    
    try:
        # 导入API模块
        from alpha.api.simulations import BrainSimulationsMixin
        
        # 检查装饰器是否已添加
        import inspect
        method = BrainSimulationsMixin.create_simulation
        print(f"create_simulation方法: {method}")
        
        # 检查是否有装饰器
        if hasattr(method, '__wrapped__'):
            print("API错误处理装饰器: [已添加]")
        else:
            print("API错误处理装饰器: [未找到]")
            
        # 检查是否有性能监控装饰器
        from alpha.core.executor import build_pending_templates_for_field
        if hasattr(build_pending_templates_for_field, '__wrapped__'):
            print("性能监控装饰器: [已添加]")
        else:
            print("性能监控装饰器: [未找到]")
        
        return True
        
    except Exception as e:
        print(f"API错误处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("短期改进集成测试")
    print("=" * 50)
    
    tests = [
        ("错误处理集成", test_error_handling_integration),
        ("性能监控集成", test_performance_monitoring_integration),
        ("配置管理器集成", test_config_manager_integration),
        ("API错误处理", test_api_error_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"{test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    print("-" * 50)
    
    all_passed = True
    for test_name, success in results:
        status = "[成功]" if success else "[失败]"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False
    
    print("-" * 50)
    if all_passed:
        print("所有集成测试通过!")
        return 0
    else:
        print("部分测试失败")
        return 1

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.WARNING)
    
    # 运行测试
    exit_code = main()
    sys.exit(exit_code)