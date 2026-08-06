"""Runtime argument protocol definitions."""

from __future__ import annotations

from typing import Protocol


class DatasetIdentityArgs(Protocol):
    @property
    def dataset_id(self) -> str: ...


class MarketScopeArgs(Protocol):
    @property
    def region(self) -> str: ...

    @property
    def universe(self) -> str: ...

    @property
    def instrument_type(self) -> str: ...

    @property
    def delay(self) -> int: ...


class TemplateSelectionArgs(Protocol):
    @property
    def max_templates_per_field(self) -> int: ...

    @property
    def max_templates_per_family(self) -> int: ...

    @property
    def legacy_similarity_penalty(self) -> int: ...

    @property
    def template_library_file(self) -> str: ...


class SimulationSettingsArgs(MarketScopeArgs, Protocol):
    @property
    def decay(self) -> int: ...

    @property
    def neutralization(self) -> str: ...

    @property
    def truncation(self) -> float: ...

    @property
    def pasteurization(self) -> str: ...

    @property
    def unit_handling(self) -> str: ...

    @property
    def nan_handling(self) -> str: ...

    @property
    def max_trade(self) -> str: ...

    @property
    def language(self) -> str: ...

    @property
    def start_date(self) -> str | None: ...

    @property
    def end_date(self) -> str | None: ...


class TemplateBuildArgs(
    DatasetIdentityArgs,
    SimulationSettingsArgs,
    TemplateSelectionArgs,
    Protocol,
):
    pass


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


class RunSettingsArgs(Protocol):
    @property
    def decay(self) -> int: ...

    @property
    def neutralization(self) -> str: ...

    @property
    def truncation(self) -> float: ...

    @property
    def nan_handling(self) -> str: ...

    @property
    def max_trade(self) -> str: ...
