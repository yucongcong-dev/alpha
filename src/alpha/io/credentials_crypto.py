"""Local encrypted credential storage helpers."""

from __future__ import annotations

from contextlib import suppress
import json
import logging
import os
from pathlib import Path
from typing import Any

from ..exceptions import BrainAPIError

logger = logging.getLogger(__name__)

CREDENTIALS_STORAGE_VERSION: int = 4


def ensure_parent_dir(path: str) -> None:
    """按需创建目标文件的父目录。"""
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def load_crypto_dependencies() -> tuple[Any, Any]:
    """加载跨平台加密依赖库。"""
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ModuleNotFoundError as exc:
        raise BrainAPIError(
            "Missing dependency 'cryptography'. Install it first: python3 -m pip install cryptography"
        ) from exc
    return Fernet, InvalidToken


def restrict_file_to_owner(path: str) -> None:
    """尽量将敏感本地文件权限收紧为仅当前用户可读写。"""
    with suppress(OSError):
        os.chmod(path, 0o600)


def read_or_create_credentials_key(key_path: str) -> bytes:
    """读取本地凭证加密密钥；不存在时生成并保存。"""
    fernet_cls, _ = load_crypto_dependencies()
    if os.path.exists(key_path):
        restrict_file_to_owner(key_path)
        with open(key_path, "rb") as handle:
            key = handle.read().strip()
        if key:
            return key
        raise BrainAPIError(f"Credentials key file is empty: {key_path}")

    ensure_parent_dir(key_path)
    key = fernet_cls.generate_key()
    with open(key_path, "wb") as handle:
        handle.write(key + b"\n")
    restrict_file_to_owner(key_path)
    logger.info("[creds] generated local credentials key file: %s", key_path)
    return bytes(key)


def encrypt_credentials_payload(email: str, password: str, key_path: str) -> dict[str, Any]:
    """生成只包含密文的本地凭证 JSON 负载。"""
    fernet_cls, _ = load_crypto_dependencies()
    key = read_or_create_credentials_key(key_path)
    plaintext = json.dumps(
        {"email": email, "password": password}, ensure_ascii=False, separators=(",", ":")
    )
    return {
        "version": CREDENTIALS_STORAGE_VERSION,
        "storage": "cryptography-fernet-local-key-file",
        "ciphertext": fernet_cls(key).encrypt(plaintext.encode("utf-8")).decode("ascii"),
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
    except invalid_token_cls as exc:
        raise BrainAPIError(
            "Failed to decrypt credentials. The local credentials key file may not match."
        ) from exc
    try:
        decoded = json.loads(plaintext)
    except Exception as exc:
        raise BrainAPIError(f"Failed to parse decrypted credentials: {exc}") from exc
    if not isinstance(decoded, dict):
        raise BrainAPIError("Decrypted credentials payload must be a JSON object.")
    return decoded.get("email"), decoded.get("password")


def is_encrypted_credentials_payload(payload: dict[str, Any]) -> bool:
    """判断凭证文件是否已经是加密格式。"""
    return (
        payload.get("version") == CREDENTIALS_STORAGE_VERSION
        and payload.get("storage") == "cryptography-fernet-local-key-file"
    )
