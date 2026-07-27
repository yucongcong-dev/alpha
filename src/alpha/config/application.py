"""Immutable application configuration assembled at the CLI boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models.io_types import RunPaths


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplicationConfig:
    """Validated runtime configuration used after argument parsing.

    ``argparse.Namespace`` remains a CLI implementation detail.  The active
    runtime receives this immutable snapshot, including normalized paths, so
    later stages cannot silently rewrite configuration values.
    """

    paths: RunPaths
    command: str
    config: str
    email: str | None
    password: str | None
    dataset_id: str
    region: str
    universe: str
    instrument_type: str
    delay: int
    decay: int
    neutralization: str
    truncation: float
    nan_handling: str
    pasteurization: str
    unit_handling: str
    max_trade: str
    language: str
    start_date: str | None
    end_date: str | None
    smoke_test: bool
    full_run: bool
    limit: int
    offset: int
    page_size: int
    sleep_between_fields: float
    max_templates_per_field: int
    max_templates_per_family: int
    field_template_batch_size: int
    legacy_similarity_penalty: int
    disable_legacy_after: int
    dry_run_plan: bool
    template_disable_after: int
    top_fields_by_feedback: int
    stop_after_submittable: int
    min_request_interval: float
    rate_limit_max_retries: int
    login_retries: int
    simulation_create_retries: int
    simulation_poll_retries: int
    max_concurrent_simulations: int
    max_concurrent_creates: int
    simulation_max_polls: int
    simulation_max_wait_seconds: float
    simulation_max_pending_cycles: int
    simulation_max_queue_seconds: float
    queue_busy_cooldown_seconds: float
    field_queue_busy_skip_after: int
    check_submit_retries: int
    min_sharpe: float
    min_fitness: float
    min_turnover: float
    max_turnover: float
    max_weight: float
    backfill_window: int
    auto_update_blacklist: bool
    verbose: bool
    quiet: bool
    include_credentials: bool
    dry_run_clean: bool

    @classmethod
    def from_args(cls, args: object, paths: RunPaths) -> ApplicationConfig:
        """Build a typed immutable snapshot from a resolved CLI namespace."""

        def get(name: str, default: Any = None) -> Any:
            return getattr(args, name, default)

        return cls(
            paths=paths,
            command=str(get("command", "run")),
            config=str(get("config", "") or ""),
            email=get("email"),
            password=get("password"),
            dataset_id=str(get("dataset_id", "") or ""),
            region=str(get("region", "") or ""),
            universe=str(get("universe", "") or ""),
            instrument_type=str(get("instrument_type", "") or ""),
            delay=int(get("delay", 0) or 0),
            decay=int(get("decay", 0) or 0),
            neutralization=str(get("neutralization", "") or ""),
            truncation=float(get("truncation", 0.0) or 0.0),
            nan_handling=str(get("nan_handling", "") or ""),
            pasteurization=str(get("pasteurization", "") or ""),
            unit_handling=str(get("unit_handling", "") or ""),
            max_trade=str(get("max_trade", "OFF") or "OFF"),
            language=str(get("language", "") or ""),
            start_date=get("start_date"),
            end_date=get("end_date"),
            smoke_test=bool(get("smoke_test", False)),
            full_run=bool(get("full_run", False)),
            limit=int(get("limit", 0) or 0),
            offset=int(get("offset", 0) or 0),
            page_size=int(get("page_size", 0) or 0),
            sleep_between_fields=float(get("sleep_between_fields", 0.0) or 0.0),
            max_templates_per_field=int(get("max_templates_per_field", 0) or 0),
            max_templates_per_family=int(get("max_templates_per_family", 0) or 0),
            field_template_batch_size=int(get("field_template_batch_size", 0) or 0),
            legacy_similarity_penalty=int(get("legacy_similarity_penalty", 0) or 0),
            disable_legacy_after=int(get("disable_legacy_after", 0) or 0),
            dry_run_plan=bool(get("dry_run_plan", False)),
            template_disable_after=int(get("template_disable_after", 0) or 0),
            top_fields_by_feedback=int(get("top_fields_by_feedback", 0) or 0),
            stop_after_submittable=int(get("stop_after_submittable", 0) or 0),
            min_request_interval=float(get("min_request_interval", 0.0) or 0.0),
            rate_limit_max_retries=int(get("rate_limit_max_retries", 0) or 0),
            login_retries=int(get("login_retries", 0) or 0),
            simulation_create_retries=int(get("simulation_create_retries", 0) or 0),
            simulation_poll_retries=int(get("simulation_poll_retries", 0) or 0),
            max_concurrent_simulations=int(get("max_concurrent_simulations", 0) or 0),
            max_concurrent_creates=int(get("max_concurrent_creates", 0) or 0),
            simulation_max_polls=int(get("simulation_max_polls", 0) or 0),
            simulation_max_wait_seconds=float(get("simulation_max_wait_seconds", 0.0) or 0.0),
            simulation_max_pending_cycles=int(get("simulation_max_pending_cycles", 0) or 0),
            simulation_max_queue_seconds=float(get("simulation_max_queue_seconds", 0.0) or 0.0),
            queue_busy_cooldown_seconds=float(get("queue_busy_cooldown_seconds", 0.0) or 0.0),
            field_queue_busy_skip_after=int(get("field_queue_busy_skip_after", 0) or 0),
            check_submit_retries=int(get("check_submit_retries", 0) or 0),
            min_sharpe=float(get("min_sharpe", 0.0) or 0.0),
            min_fitness=float(get("min_fitness", 0.0) or 0.0),
            min_turnover=float(get("min_turnover", 0.0) or 0.0),
            max_turnover=float(get("max_turnover", 0.0) or 0.0),
            max_weight=float(get("max_weight", 0.0) or 0.0),
            backfill_window=int(get("backfill_window", 0) or 0),
            auto_update_blacklist=bool(get("auto_update_blacklist", False)),
            verbose=bool(get("verbose", False)),
            quiet=bool(get("quiet", False)),
            include_credentials=bool(get("include_credentials", False)),
            dry_run_clean=bool(get("dry_run_clean", False)),
        )

    @property
    def output(self) -> str:
        return self.paths.output

    @property
    def feedback_output(self) -> str:
        return self.paths.feedback_output

    @property
    def template_library_file(self) -> str:
        return self.paths.template_library_file

    @property
    def fields_cache_file(self) -> str:
        return self.paths.fields_cache_file

    @property
    def creds_file(self) -> str:
        return self.paths.creds_file

    @property
    def creds_key_file(self) -> str:
        return self.paths.creds_key_file

    @property
    def include_fields_file(self) -> str:
        return self.paths.include_fields_file

    @property
    def exclude_fields_file(self) -> str:
        return self.paths.exclude_fields_file

    @property
    def include_templates_file(self) -> str:
        return self.paths.include_templates_file

    @property
    def exclude_templates_file(self) -> str:
        return self.paths.exclude_templates_file

    @property
    def log_file(self) -> str:
        return self.paths.log_file

    @property
    def state_file(self) -> str:
        return self.paths.state_file

    @property
    def checkpoint_file(self) -> str:
        return self.paths.checkpoint_file

    @property
    def blacklists_dir(self) -> str:
        return self.paths.blacklists_dir
