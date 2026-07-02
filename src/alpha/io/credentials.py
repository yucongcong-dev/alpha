"""
Credential loading and interactive encrypted storage.

凭证加载与交互式加密存储模块。

Low-level Fernet/key-file operations live in ``credentials_crypto``. This file
keeps the user-facing load/prompt flow and re-exports the historical helper
names for compatibility.
"""

from __future__ import annotations

import getpass
import json
import logging
import os
from typing import Any

from ..exceptions import BrainAPIError
from ..io.common import atomic_write_json
from ..models.runtime import CredentialsArgs
from .credentials_crypto import (
    CREDENTIALS_STORAGE_VERSION,
    decrypt_credentials_payload,
    encrypt_credentials_payload,
    ensure_parent_dir,
    is_encrypted_credentials_payload,
    load_crypto_dependencies,
    read_or_create_credentials_key,
    restrict_file_to_owner,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CREDENTIALS_STORAGE_VERSION",
    "decrypt_credentials_payload",
    "encrypt_credentials_payload",
    "ensure_parent_dir",
    "is_encrypted_credentials_payload",
    "load_credentials",
    "load_crypto_dependencies",
    "prompt_and_store_credentials",
    "read_or_create_credentials_key",
    "restrict_file_to_owner",
    "write_credentials_file",
]


def write_credentials_file(path: str, key_path: str, email: str, password: str) -> None:
    """将 WorldQuant 凭证加密写入本地 JSON 文件。"""
    ensure_parent_dir(path)
    atomic_write_json(path, encrypt_credentials_payload(email, password, key_path))


def prompt_and_store_credentials(path: str, key_path: str) -> tuple[str, str]:
    """交互式读取凭证并加密保存，供后续运行复用。"""
    logger.info("[creds] credentials need to be entered or refreshed: %s", path)
    logger.info(
        "[creds] Please input your WorldQuant BRAIN credentials. "
        "They will be encrypted locally for future runs.",
    )
    email = input("WorldQuant BRAIN email: ").strip()
    password = getpass.getpass("WorldQuant BRAIN password: ").strip()
    if not email or not password:
        raise BrainAPIError("Credentials were empty; aborted without saving credentials file.")
    write_credentials_file(path, key_path, email, password)
    logger.info("[creds] encrypted credentials saved to %s", path)
    return email, password


def _read_credentials_payload(creds_file: str) -> dict[str, Any]:
    """Read and validate the local credentials JSON payload."""
    try:
        with open(creds_file, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        raise BrainAPIError(f"Failed to read credentials file {creds_file}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BrainAPIError(
            f"Failed to read credentials file {creds_file}: expected a JSON object."
        )
    return payload


def _load_credentials_from_file(
    creds_file: str,
    creds_key_file: str,
) -> tuple[str | None, str | None]:
    """Load credentials from encrypted or legacy plaintext local storage."""
    payload = _read_credentials_payload(creds_file)
    if is_encrypted_credentials_payload(payload):
        return decrypt_credentials_payload(payload, creds_key_file)

    file_email = payload.get("email")
    file_password = payload.get("password")
    if file_email and file_password:
        write_credentials_file(creds_file, creds_key_file, str(file_email), str(file_password))
        logger.info("[creds] migrated plaintext credentials to encrypted storage: %s", creds_file)
    elif payload.get("ciphertext"):
        logger.info(
            "[creds] existing encrypted credentials use an unsupported old format; "
            "please re-enter them once.",
        )
    return file_email, file_password


def load_credentials(args: CredentialsArgs) -> tuple[str | None, str | None]:
    """优先从命令行/环境变量读取凭证，否则回退到本地加密凭证文件。"""
    email = args.email
    password = args.password
    creds_file = args.creds_file
    creds_key_file = args.creds_key_file

    if email and password:
        return email, password
    if not creds_file:
        raise BrainAPIError("Missing creds-file path.")
    if not os.path.exists(creds_file):
        return prompt_and_store_credentials(creds_file, creds_key_file)

    file_email, file_password = _load_credentials_from_file(creds_file, creds_key_file)
    if not (email or file_email) or not (password or file_password):
        return prompt_and_store_credentials(creds_file, creds_key_file)
    return email or file_email, password or file_password
