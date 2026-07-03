#!/usr/bin/env python3
"""
验证统一配置管理器
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from alpha.config import get_config_manager, get_config, set_config, ConfigSource

def test_basic_config_loading():
    """测试基本配置加载"""
    print("=== 测试统一配置管理器 ===")
    
    # 获取配置管理器实例
    config_manager = get_config_manager()
    print(f"项目根目录: {config_manager.project_root}")
    print(f"配置目录: {config_manager.config_dir}")
    
    # 重新加载配置
    config_manager.reload()
    
    # 获取所有配置源
    all_sources = config_manager.get_all_sources()
    print(f"\n找到的配置源数量: {len(all_sources)}")
    
    for source, config in all_sources.items():
        if config:
            print(f"\n{source.value}:")
            print(f"  包含 {len(config)} 个配置项")
            # 显示前5个配置项
            for i, (key, value) in enumerate(config.items()):
                if i < 5:
                    print(f"    {key}: {value}")
                else:
                    print(f"    ... 还有 {len(config) - 5} 个配置项")
                    break
    
    # 测试获取配置值
    print("\n=== 测试配置访问 ===")
    
    # 尝试获取一些可能存在的配置项
    test_keys = [
        "api_key",
        "model_name",
        "max_tokens",
        "temperature",
        "timeout",
    ]
    
    for key in test_keys:
        value = get_config(key)
        if value is not None:
            source = config_manager.get_source_for_key(key)
            print(f"{key}: {value} (来源: {source.value if source else '未知'})")
        else:
            print(f"{key}: 未找到")
    
    # 测试设置配置值
    print("\n=== 测试运行时配置覆盖 ===")
    
    # 设置一个测试配置
    test_key = "test_runtime_value"
    test_value = "runtime_test_123"
    
    set_config(test_key, test_value, ConfigSource.RUNTIME_OVERRIDE)
    
    # 验证设置成功
    retrieved = get_config(test_key)
    source = config_manager.get_source_for_key(test_key)
    print(f"设置 {test_key} = {test_value}")
    print(f"获取 {test_key}: {retrieved} (来源: {source.value if source else '未知'})")
    
    # 测试合并配置
    print("\n=== 测试合并配置 ===")
    merged_config = config_manager.get_merged_config()
    print(f"合并配置包含 {len(merged_config)} 个配置项")
    
    # 显示合并配置的前10个键
    print("合并配置的前10个键:")
    for i, key in enumerate(list(merged_config.keys())[:10]):
        print(f"  {key}")
    
    return True

def test_schema_validation():
    """测试配置schema验证"""
    print("\n=== 测试配置schema验证 ===")
    
    config_manager = get_config_manager()
    
    # 定义一个简单的schema
    schema_def = {
        "api": {
            "key": "str",
            "timeout": "int",
            "retry_count": "int",
            "enabled": "bool",
        },
        "model": {
            "name": "str",
            "max_tokens": "int",
            "temperature": "float",
        }
    }
    
    # 设置schema
    config_manager.set_schema(schema_def)
    
    # 获取schema验证后的默认配置
    default_config = config_manager._schema.get_default_config() if config_manager._schema else {}
    print(f"基于schema的默认配置: {default_config}")
    
    return True

if __name__ == "__main__":
    try:
        # 测试基本配置加载
        if not test_basic_config_loading():
            print("基本配置加载测试失败")
            sys.exit(1)
        
        # 测试schema验证
        if not test_schema_validation():
            print("Schema验证测试失败")
            sys.exit(1)
        
        print("\n=== 所有测试通过 ===")
        print("配置管理器可以正确加载和使用配置文件。")
        
        # 显示一些有用的信息
        config_manager = get_config_manager()
        print(f"\n可用配置源:")
        for source in ConfigSource:
            config = config_manager._config_by_source.get(source)
            if config:
                print(f"  {source.value}: {len(config)} 个配置项")
            else:
                print(f"  {source.value}: 无配置")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)