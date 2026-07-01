"""Credential loading tests."""

from __future__ import annotations

import argparse

import pytest

from alpha.exceptions import BrainAPIError
from alpha.io.credentials import load_credentials


def test_load_credentials_rejects_invalid_json_shape(tmp_path) -> None:
    """Credential files must be JSON objects, not arbitrary JSON values."""
    creds_file = tmp_path / "credentials.json"
    key_file = tmp_path / "credentials.key"
    creds_file.write_text("[]", encoding="utf-8")

    args = argparse.Namespace(
        email=None,
        password=None,
        creds_file=str(creds_file),
        creds_key_file=str(key_file),
    )

    with pytest.raises(BrainAPIError, match="expected a JSON object"):
        load_credentials(args)
