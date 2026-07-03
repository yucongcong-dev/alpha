#!/usr/bin/env python3
"""
依赖注入容器
提供类型安全的依赖注入和模块解耦能力
"""

from __future__ import annotations

import inspect
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any, Callable, Dict, Generic, List, Optional, Type, TypeVar, 
    get_type_hints, overload
)
from typing_extensions import ParamSpec

T = TypeVar('T')
P = ParamSpec('P')


class Lifecycle(Enum):
    """依赖的生命周期"""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    THREAD_LOCAL = "thread_local"


@dataclass
class DependencyInfo(Generic[T]):
    """依赖信息"""
    type: Type[T]
    factory: Callable[..., T]
    lifecycle: Lifecycle
    instance: Optional[T] = None
    thread_local_data: Optional[threading.local] = None
    dependencies: List[str] = field(default_factory=list)
    original_factory: Optional[Callable[..., T]] = None


class Container:
    """依赖注入容器"""
    
    def __init__(self):
        self._dependencies: Dict[str, DependencyInfo[Any]] = {}
        self._lock = threading.RLock()
        self._thread_local = threading.local()
    
    def register(
        self,
        interface: Type[T],
        factory: Optional[Callable[..., T]] = None,
        implementation: Optional[Type[T]] = None,
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
        **kwargs
    ) -> None:
        """
        注册依赖
        
        Args:
            interface: 接口类型（作为key）
            factory: 工厂函数，用于创建实例
            implementation: 实现类（如果没有factory则使用此类）
            lifecycle: 生命周期
            **kwargs: 传递给factory或构造函数的参数
        """
        key = self._get_key(interface)
        
        with self._lock:
            if key in self._dependencies:
                raise ValueError(f"Dependency already registered: {interface.__name__}")
            
            if factory is None and implementation is None:
                factory = interface
            elif factory is None and implementation is not None:
                factory = implementation
            
            target_factory = factory
            
            deps = self._extract_dependencies(target_factory)
            
            if inspect.isclass(target_factory) and kwargs:
                def make_factory(cls, kw):
                    def factory_func(**extra):
                        all_kwargs = {**kw, **extra}
                        return cls(**all_kwargs)
                    return factory_func
                factory_to_use = make_factory(target_factory, kwargs)
            elif inspect.isclass(target_factory):
                def make_factory(cls):
                    def factory_func(**extra):
                        return cls(**extra)
                    return factory_func
                factory_to_use = make_factory(target_factory)
            elif kwargs:
                def make_factory(f, kw):
                    def factory_func(**extra):
                        all_kwargs = {**kw, **extra}
                        return f(**all_kwargs)
                    return factory_func
                factory_to_use = make_factory(target_factory, kwargs)
            else:
                factory_to_use = target_factory
            
            dependency_info = DependencyInfo(
                type=interface,
                factory=factory_to_use,
                lifecycle=lifecycle,
                dependencies=deps,
                original_factory=target_factory,
            )
            
            if lifecycle == Lifecycle.THREAD_LOCAL:
                dependency_info.thread_local_data = threading.local()
            
            self._dependencies[key] = dependency_info
    
    def resolve(self, interface: Type[T]) -> T:
        """
        解析依赖
        
        Args:
            interface: 要解析的接口类型
            
        Returns:
            依赖实例
        """
        key = self._get_key(interface)
        
        with self._lock:
            if key not in self._dependencies:
                raise ValueError(f"Dependency not registered: {interface.__name__}")
            
            info = self._dependencies[key]
            
            if info.lifecycle == Lifecycle.SINGLETON:
                if info.instance is None:
                    info.instance = self._create_instance(info)
                return info.instance
            
            elif info.lifecycle == Lifecycle.TRANSIENT:
                return self._create_instance(info)
            
            elif info.lifecycle == Lifecycle.THREAD_LOCAL:
                if not hasattr(info.thread_local_data, 'instance'):
                    info.thread_local_data.instance = self._create_instance(info)
                return info.thread_local_data.instance
            
            raise ValueError(f"Unknown lifecycle: {info.lifecycle}")
    
    def _create_instance(self, info: DependencyInfo[Any]) -> Any:
        """创建实例，递归解析依赖"""
        factory = info.factory
        original_factory = info.original_factory or factory
        
        hints = {}
        
        if inspect.isclass(original_factory):
            init_method = getattr(original_factory, '__init__', None)
            if init_method:
                try:
                    hints = get_type_hints(init_method)
                except Exception:
                    pass
        
        if not hints:
            try:
                hints = get_type_hints(original_factory)
            except Exception:
                pass
        
        if not hints:
            try:
                target = getattr(original_factory, '__init__', original_factory)
                sig = inspect.signature(target)
                for param_name, param in sig.parameters.items():
                    if param_name in ('self', 'return'):
                        continue
                    if param.annotation != inspect.Parameter.empty:
                        hints[param_name] = param.annotation
            except Exception:
                pass
        
        resolved_kwargs = {}
        for param_name, param_type in hints.items():
            if param_name == 'return':
                continue
            try:
                resolved_kwargs[param_name] = self.resolve(param_type)
            except ValueError:
                pass
        
        if resolved_kwargs:
            try:
                return info.factory(**resolved_kwargs)
            except TypeError:
                pass
        
        return info.factory()
    
    def _extract_dependencies(self, factory: Callable[..., Any]) -> List[str]:
        """提取工厂函数的依赖"""
        try:
            hints = get_type_hints(factory)
            return [name for name in hints if name != 'return']
        except Exception:
            return []
    
    def _get_key(self, interface: Type[Any]) -> str:
        """获取依赖的唯一key"""
        return f"{interface.__module__}.{interface.__name__}"
    
    def unregister(self, interface: Type[Any]) -> None:
        """注销依赖"""
        key = self._get_key(interface)
        with self._lock:
            self._dependencies.pop(key, None)
    
    def clear(self) -> None:
        """清空所有依赖"""
        with self._lock:
            self._dependencies.clear()
    
    def has(self, interface: Type[Any]) -> bool:
        """检查依赖是否已注册"""
        key = self._get_key(interface)
        return key in self._dependencies
    
    def get_registered_types(self) -> List[Type[Any]]:
        """获取所有已注册的类型"""
        return [info.type for info in self._dependencies.values()]


class Injector:
    """依赖注入装饰器"""
    
    def __init__(self, container: Container):
        self._container = container
    
    def inject(self, func: Callable[P, T]) -> Callable[P, T]:
        """装饰器：注入依赖到函数参数"""
        import functools
        
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            hints = get_type_hints(func)
            
            for param_name, param_type in hints.items():
                if param_name == 'return':
                    continue
                if param_name not in kwargs:
                    try:
                        kwargs[param_name] = self._container.resolve(param_type)
                    except ValueError:
                        pass
            
            return func(*args, **kwargs)
        
        return wrapper


_global_container: Optional[Container] = None


def get_container() -> Container:
    """获取全局容器实例"""
    global _global_container
    if _global_container is None:
        _global_container = Container()
    return _global_container


def set_container(container: Container) -> None:
    """设置全局容器"""
    global _global_container
    _global_container = container


def inject(func: Callable[P, T]) -> Callable[P, T]:
    """便捷装饰器：使用全局容器注入依赖"""
    injector = Injector(get_container())
    return injector.inject(func)


def register(
    interface: Type[T],
    factory: Optional[Callable[..., T]] = None,
    implementation: Optional[Type[T]] = None,
    lifecycle: Lifecycle = Lifecycle.SINGLETON,
    **kwargs
) -> None:
    """便捷函数：注册依赖到全局容器"""
    get_container().register(interface, factory, implementation, lifecycle, **kwargs)


def resolve(interface: Type[T]) -> T:
    """便捷函数：从全局容器解析依赖"""
    return get_container().resolve(interface)