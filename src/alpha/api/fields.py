"""Dataset field discovery API mixin."""

from __future__ import annotations

import logging

from ..config.constants import DATA_FIELDS_URL, VERSION_HEADER
from ..exceptions import BrainAPIError
from .api_types import ApiPayload, FieldInfoDict
from .payloads import extract_total, normalize_results, safe_json_bytes

logger = logging.getLogger(__name__)


class BrainFieldsMixin:
    """Dataset field pagination helpers for BrainClient."""

    def fetch_dataset_fields(
        self,
        dataset_id: str,
        *,
        limit: int,
        offset: int,
        page_size: int,
        region: str,
        universe: str,
        instrument_type: str,
        delay: int,
    ) -> list[FieldInfoDict]:
        """按分页拉取某个数据集的字段元数据。"""
        fields: list[FieldInfoDict] = []
        current_offset = offset
        announced_total: int | None = None

        while True:
            batch_size = page_size
            if limit > 0:
                remaining = limit - len(fields)
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)

            payload = self._fetch_dataset_fields_page(
                dataset_id,
                batch_size,
                current_offset,
                region=region,
                universe=universe,
                instrument_type=instrument_type,
                delay=delay,
            )

            batch = normalize_results(payload)
            if not batch:
                break

            fields.extend(batch)
            current_offset += len(batch)

            total = extract_total(payload)
            if total is not None and total >= 0:
                announced_total = total
                logger.info(
                    "[cache] fetched %d/%d fields for dataset=%s (%s/%s/%s delay=%s)",
                    len(fields),
                    total,
                    dataset_id,
                    region,
                    universe,
                    instrument_type,
                    delay,
                )
            else:
                logger.info(
                    "[cache] fetched %d fields for dataset=%s (%s/%s/%s delay=%s)",
                    len(fields),
                    dataset_id,
                    region,
                    universe,
                    instrument_type,
                    delay,
                )
            if len(batch) < batch_size:
                break
            if total is not None and current_offset >= total:
                break

        if fields and announced_total is None:
            logger.info(
                "[cache] fetched %d fields total for dataset=%s (%s/%s/%s delay=%s)",
                len(fields),
                dataset_id,
                region,
                universe,
                instrument_type,
                delay,
            )

        return fields

    def _fetch_dataset_fields_page(
        self,
        dataset_id: str,
        limit: int,
        offset: int,
        *,
        region: str,
        universe: str,
        instrument_type: str,
        delay: int,
    ) -> ApiPayload:
        """获取一页字段元数据，并尝试几种已知可行的查询参数形态。"""
        last_error: Exception | None = None
        candidate_params = [
            {
                "dataset.id": dataset_id,
                "region": region,
                "delay": str(delay),
                "universe": universe,
                "instrumentType": instrument_type,
                "limit": limit,
                "offset": offset,
            },
            {
                "dataset.id": dataset_id,
                "region": region,
                "delay": str(delay),
                "universe": universe,
                "limit": limit,
                "offset": offset,
            },
            {
                "dataset.id": dataset_id,
                "region": region,
                "instrumentType": instrument_type,
                "limit": limit,
                "offset": offset,
            },
            {
                "dataset.id": dataset_id,
                "region": region,
                "delay": str(delay),
                "instrumentType": instrument_type,
                "limit": limit,
                "offset": offset,
            },
            {"dataset.id": dataset_id, "limit": limit, "offset": offset},
        ]

        for params in candidate_params:
            try:
                _, _, content = self.request(
                    "GET",
                    DATA_FIELDS_URL,
                    params=params,
                    headers=VERSION_HEADER,
                    expected={200},
                )
                logger.info("[data] data-fields query accepted: %s", params)
                return safe_json_bytes(content)
            except BrainAPIError as exc:
                last_error = exc
                logger.warning("[data] data-fields query rejected: %s -> %s", params, exc)

        raise BrainAPIError(f"Unable to fetch dataset fields for {dataset_id}: {last_error}")
