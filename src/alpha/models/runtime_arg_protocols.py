"""Runtime argument protocol definitions."""

from __future__ import annotations

from typing import Protocol


class CleanRuntimeArgs(Protocol):
    @property
    def include_credentials(self) -> bool: ...

    @property
    def dry_run_clean(self) -> bool: ...


class CredentialsArgs(Protocol):
    @property
    def email(self) -> str | None: ...

    @property
    def password(self) -> str | None: ...

    @property
    def creds_file(self) -> str: ...

    @property
    def creds_key_file(self) -> str: ...

