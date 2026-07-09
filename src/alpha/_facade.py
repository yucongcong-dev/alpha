"""Shared helpers for lazy compatibility facades."""

from __future__ import annotations

from importlib import import_module

ExportMap = dict[str, tuple[str, str]]


def resolve_export(
    *,
    name: str,
    export_map: ExportMap,
    package: str,
    namespace: str,
    target_globals: dict[str, object],
) -> object:
    """Resolve and memoize one lazy export from a facade module."""
    try:
        module_name, attr_name = export_map[name]
    except KeyError as exc:
        raise AttributeError(f"module {namespace!r} has no attribute {name!r}") from exc
    module = import_module(module_name, package)
    value = getattr(module, attr_name)
    target_globals[name] = value
    return value


def facade_dir(module_globals: dict[str, object], export_map: ExportMap) -> list[str]:
    """Build ``dir()`` output for a lazy facade module."""
    return sorted(set(module_globals) | set(export_map))
