"""
依赖注入模块

提供轻量级的依赖注入容器和装饰器，实现模块间解耦。

核心功能：
- Container: 依赖注入容器
- Injector: 依赖注入装饰器
- Lifecycle: 生命周期枚举（SINGLETON/TRANSIENT/THREAD_LOCAL）
- inject: 便捷装饰器
- register/resolve: 便捷函数

使用示例：
    from alpha.di import Container, Lifecycle, inject, register, resolve

    # 注册依赖
    register(ConfigManager)
    register(Database, implementation=PostgreSQLDatabase, lifecycle=Lifecycle.SINGLETON)

    # 使用装饰器注入
    @inject
    def process_data(db: Database, config: ConfigManager):
        pass

    # 直接解析
    db = resolve(Database)
"""

from __future__ import annotations

from .container import (
    Container,
    Injector,
    Lifecycle,
    get_container,
    inject,
    register,
    resolve,
    set_container,
)

__all__ = [
    "Container",
    "Injector",
    "Lifecycle",
    "get_container",
    "inject",
    "register",
    "resolve",
    "set_container",
]
