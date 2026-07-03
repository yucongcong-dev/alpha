#!/usr/bin/env python3
"""
依赖注入容器
提供类型安全的依赖注入和模块解耦能力
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
import inspect
import threading
from typing import Any, Generic, Optional, TypeVar, cast, get_type_hints

from typing_extensions import ParamSpec

T = TypeVar('T')
P = ParamSpec('P')


class Lifecycle(Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    THREAD_LOCAL = "thread_local"


@dataclass
class DependencyInfo(Generic[T]):
    type: type[T]
    factory: Callable[..., T]
    lifecycle: Lifecycle
    instance: Optional[T] = None
    thread_local_data: Optional[threading.local] = None
    dependencies: list[str] = field(default_factory=list)
    original_factory: Optional[Callable[..., T]] = None


class Container:
    """依赖注入容器"""

    def __init__(self):
        self._dependencies: dict[str, DependencyInfo[Any]] = {}
        self._lock = threading.RLock()

    def register(
        self,
        interface: type[T],
        factory: Optional[Callable[..., T]] = None,
        implementation: Optional[type[T]] = None,
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
        **kwargs
    ) -> None:
        key = self._get_key(interface)

        with self._lock:
            if key in self._dependencies:
                raise ValueError(f"Dependency already registered: {interface.__name__}")

            if factory is None and implementation is None:
                factory = interface
            elif factory is None and implementation is not None:
                factory = implementation

            target_factory = factory

            assert target_factory is not None
            deps = self._extract_dependencies(target_factory)

            factory_to_use = self._make_factory(target_factory, kwargs)

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

    def _make_factory(
        self,
        target_factory: Callable[..., Any],
        kwargs: dict[str, Any],
    ) -> Callable[..., Any]:
        if inspect.isclass(target_factory):
            if kwargs:
                def factory_func(**extra: Any) -> Any:
                    all_kwargs = {**kwargs, **extra}
                    return target_factory(**all_kwargs)
                return factory_func
            else:
                def factory_func(**extra: Any) -> Any:
                    return target_factory(**extra)
                return factory_func
        elif kwargs:
            def factory_func(**extra: Any) -> Any:
                all_kwargs = {**kwargs, **extra}
                return target_factory(**all_kwargs)
            return factory_func
        else:
            return target_factory

    def resolve(self, interface: type[T]) -> T:
        key = self._get_key(interface)

        with self._lock:
            if key not in self._dependencies:
                raise ValueError(f"Dependency not registered: {interface.__name__}")

            info = self._dependencies[key]

            if info.lifecycle == Lifecycle.SINGLETON:
                if info.instance is None:
                    info.instance = self._create_instance(info)
                return cast(T, info.instance)

            elif info.lifecycle == Lifecycle.TRANSIENT:
                return cast(T, self._create_instance(info))

            elif info.lifecycle == Lifecycle.THREAD_LOCAL:
                assert info.thread_local_data is not None
                if not hasattr(info.thread_local_data, 'instance'):
                    info.thread_local_data.instance = self._create_instance(info)
                return cast(T, info.thread_local_data.instance)

            raise ValueError(f"Unknown lifecycle: {info.lifecycle}")

    def _create_instance(self, info: DependencyInfo[Any]) -> Any:
        factory = info.factory
        original_factory = info.original_factory or factory

        hints: dict[str, Any] = {}

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

        resolved_kwargs: dict[str, Any] = {}
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

    def _extract_dependencies(self, factory: Callable[..., Any]) -> list[str]:
        try:
            hints = get_type_hints(factory)
            return [name for name in hints if name != 'return']
        except Exception:
            return []

    def _get_key(self, interface: type[Any]) -> str:
        return f"{interface.__module__}.{interface.__name__}"

    def unregister(self, interface: type[Any]) -> None:
        key = self._get_key(interface)
        with self._lock:
            self._dependencies.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._dependencies.clear()

    def has(self, interface: type[Any]) -> bool:
        key = self._get_key(interface)
        return key in self._dependencies

    def get_registered_types(self) -> list[type[Any]]:
        return [info.type for info in self._dependencies.values()]


class Injector:
    """依赖注入装饰器"""

    def __init__(self, container: Container):
        self._container = container

    def inject(self, func: Callable[P, T]) -> Callable[P, T]:
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
    global _global_container
    if _global_container is None:
        _global_container = Container()
    return _global_container


def set_container(container: Container) -> None:
    global _global_container
    _global_container = container


def inject(func: Callable[P, T]) -> Callable[P, T]:
    injector = Injector(get_container())
    return injector.inject(func)


def register(
    interface: type[T],
    factory: Optional[Callable[..., T]] = None,
    implementation: Optional[type[T]] = None,
    lifecycle: Lifecycle = Lifecycle.SINGLETON,
    **kwargs
) -> None:
    get_container().register(interface, factory, implementation, lifecycle, **kwargs)


def resolve(interface: type[T]) -> T:
    return get_container().resolve(interface)
