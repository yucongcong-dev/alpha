"""Dedicated, simulation-free refresh command for Submission Check results."""

from __future__ import annotations

from contextlib import suppress
import logging

from ..analysis.feedback_history import build_historical_run_state
from ..analysis.results_loader import load_result_summary_metadata
from ..cli.run_config import build_run_config_snapshot
from ..config.application import ApplicationConfig
from ..models.domain import FieldTestResult
from ..models.result_predicates import has_pending_checks
from ..models.runtime_options import ApiClientOptions, CredentialLoadOptions
from .bootstrap_clients import create_and_login_client, resolve_credentials
from .bootstrap_pending_checks import reconcile_pending_check_results

logger = logging.getLogger(__name__)


def _pending_alpha_ids(*result_groups: list[FieldTestResult]) -> set[str]:
    """Return the distinct persisted Alpha IDs that can still be refreshed."""
    return {
        result.alpha_id
        for results in result_groups
        for result in results
        if result.alpha_id and has_pending_checks(result)
    }


def _persistence_metadata(config: ApplicationConfig) -> dict[str, object]:
    """Use the existing summary identity, falling back only when none exists."""
    output_metadata = load_result_summary_metadata(config.paths.output)
    feedback_metadata = load_result_summary_metadata(config.paths.feedback_output)
    metadata = output_metadata or feedback_metadata
    persisted_dataset_id = str(metadata.get("dataset_id", "") or "")
    if persisted_dataset_id and persisted_dataset_id != config.dataset.dataset_id:
        raise ValueError(
            "--dataset-id does not match the existing result summary: "
            f"{config.dataset.dataset_id!r} != {persisted_dataset_id!r}"
        )
    if metadata:
        return metadata
    return {
        "dataset_id": config.dataset.dataset_id,
        "settings_fingerprint": "",
        "template_library_fingerprint": "",
        "run_fingerprint": "",
        "run_config": build_run_config_snapshot(config, config.paths),
    }


def refresh_submission_checks(config: ApplicationConfig) -> bool:
    """Refresh persisted PENDING checks without discovering or simulating fields."""
    paths = config.paths
    metadata = _persistence_metadata(config)
    historical_state = build_historical_run_state(
        paths.output,
        paths.feedback_output,
        repair_corrupt_summary=False,
    )
    pending_before = len(
        _pending_alpha_ids(
            historical_state.feedback_results,
            historical_state.existing_results,
        )
    )
    if not pending_before:
        logger.info("[check-submissions] no pending submission checks")
        return True

    email, password = resolve_credentials(CredentialLoadOptions.from_config(config))
    if not email or not password:
        logger.error("[error] 缺少凭证，无法刷新 Submission Check")
        return False

    bootstrap_client, client_factory = create_and_login_client(
        email,
        password,
        ApiClientOptions.from_config(config),
    )
    try:
        refresh_config = config.pending_check_refresh
        run_config = metadata.get("run_config")
        # One authenticated client is sufficient for the conservative default.
        # Higher explicitly requested worker counts receive independent clients.
        refresh_client = client_factory if refresh_config.max_workers > 1 else bootstrap_client
        refreshed_state = reconcile_pending_check_results(
            refresh_client,
            historical_state,
            retries=max(1, config.execution.check_submission_retries),
            output_file=paths.output,
            feedback_output=paths.feedback_output,
            dataset_id=config.dataset.dataset_id,
            settings_fingerprint=str(metadata.get("settings_fingerprint", "") or ""),
            template_library_fingerprint=str(
                metadata.get("template_library_fingerprint", "") or ""
            ),
            run_fingerprint=str(metadata.get("run_fingerprint", "") or ""),
            run_config=dict(run_config) if isinstance(run_config, dict) else {},
            refresh_limit=refresh_config.refresh_limit,
            max_refresh_seconds=refresh_config.max_refresh_seconds,
            max_workers=refresh_config.max_workers,
            repeat_until_terminal=True,
        )
    finally:
        with suppress(Exception):
            bootstrap_client.close()
        with suppress(Exception):
            client_factory.close()

    pending_after = len(
        _pending_alpha_ids(
            refreshed_state.feedback_results,
            refreshed_state.existing_results,
        )
    )
    logger.info(
        "[check-submissions] pending_before=%d resolved=%d pending_after=%d",
        pending_before,
        pending_before - pending_after,
        pending_after,
    )
    return True
