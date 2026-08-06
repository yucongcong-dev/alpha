"""Runtime protocol and shared alias definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..api.client import BrainClient

from .domain_types import FieldFeedbackSummary

TemplateFeedback = FieldFeedbackSummary
TemplateStats = dict[str, dict[str, Any]]
RunConfig = dict[str, object]


class ClientFactoryLike(Protocol):
    def get_client(self) -> BrainClient: ...

    def close(self) -> None: ...


class SemaphoreLike(Protocol):
    def acquire(self, blocking: bool = True, timeout: float | None = -1) -> bool: ...

    def release(self) -> None: ...
