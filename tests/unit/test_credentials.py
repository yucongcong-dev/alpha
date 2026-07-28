"""Credential loading tests."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import stat
from unittest.mock import patch

import pytest

from alpha.exceptions import BrainAPIError
from alpha.io.credentials import (
    CREDENTIALS_STORAGE_VERSION,
    load_credentials,
    prompt_and_store_credentials,
    write_credentials_file,
)
from alpha.io.credentials_crypto import (
    decrypt_credentials_payload,
    encrypt_credentials_payload,
    read_or_create_credentials_key,
)


def _args(creds_file, key_file, *, email=None, password=None):
    return argparse.Namespace(
        email=email,
        password=password,
        creds_file=str(creds_file),
        creds_key_file=str(key_file),
    )


def test_load_credentials_rejects_invalid_json_shape(tmp_path) -> None:
    """Credential files must be JSON objects, not arbitrary JSON values."""
    creds_file = tmp_path / "credentials.json"
    key_file = tmp_path / "credentials.key"
    creds_file.write_text("[]", encoding="utf-8")

    with pytest.raises(BrainAPIError, match="expected a JSON object"):
        load_credentials(_args(creds_file, key_file))


def test_encrypted_credentials_round_trip_and_permissions(tmp_path) -> None:
    creds_file = tmp_path / "credentials.json"
    key_file = tmp_path / "credentials.key"

    write_credentials_file(str(creds_file), str(key_file), "user@example.com", "secret")
    payload = json.loads(creds_file.read_text(encoding="utf-8"))

    assert payload["version"] == CREDENTIALS_STORAGE_VERSION
    assert "user@example.com" not in creds_file.read_text(encoding="utf-8")
    assert "secret" not in creds_file.read_text(encoding="utf-8")
    assert stat.S_IMODE(creds_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert load_credentials(_args(creds_file, key_file)) == ("user@example.com", "secret")


def test_plaintext_credentials_are_migrated_to_encrypted_storage(tmp_path) -> None:
    creds_file = tmp_path / "credentials.json"
    key_file = tmp_path / "credentials.key"
    creds_file.write_text(
        json.dumps({"email": "legacy@example.com", "password": "legacy-secret"}),
        encoding="utf-8",
    )

    assert load_credentials(_args(creds_file, key_file)) == (
        "legacy@example.com",
        "legacy-secret",
    )
    migrated = json.loads(creds_file.read_text(encoding="utf-8"))
    assert migrated["version"] == CREDENTIALS_STORAGE_VERSION
    assert "email" not in migrated
    assert stat.S_IMODE(creds_file.stat().st_mode) == 0o600


def test_explicit_credentials_do_not_touch_local_files(tmp_path) -> None:
    creds_file = tmp_path / "missing.json"
    key_file = tmp_path / "missing.key"

    assert load_credentials(
        _args(creds_file, key_file, email="cli@example.com", password="cli-secret")
    ) == ("cli@example.com", "cli-secret")
    assert not creds_file.exists()
    assert not key_file.exists()


def test_missing_credentials_file_prompts_and_stores(tmp_path) -> None:
    creds_file = tmp_path / "credentials.json"
    key_file = tmp_path / "credentials.key"
    with (
        patch("builtins.input", return_value="prompt@example.com"),
        patch("getpass.getpass", return_value="prompt-secret"),
    ):
        loaded = load_credentials(_args(creds_file, key_file))

    assert loaded == ("prompt@example.com", "prompt-secret")
    assert creds_file.exists()


def test_prompt_rejects_empty_credentials(tmp_path) -> None:
    with (
        patch("builtins.input", return_value=""),
        patch("getpass.getpass", return_value=""),
        pytest.raises(BrainAPIError, match="Credentials were empty"),
    ):
        prompt_and_store_credentials(
            str(tmp_path / "credentials.json"),
            str(tmp_path / "credentials.key"),
        )


def test_missing_creds_file_path_is_rejected() -> None:
    with pytest.raises(BrainAPIError, match="Missing creds-file path"):
        load_credentials(_args("", ""))


def test_invalid_or_empty_key_file_has_clear_error(tmp_path) -> None:
    invalid_key = tmp_path / "invalid.key"
    invalid_key.write_text("not-a-fernet-key", encoding="utf-8")
    with pytest.raises(BrainAPIError, match="key file is invalid"):
        read_or_create_credentials_key(str(invalid_key))

    empty_key = tmp_path / "empty.key"
    empty_key.write_text("", encoding="utf-8")
    with pytest.raises(BrainAPIError, match="key file is empty"):
        read_or_create_credentials_key(str(empty_key))


def test_decrypt_rejects_missing_ciphertext_or_key(tmp_path) -> None:
    with pytest.raises(BrainAPIError, match="missing ciphertext"):
        decrypt_credentials_payload({}, str(tmp_path / "key"))

    with pytest.raises(BrainAPIError, match="key file not found"):
        decrypt_credentials_payload(
            {"ciphertext": "invalid"},
            str(tmp_path / "missing.key"),
        )


def test_decrypt_rejects_wrong_key(tmp_path) -> None:
    key1 = tmp_path / "key1"
    key2 = tmp_path / "key2"
    payload = encrypt_credentials_payload("user@example.com", "secret", str(key1))
    read_or_create_credentials_key(str(key2))

    with pytest.raises(BrainAPIError, match="Failed to decrypt credentials"):
        decrypt_credentials_payload(payload, str(key2))


def test_concurrent_key_creation_returns_one_stable_key(tmp_path) -> None:
    key_path = str(tmp_path / "shared.key")

    with ThreadPoolExecutor(max_workers=8) as executor:
        keys = list(
            executor.map(lambda _index: read_or_create_credentials_key(key_path), range(16))
        )

    assert len(set(keys)) == 1
    assert read_or_create_credentials_key(key_path) == keys[0]
