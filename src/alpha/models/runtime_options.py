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
            min_request_interval=float(args.min_request_interval or 0.0),
            rate_limit_max_retries=int(args.rate_limit_max_retries or 0),
            login_retries=int(args.login_retries or 0),
        )


@dataclass(frozen=True)
class TemplateBuildOptions:
    """模板选择、反馈回路与 settings 变体展开所需的窄配置。"""

    region: str
    universe: str
    instrument_type: str
    delay: int
    decay: int
    neutralization: str
    truncation: float
    pasteurization: str
    unit_handling: str
    nan_handling: str
    language: str
    dataset_id: str = ""
    max_templates_per_field: int = 0
    max_templates_per_family: int = 0
    legacy_similarity_penalty: int = 0
    template_disable_after: int = 0
    disable_legacy_after: int = 0
    start_date: str | None = None
    end_date: str | None = None

    @classmethod
    def from_args(cls, args: TemplateBuildArgs) -> TemplateBuildOptions:
        return cls(
            region=args.region,
            universe=args.universe,
            instrument_type=args.instrument_type,
            delay=args.delay,
            decay=args.decay,
            neutralization=args.neutralization,
            truncation=args.truncation,
            pasteurization=args.pasteurization,
            unit_handling=args.unit_handling,
            nan_handling=args.nan_handling,
            language=args.language,
            dataset_id=args.dataset_id,
            max_templates_per_field=int(args.max_templates_per_field or 0),
            max_templates_per_family=int(args.max_templates_per_family or 0),
            legacy_similarity_penalty=int(args.legacy_similarity_penalty or 0),
            template_disable_after=int(args.template_disable_after or 0),
            disable_legacy_after=int(args.disable_legacy_after or 0),
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
            dataset_id=str(args.dataset_id or ""),
            output_path=str(args.output or ""),
            auto_update_blacklist=bool(args.auto_update_blacklist),
        )


@dataclass(frozen=True)
class FieldFetchOptions:
    """字段缓存校验与字段列表拉取所需的窄配置。"""

    region: str
    universe: str
    instrument_type: str
    delay: int
    dataset_id: str = ""
    page_size: int = 0

    @classmethod
    def from_args(cls, args: FieldFetchArgs) -> FieldFetchOptions:
        return cls(
            region=args.region,
            universe=args.universe,
            instrument_type=args.instrument_type,
            delay=args.delay,
            dataset_id=args.dataset_id,
            page_size=int(args.page_size or 0),
        )
