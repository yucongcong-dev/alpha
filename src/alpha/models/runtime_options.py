"""Runtime option dataclasses."""

from __future__ import annotations

from dataclasses import dataclass

from .runtime_protocols import (
    ApiClientArgs,
    FieldFetchArgs,
    ResultWriteArgs,
    TemplateBuildArgs,
)


@dataclass(frozen=True)
class ApiClientOptions:
    """API 客户端与线程级 worker client 的窄配置。"""

    min_request_interval: float = 0.0
    rate_limit_max_retries: int = 0
    login_retries: int = 0

    @classmethod
    def from_args(cls, args: ApiClientArgs) -> ApiClientOptions:
        return cls(
            min_request_interval=float(getattr(args, "min_request_interval", 0.0) or 0.0),
            rate_limit_max_retries=int(getattr(args, "rate_limit_max_retries", 0) or 0),
            login_retries=int(getattr(args, "login_retries", 0) or 0),
        )


@dataclass(frozen=True)
class TemplateBuildOptions:
    """模板选择、反馈回路与 settings 变体展开所需的窄配置。"""

    dataset_id: str = ""
    max_templates_per_field: int = 0
    max_templates_per_family: int = 0
    legacy_similarity_penalty: int = 0
    template_disable_after: int = 0
    disable_legacy_after: int = 0
    region: str = ""
    universe: str = ""
    instrument_type: str = "EQUITY"
    delay: int = 1
    decay: int = 4
    neutralization: str = "SUBINDUSTRY"
    truncation: float = 0.08
    pasteurization: str = "ON"
    unit_handling: str = "VERIFY"
    nan_handling: str = "OFF"
    language: str = "FASTEXPR"
    start_date: str | None = None
    end_date: str | None = None

    @classmethod
    def from_args(cls, args: TemplateBuildArgs) -> TemplateBuildOptions:
        return cls(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            max_templates_per_field=int(getattr(args, "max_templates_per_field", 0) or 0),
            max_templates_per_family=int(getattr(args, "max_templates_per_family", 0) or 0),
            legacy_similarity_penalty=int(getattr(args, "legacy_similarity_penalty", 0) or 0),
            template_disable_after=int(getattr(args, "template_disable_after", 0) or 0),
            disable_legacy_after=int(getattr(args, "disable_legacy_after", 0) or 0),
            region=str(getattr(args, "region", "USA") or "USA"),
            universe=str(getattr(args, "universe", "TOP3000") or "TOP3000"),
            instrument_type=str(getattr(args, "instrument_type", "EQUITY") or "EQUITY"),
            delay=int(getattr(args, "delay", 1) or 1),
            decay=int(getattr(args, "decay", 4) or 4),
            neutralization=str(getattr(args, "neutralization", "SUBINDUSTRY") or "SUBINDUSTRY"),
            truncation=float(getattr(args, "truncation", 0.08) or 0.08),
            pasteurization=str(getattr(args, "pasteurization", "ON") or "ON"),
            unit_handling=str(getattr(args, "unit_handling", "VERIFY") or "VERIFY"),
            nan_handling=str(getattr(args, "nan_handling", "OFF") or "OFF"),
            language=str(getattr(args, "language", "FASTEXPR") or "FASTEXPR"),
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
        )


@dataclass(frozen=True)
class ResultWriteOptions:
    """future 完成后结果落盘与副作用所需的窄配置。"""

    dataset_id: str = ""
    output_path: str = ""
    auto_update_blacklist: bool = False

    @classmethod
    def from_args(cls, args: ResultWriteArgs) -> ResultWriteOptions:
        return cls(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            output_path=str(getattr(args, "output", "") or ""),
            auto_update_blacklist=bool(getattr(args, "auto_update_blacklist", False)),
        )


@dataclass(frozen=True)
class FieldFetchOptions:
    """字段缓存校验与字段列表拉取所需的窄配置。"""

    dataset_id: str = ""
    page_size: int = 0
    region: str = ""
    universe: str = ""
    instrument_type: str = ""
    delay: int = 0

    @classmethod
    def from_args(cls, args: FieldFetchArgs) -> FieldFetchOptions:
        return cls(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            page_size=int(getattr(args, "page_size", 0) or 0),
            region=str(getattr(args, "region", "") or ""),
            universe=str(getattr(args, "universe", "") or ""),
            instrument_type=str(getattr(args, "instrument_type", "") or ""),
            delay=int(getattr(args, "delay", 0) or 0),
        )
