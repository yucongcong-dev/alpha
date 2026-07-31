"""Local encrypted credential storage helpers."""

from __future__ import annotations

import base64
import binascii
from contextlib import suppress
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any

from ..exceptions import BrainAPIError
from .file_lock import exclusive_file_lock
from .windows_dpapi import protect_for_current_user, unprotect_for_current_user

logger = logging.getLogger(__name__)

CREDENTIALS_STORAGE_VERSION: int = 4
WINDOWS_DPAPI_KEY_VERSION: int = 1
WINDOWS_DPAPI_KEY_STORAGE: str = "windows-dpapi-current-user"


def ensure_parent_dir(path: str) -> None:
    """按需创建目标文件的父目录。"""
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def load_crypto_dependencies() -> tuple[Any, Any]:
    """加载跨平台加密依赖库。"""
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ModuleNotFoundError as exc:
        raise BrainAPIError(
            "Missing dependency 'cryptography'. Install it first: python3.10 -m pip install cryptography"
        ) from exc
    return Fernet, InvalidToken


def restrict_file_to_owner(path: str) -> None:
    """On POSIX, restrict a sensitive local file to the current user."""
    if os.name == "nt":
        return
    with suppress(OSError):
        os.chmod(path, 0o600)


def _atomic_write_key_file(path: str, payload: bytes) -> None:
    """Atomically replace a credentials key file without exposing partial content."""
    ensure_parent_dir(path)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, temp_path = tempfile.mkstemp(prefix=".tmp_credentials_", suffix=".key", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        restrict_file_to_owner(temp_path)
        os.replace(temp_path, path)
        restrict_file_to_owner(path)
    finally:
        if os.path.exists(temp_path):
            with suppress(OSError):
                os.remove(temp_path)


def _serialize_windows_dpapi_key(key: bytes) -> bytes:
    protected_key = protect_for_current_user(key)
    payload = {
        "version": WINDOWS_DPAPI_KEY_VERSION,
        "storage": WINDOWS_DPAPI_KEY_STORAGE,
        "protected_key": base64.b64encode(protected_key).decode("ascii"),
    }
    return (json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")


def _deserialize_windows_dpapi_key(raw: bytes, key_path: str) -> bytes:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrainAPIError(f"Credentials key file is invalid: {key_path}") from exc
    if not isinstance(payload, dict):
        raise BrainAPIError(f"Credentials key file is invalid: {key_path}")
    if payload.get("storage") != WINDOWS_DPAPI_KEY_STORAGE:
        raise BrainAPIError(f"Credentials key file uses an unsupported storage format: {key_path}")
    if payload.get("version") != WINDOWS_DPAPI_KEY_VERSION:
        raise BrainAPIError(f"Credentials key file uses an unsupported DPAPI version: {key_path}")
    encoded_key = payload.get("protected_key")
    if not isinstance(encoded_key, str) or not encoded_key.strip():
        raise BrainAPIError(f"Credentials DPAPI key payload is missing protected_key: {key_path}")
    try:
        protected_key = base64.b64decode(encoded_key, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise BrainAPIError(f"Credentials DPAPI key payload is invalid: {key_path}") from exc
    if os.name != "nt":
        raise BrainAPIError(
            "Windows DPAPI credentials keys can only be read by the original Windows user."
        )
    return unprotect_for_current_user(protected_key)


def _validate_fernet_key(key: bytes, key_path: str, fernet_cls: Any) -> bytes:
    try:
        fernet_cls(key)
    except (TypeError, ValueError) as exc:
        raise BrainAPIError(f"Credentials key file is invalid: {key_path}") from exc
    return bytes(key)


def _read_existing_credentials_key(key_path: str, fernet_cls: Any) -> bytes:
    restrict_file_to_owner(key_path)
    with open(key_path, "rb") as handle:
        raw = handle.read()
    if not raw.strip():
        raise BrainAPIError(f"Credentials key file is empty: {key_path}")

    if raw.lstrip().startswith(b"{"):
        key = _deserialize_windows_dpapi_key(raw, key_path)
        return _validate_fernet_key(key, key_path, fernet_cls)

    key = _validate_fernet_key(raw.strip(), key_path, fernet_cls)
    if os.name == "nt":
        _atomic_write_key_file(key_path, _serialize_windows_dpapi_key(key))
        logger.info("[creds] migrated local credentials key to Windows DPAPI: %s", key_path)
    return key


def read_or_create_credentials_key(key_path: str) -> bytes:
    """Read or create a Fernet key, using current-user DPAPI storage on Windows."""
    fernet_cls, _ = load_crypto_dependencies()
    ensure_parent_dir(key_path)
    with exclusive_file_lock(f"{key_path}.lock"):
        if os.path.exists(key_path):
            return _read_existing_credentials_key(key_path, fernet_cls)

        key = bytes(fernet_cls.generate_key())
        serialized_key = _serialize_windows_dpapi_key(key) if os.name == "nt" else key + b"\n"
        _atomic_write_key_file(key_path, serialized_key)
        logger.info("[creds] generated local credentials key file: %s", key_path)
        return key


def encrypt_credentials_payload(email: str, password: str, key_path: str) -> dict[str, Any]:
    """生成只包含密文的本地凭证 JSON 负载。"""
    fernet_cls, _ = load_crypto_dependencies()
    key = read_or_create_credentials_key(key_path)
    plaintext = json.dumps(
        {"email": email, "password": password}, ensure_ascii=False, separators=(",", ":")
    )
    try:
        ciphertext = fernet_cls(key).encrypt(plaintext.encode("utf-8")).decode("ascii")
    except (TypeError, ValueError) as exc:
        raise BrainAPIError(f"Failed to initialize credentials encryption: {exc}") from exc
    return {
        "version": CREDENTIALS_STORAGE_VERSION,
        "storage": "cryptography-fernet-local-key-file",
        "ciphertext": ciphertext,
    }


def decrypt_credentials_payload(
    payload: dict[str, Any], key_path: str
) -> tuple[str | None, str | None]:
    """解密本地凭证 JSON 负载并返回账号密码。"""
    fernet_cls, invalid_token_cls = load_crypto_dependencies()
    ciphertext = payload.get("ciphertext")
    if not isinstance(ciphertext, str) or not ciphertext.strip():
        raise BrainAPIError("Encrypted credentials file is missing ciphertext.")
    if not os.path.exists(key_path):
        raise BrainAPIError(
            f"Credentials key file not found: {key_path}. Please re-enter credentials once."
        )
    key = read_or_create_credentials_key(key_path)
    try:
        plaintext = fernet_cls(key).decrypt(ciphertext.strip().encode("ascii")).decode("utf-8")
    except (invalid_token_cls, TypeError, ValueError, UnicodeError) as exc:
        raise BrainAPIError(
            "Failed to decrypt credentials. The local credentials key file may not match."
        ) from exc
    try:
        decoded = json.loads(plaintext)
    except Exception as exc:
        raise BrainAPIError(f"Failed to parse decrypted credentials: {exc}") from exc
    if not isinstance(decoded, dict):
        raise BrainAPIError("Decrypted credentials payload must be a JSON object.")
    raw_email = decoded.get("email")
    raw_password = decoded.get("password")
    email = raw_email.strip() if isinstance(raw_email, str) and raw_email.strip() else None
    password = raw_password if isinstance(raw_password, str) and raw_password else None
    return email, password


def is_encrypted_credentials_payload(payload: dict[str, Any]) -> bool:
    """判断凭证文件是否已经是加密格式。"""
    return (
        payload.get("version") == CREDENTIALS_STORAGE_VERSION
        and payload.get("storage") == "cryptography-fernet-local-key-file"
    )
