"""Structured submission-check observations.

The platform exposes a mixture of semantic check states and transport
failures.  Keeping that distinction in one small value object prevents the
refresh scheduler, result predicates, and persistence code from each
re-interpreting the same ``FieldTestResult`` fields slightly differently.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .domain import FailedCheck, FieldTestResult


class SubmissionCheckState(str, Enum):
    """Normalized state of a Submission Check observation."""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


# ``SubmissionCheckStatus`` reads naturally at call sites and keeps the
# state type discoverable for users of the model.
SubmissionCheckStatus = SubmissionCheckState


@dataclass(frozen=True)
class SubmissionCheckOutcome:
    """A normalized, immutable observation of one Alpha's checks."""

    state: SubmissionCheckState
    submittable: bool | None
    message: str
    failed_checks: tuple[FailedCheck, ...] = ()
    checked_at: str = ""

    @property
    def status(self) -> SubmissionCheckState:
        """Alias for callers that use the platform's ``status`` vocabulary."""

        return self.state

    @property
    def kind(self) -> SubmissionCheckState:
        """Alias useful when comparing outcome categories."""

        return self.state

    @property
    def needs_refresh(self) -> bool:
        """Whether the observation may become terminal on a later read."""

        return self.state in {
            SubmissionCheckState.PENDING,
            SubmissionCheckState.UNAVAILABLE,
        }

    @property
    def is_terminal(self) -> bool:
        return not self.needs_refresh

    @property
    def is_available(self) -> bool:
        return self.state is not SubmissionCheckState.UNAVAILABLE

    @classmethod
    def from_observation(
        cls,
        submittable: bool | None,
        message: str,
        failed_checks: Iterable[FailedCheck] = (),
        *,
        checked_at: str = "",
    ) -> SubmissionCheckOutcome:
        """Classify a platform response without changing its payload.

        An explicit FAIL is terminal even when another check is still marked
        PENDING.  This mirrors BRAIN's submission semantics: one failed check
        is enough to reject the Alpha, so it must not be retried forever.
        """

        checks = tuple(failed_checks)
        check_results = {str(check.result or "").strip().upper() for check in checks}
        normalized_message = str(message or "").strip().lower()
        state = SubmissionCheckState.ERROR
        if submittable is True:
            state = SubmissionCheckState.PASSED
        elif "FAIL" in check_results:
            state = SubmissionCheckState.FAILED
        elif "PENDING" in check_results or normalized_message == "checks pending":
            state = SubmissionCheckState.PENDING
        elif submittable is False:
            state = SubmissionCheckState.FAILED
        elif normalized_message == "checks unavailable":
            state = SubmissionCheckState.UNAVAILABLE
        return cls(
            state=state,
            submittable=submittable,
            message=str(message or ""),
            failed_checks=checks,
            checked_at=checked_at,
        )

    @classmethod
    def from_result(cls, result: FieldTestResult) -> SubmissionCheckOutcome:
        """Classify a persisted result, preserving terminal infrastructure errors."""

        if result.status == "error" and result.failed_stage == "check_submission":
            return cls(
                state=SubmissionCheckState.ERROR,
                submittable=result.submittable,
                message=result.message,
                failed_checks=tuple(result.failed_checks or ()),
                checked_at=result.updated_at,
            )
        return cls.from_observation(
            result.submittable,
            result.message,
            result.failed_checks or (),
            checked_at=result.updated_at,
        )

    def with_checked_at(self, checked_at: str) -> SubmissionCheckOutcome:
        return replace(self, checked_at=checked_at)

    def as_legacy_tuple(self) -> tuple[bool | None, str, list[FailedCheck]]:
        """Return the historical tuple shape used by simulation-stage callers."""

        return self.submittable, self.message, list(self.failed_checks)


__all__ = [
    "SubmissionCheckOutcome",
    "SubmissionCheckState",
    "SubmissionCheckStatus",
]
