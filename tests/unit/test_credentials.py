"""Credential loading tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import stat
from unittest.mock import patch

import pytest

from alpha.exceptions import BrainAPIError
from alpha.io.credentials import (
    load_credentials,
    prompt_and_store_credentials,
    write_credentials_file,
)
import alpha.io.credentials_crypto as credentials_crypto
from alpha.io.credentials_crypto import (
    CREDENTIALS_STORAGE_VERSION,
    WINDOWS_DPAPI_KEY_STORAGE,
    WINDOWS_DPAPI_KEY_VERSION,
    decrypt_credentials_payload,
    encrypt_credentials_payload,
    read_or_create_credentials_key,
)
from alpha.models.runtime_options import CredentialLoadOptions


def _options(creds_file, key_file, *, email=None, password=None) -> CredentialLoadOptions:
    return CredentialLoadOptions(
        email=email,
        password=password,
        creds_file=str(creds_file),
        creds_key_file=str(key_file),
    )


def _assert_credentials_storage_is_protected(creds_file, key_file) -> None:
    if os.name == "nt":
        key = read_or_create_credentials_key(str(key_file))
        key_text = key_file.read_text(encoding="utf-8")
        key_payload = json.loads(key_text)
        assert key_payload["version"] == WINDOWS_DPAPI_KEY_VERSION
        assert key_payload["storage"] == WINDOWS_DPAPI_KEY_STORAGE
        assert key_payload["protected_key"]
        assert key.decode("ascii") not in key_text
    else:
        assert stat.S_IMODE(creds_file.stat().st_mode) == 0o600
        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600


def test_load_credentials_rejects_invalid_json_shape(tmp_path) -> None:
    """Credential files must be JSON objects, not arbitrary JSON values."""
    creds_file = tmp_path / "credentials.json"
    key_file = tmp_path / "credentials.key"
    creds_file.write_text("[]", encoding="utf-8")

    with pytest.raises(BrainAPIError, match="expected a JSON object"):
        load_credentials(_options(creds_file, key_file))


def test_encrypted_credentials_round_trip_and_permissions(tmp_path) -> None:
    creds_file = tmp_path / "credentials.json"
    key_file = tmp_path / "credentials.key"

    write_credentials_file(str(creds_file), str(key_file), "user@example.com", "secret")
    payload = json.loads(creds_file.read_text(encoding="utf-8"))

    assert payload["version"] == CREDENTIALS_STORAGE_VERSION
    assert "user@example.com" not in creds_file.read_text(encoding="utf-8")
    assert "secret" not in creds_file.read_text(encoding="utf-8")
    _assert_credentials_storage_is_protected(creds_file, key_file)
    assert load_credentials(_options(creds_file, key_file)) == ("user@example.com", "secret")


def test_plaintext_credentials_are_migrated_to_encrypted_storage(tmp_path) -> None:
    creds_file = tmp_path / "credentials.json"
    key_file = tmp_path / "credentials.key"
    creds_file.write_text(
        json.dumps({"email": "legacy@example.com", "password": "legacy-secret"}),
        encoding="utf-8",
    )

    assert load_credentials(_options(creds_file, key_file)) == (
        "legacy@example.com",
        "legacy-secret",
    )
    migrated = json.loads(creds_file.read_text(encoding="utf-8"))
    assert migrated["version"] == CREDENTIALS_STORAGE_VERSION
    assert "email" not in migrated
    _assert_credentials_storage_is_protected(creds_file, key_file)


def test_explicit_credentials_do_not_touch_local_files(tmp_path) -> None:
    creds_file = tmp_path / "missing.json"
    key_file = tmp_path / "missing.key"

    assert load_credentials(
        _options(creds_file, key_file, email="cli@example.com", password="cli-secret")
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
        loaded = load_credentials(_options(creds_file, key_file))

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
        load_credentials(_options("", ""))


def test_invalid_or_empty_key_file_has_clear_error(tmp_path) -> None:
    invalid_key = tmp_path / "invalid.key"
    invalid_key.write_text("not-a-fernet-key", encoding="utf-8")
    with pytest.raises(BrainAPIError, match="key file is invalid"):
        read_or_create_credentials_key(str(invalid_key))

    empty_key = tmp_path / "empty.key"
    empty_key.write_text("", encoding="utf-8")
    with pytest.raises(BrainAPIError, match="key file is empty"):
        read_or_create_credentials_key(str(empty_key))


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI migration")
def test_windows_raw_fernet_key_is_migrated_to_dpapi(tmp_path) -> None:
    from cryptography.fernet import Fernet

    key_file = tmp_path / "credentials.key"
    raw_key = Fernet.generate_key()
    key_file.write_bytes(raw_key + b"\n")

    assert read_or_create_credentials_key(str(key_file)) == raw_key

    migrated_text = key_file.read_text(encoding="utf-8")
    migrated = json.loads(migrated_text)
    assert migrated["version"] == WINDOWS_DPAPI_KEY_VERSION
    assert migrated["storage"] == WINDOWS_DPAPI_KEY_STORAGE
    assert migrated["protected_key"]
    assert raw_key.decode("ascii") not in migrated_text
    assert read_or_create_credentials_key(str(key_file)) == raw_key


def test_invalid_windows_dpapi_key_payload_has_clear_error(tmp_path) -> None:
    key_file = tmp_path / "invalid-dpapi.key"
    key_file.write_text(
        json.dumps(
            {
                "version": WINDOWS_DPAPI_KEY_VERSION,
                "storage": WINDOWS_DPAPI_KEY_STORAGE,
                "protected_key": "not valid base64!",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BrainAPIError, match="DPAPI key payload is invalid"):
        read_or_create_credentials_key(str(key_file))


def test_windows_dpapi_key_payload_round_trip_with_mocked_dpapi(monkeypatch) -> None:
    from cryptography.fernet import Fernet

    raw_key = Fernet.generate_key()
    monkeypatch.setattr(credentials_crypto.os, "name", "nt")
    monkeypatch.setattr(
        credentials_crypto,
        "protect_for_current_user",
        lambda key: b"protected:" + key,
    )
    monkeypatch.setattr(
        credentials_crypto,
        "unprotect_for_current_user",
        lambda protected: protected.removeprefix(b"protected:"),
    )

    serialized = credentials_crypto._serialize_windows_dpapi_key(raw_key)

    assert credentials_crypto._deserialize_windows_dpapi_key(serialized, "key") == raw_key


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
