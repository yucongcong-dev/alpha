"""Runtime protocol and shared alias definitions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..api.client import BrainClient

from .domain_types import FieldFeedbackSummary

TemplateFeedback = FieldFeedbackSummary
TemplateStats = dict[str, dict[str, Any]]
RunConfig = dict[str, object]


class ClientFactoryLike(Protocol):
    def get_client(
        self,
        *,
        request_deadline: float | None = None,
        request_abort: Callable[[], bool] | None = None,
    ) -> BrainClient: ...

    def close(self) -> None: ...


class SemaphoreLike(Protocol):
    def acquire(self, blocking: bool = True, timeout: float | None = -1) -> bool: ...

    def release(self) -> None: ...
