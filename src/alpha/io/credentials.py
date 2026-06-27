"""
凭证管理模块

本模块提供 WorldQuant Brain API 的凭证加密存储和管理功能。
支持将用户凭证加密保存到本地文件，避免重复输入。

主要功能：
    - 凭证加密存储与解密
    - 凭证文件权限管理
    - 交互式凭证输入与保存
    - 多来源凭证加载（命令行、环境变量、本地文件）

模块内容：
    - load_crypto_dependencies: 加载加密依赖
    - restrict_file_to_owner: 限制文件权限
    - read_or_create_credentials_key: 读取或创建加密密钥
    - encrypt_credentials_payload: 加密凭证
    - decrypt_credentials_payload: 解密凭证
    - is_encrypted_credentials_payload: 判断是否为加密格式
    - write_credentials_file: 写入凭证文件
    - prompt_and_store_credentials: 交互式凭证输入
    - load_credentials: 加载凭证
"""

import argparse
import getpass
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..exceptions import BrainAPIError
from ..io.output import atomic_write_json

logger = logging.getLogger(__name__)

# ============================================================================
# 常量定义
# ============================================================================

CREDENTIALS_STORAGE_VERSION: int = 4
"""
凭证存储格式版本号

当前版本为 4，使用 cryptography 库的 Fernet 对称加密。
版本号用于识别凭证文件格式，便于未来升级迁移。
"""


# ============================================================================
# 辅助函数
# ============================================================================

def ensure_parent_dir(path: str) -> None:
    """
    按需创建目标文件的父目录。

    如果指定的文件路径的父目录不存在，会自动创建所有必需的父目录。
    如果父目录已存在，则不做任何操作。

    Args:
        path: 文件路径，可以是相对路径或绝对路径。

    Example:
        >>> ensure_parent_dir("/path/to/output/result.json")
        # 如果 /path/to/output 目录不存在，会自动创建

    Note:
        路径中的波浪号 (~) 会被自动展开为用户主目录。
        使用 parents=True 确保创建所有缺失的父目录层级。
    """
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 加密相关函数
# ============================================================================

def load_crypto_dependencies() -> Tuple[Any, Any]:
    """
    加载跨平台加密依赖库。

    尝试导入 cryptography 库中的 Fernet 加密模块和 InvalidToken 异常类。
    如果依赖库未安装，会抛出包含安装提示的 BrainAPIError 异常。

    Returns:
        Tuple[Any, Any]: 返回一个元组，包含两个元素：
            - Fernet: Fernet 对称加密类
            - InvalidToken: 解密失败时抛出的异常类

    Raises:
        BrainAPIError: 当 cryptography 库未安装时抛出，
            包含安装命令提示。

    Example:
        >>> Fernet, InvalidToken = load_crypto_dependencies()
        >>> key = Fernet.generate_key()
        >>> cipher = Fernet(key)
        >>> encrypted = cipher.encrypt(b"secret message")

    Note:
        使用前需确保已安装 cryptography 库：
        $ python3 -m pip install cryptography
    """
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ModuleNotFoundError as exc:
        raise BrainAPIError(
            "Missing dependency 'cryptography'. Install it first: python3 -m pip install cryptography"
        ) from exc
    return Fernet, InvalidToken


def restrict_file_to_owner(path: str) -> None:
    """
    尽量将敏感本地文件权限收紧为仅当前用户可读写。

    尝试将文件权限设置为 0o600（仅所有者可读写），
    以增强安全性。如果操作失败（如权限不足或操作系统不支持），
    会静默忽略错误。

    Args:
        path: 要设置权限的文件路径。

    Example:
        >>> restrict_file_to_owner("/path/to/credentials.json")
        # 文件权限被设置为仅所有者可读写

    Note:
        - 在 Unix/Linux 系统上有效
        - 在 Windows 系统上可能无效，但不会抛出异常
        - 这是一个"尽力而为"的操作，失败不影响程序运行
    """
    with suppress(OSError):
        os.chmod(path, 0o600)


def read_or_create_credentials_key(key_path: str) -> bytes:
    """
    读取本地凭证加密密钥；不存在时生成并保存。

    如果密钥文件存在，读取并返回密钥内容。
    如果密钥文件不存在，生成新的 Fernet 密钥并保存到文件。

    Args:
        key_path: 密钥文件的路径。

    Returns:
        bytes: Fernet 加密密钥，长度为 44 字节的 URL-safe base64 编码字节串。

    Raises:
        BrainAPIError: 当密钥文件存在但内容为空时抛出。

    Example:
        >>> key = read_or_create_credentials_key("~/.wqb/credentials.key")
        >>> print(len(key))
        44

    Note:
        - 首次运行时会自动生成密钥文件
        - 密钥文件权限会被设置为 0o600（仅所有者可读写）
        - 生成的密钥文件会被打印到控制台，方便用户确认
    """
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
    return key


# ============================================================================
# 凭证加密与解密
# ============================================================================

def encrypt_credentials_payload(
    email: str,
    password: str,
    key_path: str
) -> Dict[str, Any]:
    """
    生成只包含密文的本地凭证 JSON 负载。

    使用 Fernet 对称加密算法对用户邮箱和密码进行加密，
    返回包含版本号、存储类型和密文的字典。

    Args:
        email: WorldQuant Brain 账号的邮箱地址。
        password: WorldQuant Brain 账号的密码。
        key_path: 加密密钥文件的路径。

    Returns:
        Dict[str, Any]: 包含以下字段的字典：
            - version (int): 凭证存储格式版本号
            - storage (str): 存储类型标识
            - ciphertext (str): 加密后的凭证内容（base64 编码）

    Example:
        >>> payload = encrypt_credentials_payload(
        ...     "user@example.com",
        ...     "my_password",
        ...     "~/.wqb/credentials.key"
        ... )
        >>> print(payload["version"])
        4
        >>> print(payload["storage"])
        cryptography-fernet-local-key-file

    Note:
        - 使用 UTF-8 编码存储凭证
        - JSON 序列化时使用紧凑格式（无空格）以减少存储空间
    """
    fernet_cls, _ = load_crypto_dependencies()
    key = read_or_create_credentials_key(key_path)
    plaintext = json.dumps(
        {"email": email, "password": password},
        ensure_ascii=False,
        separators=(",", ":")
    )
    return {
        "version": CREDENTIALS_STORAGE_VERSION,
        "storage": "cryptography-fernet-local-key-file",
        "ciphertext": fernet_cls(key).encrypt(plaintext.encode("utf-8")).decode("ascii"),
    }


def decrypt_credentials_payload(
    payload: Dict[str, Any],
    key_path: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    解密本地凭证 JSON 负载并返回账号密码。

    使用指定的密钥文件解密凭证负载，提取并返回邮箱和密码。

    Args:
        payload: 包含加密凭证的字典，必须包含 "ciphertext" 字段。
        key_path: 加密密钥文件的路径。

    Returns:
        Tuple[Optional[str], Optional[str]]: 返回一个元组，包含两个元素：
            - email (Optional[str]): 解密后的邮箱地址，可能为 None
            - password (Optional[str]): 解密后的密码，可能为 None

    Raises:
        BrainAPIError: 当以下情况发生时抛出：
            - 负载中缺少 ciphertext 字段
            - 密钥文件不存在
            - 解密失败（密钥不匹配）
            - 解密后的内容不是有效的 JSON

    Example:
        >>> email, password = decrypt_credentials_payload(
        ...     encrypted_payload,
        ...     "~/.wqb/credentials.key"
        ... )
        >>> print(email)
        user@example.com

    Note:
        - 密钥文件必须与加密时使用的密钥一致
        - 如果密钥文件丢失，需要重新输入凭证
    """
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
        plaintext = fernet_cls(key).decrypt(
            ciphertext.strip().encode("ascii")
        ).decode("utf-8")
    except invalid_token_cls as exc:
        raise BrainAPIError(
            "Failed to decrypt credentials. The local credentials key file may not match."
        ) from exc
    try:
        decoded = json.loads(plaintext)
    except Exception as exc:
        raise BrainAPIError(
            f"Failed to parse decrypted credentials: {exc}"
        ) from exc
    if not isinstance(decoded, dict):
        raise BrainAPIError("Decrypted credentials payload must be a JSON object.")
    return decoded.get("email"), decoded.get("password")


def is_encrypted_credentials_payload(payload: Dict[str, Any]) -> bool:
    """
    判断凭证文件是否已经是加密格式。

    检查凭证负载的版本号和存储类型，判断其是否为
    当前支持的加密格式。

    Args:
        payload: 凭证负载字典，通常从 JSON 文件加载。

    Returns:
        bool: 如果凭证是加密格式返回 True，否则返回 False。

    Example:
        >>> with open("credentials.json", "r") as f:
        ...     payload = json.load(f)
        >>> if is_encrypted_credentials_payload(payload):
        ...     print("凭证已加密")
        ... else:
        ...     print("凭证未加密，需要迁移")

    Note:
        当前支持的加密格式：
        - version == 4
        - storage == "cryptography-fernet-local-key-file"
    """
    return (
        payload.get("version") == CREDENTIALS_STORAGE_VERSION
        and payload.get("storage") == "cryptography-fernet-local-key-file"
    )


# ============================================================================
# 凭证文件操作
# ============================================================================

def write_credentials_file(
    path: str,
    key_path: str,
    email: str,
    password: str
) -> None:
    """
    将 WorldQuant 凭证加密写入本地 JSON 文件。

    使用指定的密钥文件对凭证进行加密，并以原子方式写入文件，
    确保写入过程的安全性。

    Args:
        path: 凭证文件的路径。
        key_path: 加密密钥文件的路径。
        email: WorldQuant Brain 账号的邮箱地址。
        password: WorldQuant Brain 账号的密码。

    Example:
        >>> write_credentials_file(
        ...     "~/.wqb/credentials.json",
        ...     "~/.wqb/credentials.key",
        ...     "user@example.com",
        ...     "my_password"
        ... )

    Note:
        - 如果父目录不存在，会自动创建
        - 使用原子写入，避免程序中断导致文件损坏
        - 凭证会被加密存储，不会以明文形式保存
    """
    ensure_parent_dir(path)
    atomic_write_json(
        path,
        encrypt_credentials_payload(email, password, key_path)
    )


def prompt_and_store_credentials(
    path: str,
    key_path: str
) -> Tuple[str, str]:
    """
    交互式读取凭证并加密保存，供后续运行复用。

    提示用户输入 WorldQuant Brain 账号的邮箱和密码，
    然后将凭证加密保存到指定的文件中。

    Args:
        path: 凭证文件的路径。
        key_path: 加密密钥文件的路径。

    Returns:
        Tuple[str, str]: 返回一个元组，包含两个元素：
            - email (str): 用户输入的邮箱地址
            - password (str): 用户输入的密码

    Raises:
        BrainAPIError: 当用户输入的邮箱或密码为空时抛出。

    Example:
        >>> email, password = prompt_and_store_credentials(
        ...     "~/.wqb/credentials.json",
        ...     "~/.wqb/credentials.key"
        ... )
        WorldQuant BRAIN email: user@example.com
        WorldQuant BRAIN password: [输入密码时不显示]

    Note:
        - 密码输入时不会在终端显示
        - 凭证会被加密存储，后续运行无需重新输入
        - 首次运行时会自动生成密钥文件
    """
    logger.info("[creds] credentials need to be entered or refreshed: %s", path)
    logger.info(
        "[creds] Please input your WorldQuant BRAIN credentials. "
        "They will be encrypted locally for future runs.",
    )
    email = input("WorldQuant BRAIN email: ").strip()
    password = getpass.getpass("WorldQuant BRAIN password: ").strip()
    if not email or not password:
        raise BrainAPIError(
            "Credentials were empty; aborted without saving credentials file."
        )
    write_credentials_file(path, key_path, email, password)
    logger.info("[creds] encrypted credentials saved to %s", path)
    return email, password


def load_credentials(args: argparse.Namespace) -> Tuple[Optional[str], Optional[str]]:
    """
    优先从命令行或环境变量读取凭证，否则回退到本地凭证文件。

    凭证加载的优先级顺序：
    1. 命令行参数（args.email 和 args.password）
    2. 本地加密凭证文件（args.creds_file）
    3. 交互式输入（如果凭证文件不存在）

    Args:
        args: 命令行参数命名空间，必须包含以下属性：
            - email: 命令行指定的邮箱（可能为 None）
            - password: 命令行指定的密码（可能为 None）
            - creds_file: 凭证文件路径
            - creds_key_file: 密钥文件路径

    Returns:
        Tuple[Optional[str], Optional[str]]: 返回一个元组，包含两个元素：
            - email (Optional[str]): 加载的邮箱地址
            - password (Optional[str]): 加载的密码

    Raises:
        BrainAPIError: 当以下情况发生时抛出：
            - 未指定凭证文件路径
            - 读取凭证文件失败
            - 凭证格式不支持

    Example:
        >>> import argparse
        >>> args = argparse.Namespace(
        ...     email=None,
        ...     password=None,
        ...     creds_file="~/.wqb/credentials.json",
        ...     creds_key_file="~/.wqb/credentials.key"
        ... )
        >>> email, password = load_credentials(args)
        >>> print(f"Loaded: {email}")

    Note:
        - 如果凭证文件是明文格式，会自动迁移到加密格式
        - 如果凭证文件不存在，会提示用户输入并保存
        - 支持的凭证格式：
            - 版本 4 加密格式（推荐）
            - 明文格式（会自动迁移）
    """
    # 优先使用命令行/环境变量提供的凭证
    # 否则回退到加密的本地凭证文件，避免重复输入
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

    try:
        with open(creds_file, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        raise BrainAPIError(
            f"Failed to read credentials file {creds_file}: {exc}"
        ) from exc

    if is_encrypted_credentials_payload(payload):
        file_email, file_password = decrypt_credentials_payload(
            payload, creds_key_file
        )
    else:
        file_email = payload.get("email")
        file_password = payload.get("password")
        if file_email and file_password:
            write_credentials_file(
                creds_file,
                creds_key_file,
                str(file_email),
                str(file_password)
            )
            logger.info(
                "[creds] migrated plaintext credentials to encrypted storage: %s", creds_file,
            )
        elif payload.get("ciphertext"):
            logger.info(
                "[creds] existing encrypted credentials use an unsupported old format; "
                "please re-enter them once.",
            )

    if not (email or file_email) or not (password or file_password):
        return prompt_and_store_credentials(creds_file, creds_key_file)
    return email or file_email, password or file_password
