#!/usr/bin/env python3
"""Test all fields in a WorldQuant Brain dataset and submit submittable alphas.

Usage examples:
  python3 worldquant_brain_dataset_submit.py
  python3 worldquant_brain_dataset_submit.py --smoke-test
  python3 worldquant_brain_dataset_submit.py --dry-run-plan
  python3 worldquant_brain_dataset_submit.py --limit 50 --max-templates-per-field 8
  python3 worldquant_brain_dataset_submit.py --full-run
  python3 worldquant_brain_dataset_submit.py --submit
  python3 worldquant_brain_dataset_submit.py --dataset-id fundamental6 --submit
  WQB_EMAIL=you@example.com WQB_PASSWORD=secret python3 worldquant_brain_dataset_submit.py --submit
"""

from __future__ import annotations

import argparse
import atexit
import base64
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import getpass
import hashlib
import json
import os
from pathlib import Path
import tempfile
import re
import sys
import threading
import time
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


API_BASE = "https://api.worldquantbrain.com"
AUTH_URL = f"{API_BASE}/authentication"
DATA_FIELDS_URL = f"{API_BASE}/data-fields"
SIMULATIONS_URL = f"{API_BASE}/simulations"
ALPHAS_URL = f"{API_BASE}/alphas"
DEFAULT_DATASET_ID = "fundamental6"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE_LIBRARY_FILE = str(SCRIPT_DIR / "worldquant_template_library.json")
DEFAULT_FIELDS_CACHE_FILE = str(SCRIPT_DIR / "fundamental6_fields_cache.json")
DEFAULT_CREDS_FILE = str(SCRIPT_DIR / "worldquant_brain_credentials.json")
DEFAULT_CREDS_KEY_FILE = str(SCRIPT_DIR / "worldquant_brain_credentials.key")
DEFAULT_OUTPUT_FILE = str(SCRIPT_DIR / "fundamental6_test_results.json")
CREDENTIALS_STORAGE_VERSION = 4
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}
VERSION_HEADER = {"Accept": "application/json;version=2.0"}
SIM_ACCEPT_HEADER = {"Accept": "application/json;version=3.0"}
DEFAULT_RATE_LIMIT_MAX_RETRIES = 5
RATIO_PARTNER_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "debt": ("cap", "fnd6_mkvalt", "fnd6_mkvaltq", "assets", "equity", "enterprise_value"),
    "debt_lt": ("fnd6_mkvalt", "fnd6_mkvaltq", "assets", "equity", "enterprise_value"),
    "debt_st": ("assets", "cash", "cash_st", "fnd6_mkvalt"),
    "liabilities": ("assets", "equity", "fnd6_mkvalt", "fnd6_mkvaltq", "cap", "liabilities_curr"),
    "liabilities_curr": ("assets", "equity", "fnd6_mkvalt", "fnd6_mkvaltq"),
    "cash": ("assets", "debt", "liabilities"),
    "cash_st": ("assets", "debt_st"),
    "cashflow": ("assets", "enterprise_value"),
    "cashflow_op": ("assets", "debt", "enterprise_value"),
    "capex": ("assets", "cashflow_op"),
    "ebit": ("assets", "enterprise_value"),
    "ebitda": ("assets", "enterprise_value"),
    "equity": ("assets", "enterprise_value"),
    "enterprise_value": ("assets", "ebitda", "cashflow_op"),
}
POSITIVE_RAW_FIELDS = {
    "assets",
    "assets_curr",
    "bookvalue_ps",
    "cash",
    "cash_st",
    "cashflow",
    "cashflow_op",
    "current_ratio",
    "ebit",
    "ebitda",
    "enterprise_value",
    "eps",
    "equity",
}
NEGATIVE_RAW_FIELDS = {
    "cogs",
    "debt",
    "debt_lt",
    "debt_st",
    "liabilities",
}
RATIO_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "debt": ("cap", "assets", "equity", "enterprise_value", "liabilities"),
    "liabilities": ("assets", "equity", "cap", "enterprise_value"),
    "cash": ("debt", "liabilities", "assets", "enterprise_value"),
    "cashflow": ("assets", "enterprise_value", "debt"),
    "cashflow_op": ("assets", "enterprise_value", "debt"),
    "capex": ("cashflow_op", "assets", "enterprise_value"),
    "ebit": ("assets", "enterprise_value", "sales", "revenue"),
    "ebitda": ("assets", "enterprise_value", "sales", "revenue"),
    "equity": ("assets", "enterprise_value", "debt"),
    "enterprise_value": ("assets", "ebitda", "ebit", "cashflow_op"),
    "assets": ("debt", "liabilities", "equity", "cash", "enterprise_value"),
}


def use_fundamental6_heuristics(dataset_id: str) -> bool:
    """判断是否启用 fundamental6 专属字段与模板启发式。
    Return whether fundamental6-specific field/template heuristics should be enabled.
    """
    return dataset_id == DEFAULT_DATASET_ID


class BrainAPIError(RuntimeError):
    """当 Brain API 返回非预期响应时抛出。
    Raised when the Brain API returns an unexpected response.
    """


class BrainRateLimitError(BrainAPIError):
    """当 Brain API 持续触发限流时抛出。
    Raised when the Brain API keeps returning rate limits.
    """

    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class BrainQueueBusyError(BrainAPIError):
    """当模拟任务排队过久且需要主动退避时抛出。
    Raised when simulations stay queued too long and we should back off.
    """


@dataclass
class FieldTestResult:
    """字段模板测试结果的数据载体。
    Data container for one field-template test result.
    """

    field_id: str
    field_type: str
    field_name: str
    template_name: str
    simulation_id: Optional[str]
    alpha_id: Optional[str]
    status: str
    submittable: Optional[bool]
    submitted: bool
    message: str
    expression: str
    settings_fingerprint: str = ""
    template_library_fingerprint: str = ""
    failed_stage: Optional[str] = None
    failed_checks: Optional[List[Dict[str, Any]]] = None


TemplateLibrary = Dict[str, List[Dict[str, Any]]]
SettingsVariant = Dict[str, Any]


@dataclass(frozen=True)
class RunPaths:
    """一次运行所使用的已解析文件路径集合。
    Resolved filesystem layout for one script run.
    """

    creds_file: str
    creds_key_file: str
    template_library_file: str
    fields_cache_file: str
    output: str
    feedback_output: str
    include_fields_file: str
    exclude_fields_file: str
    include_templates_file: str
    exclude_templates_file: str


@dataclass
class RuntimeConcurrencyState:
    """运行期并发调度与拥塞退避状态。
    Mutable runtime scheduling state for queue backoff and worker throttling.
    """

    max_workers: int
    runtime_max_workers: int
    cooldown_until: float = 0.0


@dataclass(frozen=True)
class RunFilters:
    """字段与模板的包含/排除过滤器集合。
    Loaded include/exclude filters for fields and templates.
    """

    include_fields: set[str]
    exclude_fields: set[str]
    include_templates: set[str]
    exclude_templates: set[str]


@dataclass
class HistoricalRunState:
    """续跑时复用的历史结果与派生信号。
    Historical results and derived signals reused across resumed runs.
    """

    existing_results: List[FieldTestResult]
    attempted_keys: set[Tuple[str, str, str, str]]
    template_stats: Dict[str, Dict[str, int]]
    field_feedback: Dict[str, Dict[str, Any]]


@dataclass
class ExecutionState:
    """执行过程中可变的待运行、跳过与累计结果状态。
    Mutable execution-time state for pending work, skips, and accumulated results.
    """

    results: List[FieldTestResult]
    attempted_keys: set[Tuple[str, str, str, str]]
    template_stats: Dict[str, Dict[str, int]]
    pending_futures: Dict[Future[FieldTestResult], Dict[str, Any]]
    field_queue_busy_counts: Dict[str, int]
    skipped_fields_due_to_queue: set[str]
    last_submission_at: float = 0.0


class TeeStream:
    """将同一份输出同时写到多个流，用于终端与文件双写日志。
    Write the same output to multiple streams for terminal-and-file logging.
    """

    def __init__(self, *streams: Any) -> None:
        """保存需要同步写入的底层输出流。
        Store the underlying streams that should receive mirrored output.
        """
        self.streams = streams
        self._line_started = False

    def write(self, data: str) -> int:
        """把文本写入所有输出流并返回写入长度。
        Write text to all streams and return the written length.
        """
        if not data:
            return 0

        chunks: List[str] = []
        for piece in data.splitlines(keepends=True):
            if not self._line_started:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                chunks.append(f"[{timestamp}] ")
                self._line_started = True
            chunks.append(piece)
            if piece.endswith("\n"):
                self._line_started = False

        formatted = "".join(chunks)
        for stream in self.streams:
            try:
                stream.write(formatted)
            except ValueError:
                # Interpreter shutdown can close one stream before another.
                continue
        return len(data)

    def flush(self) -> None:
        """刷新所有底层输出流，保证日志及时可见。
        Flush all underlying streams so logs stay visible in real time.
        """
        for stream in self.streams:
            try:
                stream.flush()
            except ValueError:
                continue


def parse_args() -> argparse.Namespace:
    """解析命令行参数，包括数据集、搜索策略和本地文件配置。
    Parse CLI flags for dataset selection, search strategy, and local files.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--creds-file",
        default=DEFAULT_CREDS_FILE,
        help="Local JSON file with email/password fields",
    )
    parser.add_argument(
        "--creds-key-file",
        default=DEFAULT_CREDS_KEY_FILE,
        help="Local key file used to encrypt/decrypt --creds-file",
    )
    parser.add_argument("--email", default=os.getenv("WQB_EMAIL"))
    parser.add_argument("--password", default=os.getenv("WQB_PASSWORD"))
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID)
    parser.add_argument("--region", default="USA")
    parser.add_argument("--universe", default="TOP3000")
    parser.add_argument("--instrument-type", default="EQUITY")
    parser.add_argument("--delay", type=int, default=1)
    parser.add_argument("--decay", type=int, default=5)
    parser.add_argument("--neutralization", default="SUBINDUSTRY")
    parser.add_argument("--truncation", type=float, default=0.05)
    parser.add_argument("--nan-handling", default="ON")
    run_mode_group = parser.add_mutually_exclusive_group()
    run_mode_group.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run a tiny one-field/one-template flow check; not useful for alpha discovery",
    )
    run_mode_group.add_argument(
        "--full-run",
        action="store_true",
        help="Run all fetched fields and all generated templates; can be slow and queue-heavy",
    )
    parser.add_argument("--limit", type=int, default=20, help="How many fields to fetch/test; 0 means all fields")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--sleep-between-fields", type=float, default=2.0)
    parser.add_argument(
        "--max-templates-per-field",
        type=int,
        default=5,
        help="0 means try all built-in templates for each field",
    )
    parser.add_argument(
        "--max-templates-per-family",
        type=int,
        default=1,
        help="Keep only the top-N candidates from each expression family per field; 0 disables family capping",
    )
    parser.add_argument(
        "--legacy-similarity-penalty",
        type=int,
        default=42,
        help="Priority penalty applied to raw/group-rank/simple-ratio templates that tend to look too similar to prior submissions",
    )
    parser.add_argument(
        "--disable-legacy-after",
        type=int,
        default=8,
        help="Globally disable legacy-style template families after this many zero-submittable attempts; 0 disables this guard",
    )
    parser.add_argument(
        "--template-library-file",
        default=DEFAULT_TEMPLATE_LIBRARY_FILE,
        help="Local JSON file describing per-field-type template library",
    )
    parser.add_argument(
        "--feedback-output",
        default="",
        help="Optional prior results JSON used only for field/template feedback ranking; defaults to --output",
    )
    parser.add_argument(
        "--fields-cache-file",
        default=DEFAULT_FIELDS_CACHE_FILE,
        help="Optional local JSON cache for fetched data-fields metadata",
    )
    parser.add_argument(
        "--refresh-fields-cache",
        action="store_true",
        help="Force refetching dataset fields and overwrite the local fields cache",
    )
    parser.add_argument(
        "--dry-run-plan",
        action="store_true",
        help="Print the planned fields/templates without creating simulations",
    )
    parser.add_argument(
        "--include-fields-file",
        default="",
        help="Optional text file listing field ids/names to include, one per line",
    )
    parser.add_argument(
        "--exclude-fields-file",
        default="",
        help="Optional text file listing field ids/names to exclude, one per line",
    )
    parser.add_argument(
        "--include-templates-file",
        default="",
        help="Optional text file listing template names to include, one per line",
    )
    parser.add_argument(
        "--exclude-templates-file",
        default="",
        help="Optional text file listing template names to exclude, one per line",
    )
    parser.add_argument(
        "--template-disable-after",
        type=int,
        default=12,
        help="Disable a template globally after this many attempts with zero submittable results; 0 disables auto-pruning",
    )
    parser.add_argument(
        "--top-fields-by-feedback",
        type=int,
        default=0,
        help="If >0, only test the top-N fields ranked by prior near-pass feedback",
    )
    parser.add_argument(
        "--stop-after-submittable",
        type=int,
        default=0,
        help="If >0, stop the run after finding this many submittable alphas in the current output file",
    )
    parser.add_argument(
        "--min-request-interval",
        type=float,
        default=1.25,
        help="Proactive delay between outbound API requests to reduce hitting rate limits",
    )
    parser.add_argument(
        "--rate-limit-max-retries",
        type=int,
        default=DEFAULT_RATE_LIMIT_MAX_RETRIES,
        help="Skip the current template after this many consecutive 429 retries inside one API call",
    )
    parser.add_argument("--login-retries", type=int, default=3)
    parser.add_argument("--field-fetch-retries", type=int, default=3)
    parser.add_argument("--simulation-create-retries", type=int, default=3)
    parser.add_argument("--simulation-poll-retries", type=int, default=3)
    parser.add_argument(
        "--max-concurrent-simulations",
        type=int,
        default=2,
        help="How many field-template simulations to run in parallel; runtime cooldown drops to 1 on queue congestion",
    )
    parser.add_argument(
        "--max-concurrent-creates",
        type=int,
        default=1,
        help="How many simulation create requests may run at once; keep this low to avoid create-stage rate limits",
    )
    parser.add_argument(
        "--simulation-max-polls",
        type=int,
        default=240,
        help="Maximum poll iterations for a single simulation before skipping the current template",
    )
    parser.add_argument(
        "--simulation-max-wait-seconds",
        type=float,
        default=1800.0,
        help="Maximum total wait time for a single simulation before skipping the current template",
    )
    parser.add_argument(
        "--simulation-max-pending-cycles",
        type=int,
        default=120,
        help="Skip the current template when one simulation stays pending for too many Retry-After cycles",
    )
    parser.add_argument(
        "--simulation-max-queue-seconds",
        type=float,
        default=600.0,
        help="Skip the current template when one simulation stays queued longer than this wall-clock budget",
    )
    parser.add_argument(
        "--queue-busy-cooldown-seconds",
        type=float,
        default=180.0,
        help="Temporarily reduce runtime concurrency after queue congestion or concurrent simulation limit errors",
    )
    parser.add_argument(
        "--field-queue-busy-skip-after",
        type=int,
        default=2,
        help="Skip the rest of a field's templates after this many queue-busy simulation failures; 0 disables field-level skipping",
    )
    parser.add_argument("--check-submit-retries", type=int, default=3)
    parser.add_argument("--submit-retries", type=int, default=3)
    parser.add_argument("--submit", action="store_true", help="Submit when checks pass")
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help="Where to save the full JSON results",
    )
    args = parser.parse_args()
    if args.smoke_test:
        args.limit = 1
        args.max_templates_per_field = 1
        args.max_concurrent_simulations = 1
        args.max_concurrent_creates = 1
    elif args.full_run:
        args.limit = 0
        args.max_templates_per_field = 0
    return args


def ensure_parent_dir(path: str) -> None:
    """按需创建目标文件的父目录。
    Create the parent directory for a file path when needed.
    """
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def load_crypto_dependencies() -> Tuple[Any, Any]:
    """加载跨平台加密依赖；缺失时给出安装提示。
    Load cross-platform crypto dependencies and show an install hint when missing.
    """
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ModuleNotFoundError as exc:
        raise BrainAPIError(
            "Missing dependency 'cryptography'. Install it first: python3 -m pip install cryptography"
        ) from exc
    return Fernet, InvalidToken


def restrict_file_to_owner(path: str) -> None:
    """尽量将敏感本地文件权限收紧为仅当前用户可读写。
    Best-effort restrict a sensitive local file to owner read/write only.
    """
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def read_or_create_credentials_key(key_path: str) -> bytes:
    """读取本地凭证加密 key；不存在时生成并保存。
    Read the local credential encryption key, creating and saving it if missing.
    """
    Fernet, _ = load_crypto_dependencies()
    if os.path.exists(key_path):
        restrict_file_to_owner(key_path)
        with open(key_path, "rb") as handle:
            key = handle.read().strip()
        if key:
            return key
        raise BrainAPIError(f"Credentials key file is empty: {key_path}")

    ensure_parent_dir(key_path)
    key = Fernet.generate_key()
    with open(key_path, "wb") as handle:
        handle.write(key + b"\n")
    restrict_file_to_owner(key_path)
    print(f"[creds] generated local credentials key file: {key_path}", flush=True)
    return key


def encrypt_credentials_payload(email: str, password: str, key_path: str) -> Dict[str, Any]:
    """生成只包含密文的本地凭证 JSON 负载。
    Build a local credentials JSON payload that contains only ciphertext.
    """
    Fernet, _ = load_crypto_dependencies()
    key = read_or_create_credentials_key(key_path)
    plaintext = json.dumps({"email": email, "password": password}, ensure_ascii=False, separators=(",", ":"))
    return {
        "version": CREDENTIALS_STORAGE_VERSION,
        "storage": "cryptography-fernet-local-key-file",
        "ciphertext": Fernet(key).encrypt(plaintext.encode("utf-8")).decode("ascii"),
    }


def decrypt_credentials_payload(payload: Dict[str, Any], key_path: str) -> Tuple[Optional[str], Optional[str]]:
    """解密本地凭证 JSON 负载并返回账号密码。
    Decrypt the local credentials JSON payload and return email/password.
    """
    Fernet, InvalidToken = load_crypto_dependencies()
    ciphertext = payload.get("ciphertext")
    if not isinstance(ciphertext, str) or not ciphertext.strip():
        raise BrainAPIError("Encrypted credentials file is missing ciphertext.")
    if not os.path.exists(key_path):
        raise BrainAPIError(f"Credentials key file not found: {key_path}. Please re-enter credentials once.")
    key = read_or_create_credentials_key(key_path)
    try:
        plaintext = Fernet(key).decrypt(ciphertext.strip().encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise BrainAPIError("Failed to decrypt credentials. The local credentials key file may not match.") from exc
    try:
        decoded = json.loads(plaintext)
    except Exception as exc:  # noqa: BLE001
        raise BrainAPIError(f"Failed to parse decrypted credentials: {exc}") from exc
    if not isinstance(decoded, dict):
        raise BrainAPIError("Decrypted credentials payload must be a JSON object.")
    return decoded.get("email"), decoded.get("password")


def is_encrypted_credentials_payload(payload: Dict[str, Any]) -> bool:
    """判断凭证文件是否已经是加密格式。
    Return whether a credentials payload already uses the encrypted format.
    """
    return payload.get("version") == CREDENTIALS_STORAGE_VERSION and payload.get("storage") == "cryptography-fernet-local-key-file"


def write_credentials_file(path: str, key_path: str, email: str, password: str) -> None:
    """将 WorldQuant 凭证加密写入本地 JSON 文件。
    Persist WorldQuant credentials to a local encrypted JSON sidecar file.
    """
    ensure_parent_dir(path)
    atomic_write_json(path, encrypt_credentials_payload(email, password, key_path))


def prompt_and_store_credentials(path: str, key_path: str) -> Tuple[str, str]:
    """交互式读取凭证并加密保存，供后续运行复用。
    Prompt interactively for credentials, then store them encrypted for future runs.
    """
    print(f"[creds] credentials need to be entered or refreshed: {path}", flush=True)
    print(
        "[creds] Please input your WorldQuant BRAIN credentials. They will be encrypted locally for future runs.",
        flush=True,
    )
    email = input("WorldQuant BRAIN email: ").strip()
    password = getpass.getpass("WorldQuant BRAIN password: ").strip()
    if not email or not password:
        raise BrainAPIError("Credentials were empty; aborted without saving credentials file.")
    write_credentials_file(path, key_path, email, password)
    print(f"[creds] encrypted credentials saved to {path}", flush=True)
    return email, password


def load_credentials(args: argparse.Namespace) -> Tuple[Optional[str], Optional[str]]:
    """优先从命令行或环境变量读取凭证，否则回退到本地凭证文件。
    Load credentials from CLI/env first, then fall back to the local creds file.
    """
    # Prefer explicit CLI / environment credentials; otherwise fall back to
    # the encrypted local JSON file so repeated runs do not require re-entering secrets.
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
        with open(creds_file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:  # noqa: BLE001
        raise BrainAPIError(f"Failed to read credentials file {creds_file}: {exc}") from exc

    if is_encrypted_credentials_payload(payload):
        file_email, file_password = decrypt_credentials_payload(payload, creds_key_file)
    else:
        file_email = payload.get("email")
        file_password = payload.get("password")
        if file_email and file_password:
            write_credentials_file(creds_file, creds_key_file, str(file_email), str(file_password))
            print(f"[creds] migrated plaintext credentials to encrypted storage: {creds_file}", flush=True)
        elif payload.get("ciphertext"):
            print(
                "[creds] existing encrypted credentials use an unsupported old format; please re-enter them once.",
                flush=True,
            )

    if not (email or file_email) or not (password or file_password):
        return prompt_and_store_credentials(creds_file, creds_key_file)
    return email or file_email, password or file_password


def default_template_library() -> TemplateLibrary:
    """返回内置模板库，在未提供外部 JSON 时作为默认策略集合。
    Return the built-in template library used when no JSON file is provided.
    """
    # Template expressions use {field} and are expanded per field at runtime.
    return {
        "default": [
            {"name": "ts_mean_20", "expression": "rank(ts_mean({field}, 20))"},
            {"name": "ts_mean_60", "expression": "rank(ts_mean({field}, 60))"},
            {"name": "ts_mean_120", "expression": "rank(ts_mean({field}, 120))"},
            {"name": "backfill_120", "expression": "rank(ts_backfill({field}, 120))"},
            {"name": "backfill_mean_60", "expression": "rank(ts_mean(ts_backfill({field}, 120), 60))"},
            {"name": "ts_rank_60", "expression": "rank(ts_rank({field}, 60))"},
            {"name": "ts_rank_120", "expression": "rank(ts_rank({field}, 120))"},
            {"name": "ts_zscore_60", "expression": "rank(ts_zscore({field}, 60))"},
            {"name": "ts_zscore_120", "expression": "rank(ts_zscore(ts_backfill({field}, 120), 120))"},
            {"name": "zscore", "expression": "rank(zscore({field}))"},
            {"name": "scale", "expression": "rank(scale({field}))"},
            {"name": "delta_20", "expression": "rank(ts_delta({field}, 20))"},
            {"name": "delta_60", "expression": "rank(ts_delta({field}, 60))"},
            {"name": "decay_20", "expression": "rank(ts_decay_linear(ts_backfill({field}, 120), 20))"},
            {"name": "stddev_60", "expression": "rank(ts_std_dev({field}, 60))"},
            {"name": "sum_20", "expression": "rank(ts_sum({field}, 20))"},
            {"name": "argmax_60", "expression": "rank(ts_arg_max({field}, 60))"},
            {"name": "argmin_60", "expression": "rank(ts_arg_min({field}, 60))"},
        ],
        "VECTOR": [
            {"name": "vec_avg_rank", "expression": "rank(vec_avg({field}))"},
            {"name": "vec_avg_ts_mean_20", "expression": "rank(ts_mean(vec_avg({field}), 20))"},
            {"name": "vec_avg_ts_mean_60", "expression": "rank(ts_mean(vec_avg({field}), 60))"},
            {"name": "vec_avg_backfill_120", "expression": "rank(ts_backfill(vec_avg({field}), 120))"},
            {"name": "vec_avg_ts_rank_60", "expression": "rank(ts_rank(vec_avg({field}), 60))"},
            {"name": "vec_avg_ts_zscore_60", "expression": "rank(ts_zscore(vec_avg({field}), 60))"},
            {"name": "vec_avg_zscore", "expression": "rank(zscore(vec_avg({field})))"},
            {"name": "vec_avg_scale", "expression": "rank(scale(vec_avg({field})))"},
            {"name": "vec_avg_delta_20", "expression": "rank(ts_delta(vec_avg({field}), 20))"},
            {
                "name": "vec_avg_decay_20",
                "expression": "rank(ts_decay_linear(ts_backfill(vec_avg({field}), 120), 20))",
            },
        ],
        "GROUP": [
            {"name": "vec_avg_rank", "expression": "rank(vec_avg({field}))"},
            {"name": "vec_avg_ts_mean_20", "expression": "rank(ts_mean(vec_avg({field}), 20))"},
            {"name": "vec_avg_ts_rank_60", "expression": "rank(ts_rank(vec_avg({field}), 60))"},
            {"name": "vec_avg_ts_zscore_60", "expression": "rank(ts_zscore(vec_avg({field}), 60))"},
        ],
        "SET": [
            {"name": "vec_avg_rank", "expression": "rank(vec_avg({field}))"},
            {"name": "vec_avg_ts_mean_20", "expression": "rank(ts_mean(vec_avg({field}), 20))"},
            {"name": "vec_avg_ts_rank_60", "expression": "rank(ts_rank(vec_avg({field}), 60))"},
            {"name": "vec_avg_ts_zscore_60", "expression": "rank(ts_zscore(vec_avg({field}), 60))"},
        ],
        "STRING": [
            {"name": "raw_field", "expression": "{field}"},
            {"name": "rank_raw_field", "expression": "rank({field})"},
        ],
        "TEXT": [
            {"name": "raw_field", "expression": "{field}"},
            {"name": "rank_raw_field", "expression": "rank({field})"},
        ],
        "BOOL": [
            {"name": "raw_field", "expression": "{field}"},
            {"name": "rank_raw_field", "expression": "rank({field})"},
        ],
        "BOOLEAN": [
            {"name": "raw_field", "expression": "{field}"},
            {"name": "rank_raw_field", "expression": "rank({field})"},
        ],
    }


def load_template_library(path: str) -> TemplateLibrary:
    """加载并校验外部模板库 JSON 文件。
    Load and validate an external template library JSON file.
    """
    # Externalizing the template library makes it easy to expand/shrink
    # search coverage without touching the Python code.
    if not path or not os.path.exists(path):
        return default_template_library()

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:  # noqa: BLE001
        raise BrainAPIError(f"Failed to read template library file {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise BrainAPIError(f"Template library file {path} must contain a JSON object.")

    validated: TemplateLibrary = {}
    for field_type, templates in payload.items():
        if not isinstance(field_type, str):
            raise BrainAPIError("Template library keys must be strings.")
        if not isinstance(templates, list):
            raise BrainAPIError(f"Template library entry '{field_type}' must be a list.")
        validated[field_type] = []
        for index, item in enumerate(templates):
            if not isinstance(item, dict):
                raise BrainAPIError(f"Template '{field_type}[{index}]' must be an object.")
            if "name" not in item or "expression" not in item:
                raise BrainAPIError(f"Template '{field_type}[{index}]' must include name and expression.")
            if not isinstance(item["name"], str) or not item["name"].strip():
                raise BrainAPIError(f"Template '{field_type}[{index}]' name must be a non-empty string.")
            if not isinstance(item["expression"], str) or not item["expression"].strip():
                raise BrainAPIError(f"Template '{field_type}[{index}]' expression must be a non-empty string.")
            priority = item.get("priority", 0)
            if not isinstance(priority, int):
                raise BrainAPIError(f"Template '{field_type}[{index}]' priority must be an integer.")
            validated[field_type].append(
                {
                    "name": item["name"].strip(),
                    "expression": item["expression"].strip(),
                    "priority": priority,
                }
            )
    return validated


def load_name_filter_file(path: str) -> set[str]:
    """加载按行分隔的简单包含/排除过滤文件。
    Load a simple newline-delimited include/exclude filter file.
    """
    if not path:
        return set()
    if not os.path.exists(path):
        raise BrainAPIError(f"Filter file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle.readlines()]
    except Exception as exc:  # noqa: BLE001
        raise BrainAPIError(f"Failed to read filter file {path}: {exc}") from exc
    return {line for line in lines if line and not line.startswith("#")}


def stable_fingerprint(payload: Any) -> str:
    """为配置、模板或结果标识生成稳定的短哈希。
    Generate a stable short hash for settings, templates, or result identities.
    """
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def atomic_write_json(path: str, payload: Any) -> None:
    """以原子方式写入 JSON，避免中断运行破坏状态文件。
    Write JSON atomically so interrupted runs do not corrupt state files.
    """
    # Write to a temporary file first, then atomically replace the target.
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def resolve_cli_path(path: str) -> str:
    """将 CLI 文件路径解析为相对于脚本目录的绝对路径。
    Resolve a CLI file argument to an absolute path relative to the script directory.
    """
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = SCRIPT_DIR / candidate
    return str(candidate.resolve())


def sanitize_dataset_id_for_filename(dataset_id: str) -> str:
    """将 dataset_id 转成适合文件名的安全片段。
    Convert a dataset_id into a filesystem-friendly filename fragment.
    """
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", dataset_id.strip())
    return sanitized or DEFAULT_DATASET_ID


def build_dataset_scoped_paths(dataset_id: str) -> Dict[str, str]:
    """根据 dataset_id 派生默认缓存、结果与模板库路径。
    Derive dataset-scoped default cache, output, and template-library paths.
    """
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    return {
        "template_library_file": str(SCRIPT_DIR / f"worldquant_template_library_{dataset_key}.json"),
        "fields_cache_file": str(SCRIPT_DIR / f"{dataset_key}_fields_cache.json"),
        "output": str(SCRIPT_DIR / f"{dataset_key}_test_results.json"),
    }


def build_output_sidecar_paths(output_path: str) -> Dict[str, str]:
    """生成主结果文件旁边的精简分析与日志路径。
    Return the compact analysis and runtime log paths beside the main results file.
    """
    output = Path(output_path)
    base_dir = output.parent
    base_name = output.stem
    log_date = time.strftime("%Y-%m-%d")
    return {
        "analysis": str(base_dir / f"{base_name}_analysis.json"),
        "run_log": str(base_dir / f"{base_name}_{log_date}_run.log"),
    }


def cleanup_legacy_sidecar_files(output_path: str, *, verbose: bool = False) -> None:
    """删除旧版分散 summary 文件，避免目录里反复出现过时输出。
    Delete legacy split summary files so only the compact output layout remains.
    """
    output = Path(output_path)
    base_dir = output.parent
    base_name = output.stem
    legacy_suffixes = (
        "_submittable.json",
        "_submitted.json",
        "_failed_checks_summary.json",
        "_template_performance_summary.json",
        "_field_performance_summary.json",
        "_run_config.json",
    )
    for suffix in legacy_suffixes:
        legacy_path = base_dir / f"{base_name}{suffix}"
        try:
            legacy_path.unlink()
            if verbose:
                print(f"[cleanup] removed legacy sidecar file {legacy_path}", flush=True)
        except FileNotFoundError:
            continue


def normalize_args_paths(args: argparse.Namespace) -> RunPaths:
    """在启动早期一次性规范化所有路径类命令行参数。
    Normalize all path-like CLI arguments once near startup.
    """
    dataset_scoped_paths = build_dataset_scoped_paths(args.dataset_id)
    if args.template_library_file == DEFAULT_TEMPLATE_LIBRARY_FILE:
        dataset_template_path = dataset_scoped_paths["template_library_file"]
        args.template_library_file = dataset_template_path if os.path.exists(dataset_template_path) else DEFAULT_TEMPLATE_LIBRARY_FILE
    if args.fields_cache_file == DEFAULT_FIELDS_CACHE_FILE:
        args.fields_cache_file = dataset_scoped_paths["fields_cache_file"]
    if args.output == DEFAULT_OUTPUT_FILE:
        args.output = dataset_scoped_paths["output"]
    args.creds_file = resolve_cli_path(args.creds_file)
    args.creds_key_file = resolve_cli_path(args.creds_key_file)
    args.template_library_file = resolve_cli_path(args.template_library_file)
    args.fields_cache_file = resolve_cli_path(args.fields_cache_file)
    args.output = resolve_cli_path(args.output)
    args.feedback_output = resolve_cli_path(args.feedback_output) if args.feedback_output else ""
    args.include_fields_file = resolve_cli_path(args.include_fields_file) if args.include_fields_file else ""
    args.exclude_fields_file = resolve_cli_path(args.exclude_fields_file) if args.exclude_fields_file else ""
    args.include_templates_file = resolve_cli_path(args.include_templates_file) if args.include_templates_file else ""
    args.exclude_templates_file = resolve_cli_path(args.exclude_templates_file) if args.exclude_templates_file else ""
    return RunPaths(
        creds_file=args.creds_file,
        creds_key_file=args.creds_key_file,
        template_library_file=args.template_library_file,
        fields_cache_file=args.fields_cache_file,
        output=args.output,
        feedback_output=args.feedback_output,
        include_fields_file=args.include_fields_file,
        exclude_fields_file=args.exclude_fields_file,
        include_templates_file=args.include_templates_file,
        exclude_templates_file=args.exclude_templates_file,
    )


def relativize_path_for_storage(path: str) -> str:
    """将路径转成相对于脚本目录的形式，便于目录整体迁移。
    Convert a path into a script-relative form for portable config storage.
    """
    if not path:
        return ""
    candidate = Path(path).expanduser().resolve()
    try:
        return os.path.relpath(str(candidate), str(SCRIPT_DIR))
    except ValueError:
        # On uncommon cross-volume cases, keep the absolute path as fallback.
        return str(candidate)


def build_run_config_snapshot(args: argparse.Namespace, run_paths: RunPaths) -> Dict[str, Any]:
    """构建写入配置快照文件的运行参数，路径字段统一保存为相对路径。
    Build a run-config snapshot whose path fields are stored as relative paths.
    """
    snapshot = vars(args).copy()
    for key in (
        "creds_file",
        "creds_key_file",
        "template_library_file",
        "fields_cache_file",
        "output",
        "feedback_output",
        "include_fields_file",
        "exclude_fields_file",
        "include_templates_file",
        "exclude_templates_file",
    ):
        snapshot[key] = relativize_path_for_storage(getattr(run_paths, key))
    snapshot["script_dir"] = "."
    snapshot["script_name"] = Path(__file__).name
    return snapshot


def load_run_filters(run_paths: RunPaths) -> RunFilters:
    """从磁盘加载所有可选的字段与模板过滤器。
    Load all optional field/template include-exclude filters from disk.
    """
    return RunFilters(
        include_fields=load_name_filter_file(run_paths.include_fields_file),
        exclude_fields=load_name_filter_file(run_paths.exclude_fields_file),
        include_templates=load_name_filter_file(run_paths.include_templates_file),
        exclude_templates=load_name_filter_file(run_paths.exclude_templates_file),
    )


def setup_runtime_logging(log_path: str) -> None:
    """把标准输出与错误输出同步写入日志文件，便于实时跟踪运行状态。
    Mirror stdout and stderr into a log file for real-time run tracking.
    """
    ensure_parent_dir(log_path)
    log_handle = open(log_path, "a", encoding="utf-8", buffering=1)
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    def close_runtime_logging() -> None:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_handle.close()

    atexit.register(close_runtime_logging)
    sys.stdout = TeeStream(sys.__stdout__, log_handle)
    sys.stderr = TeeStream(sys.__stderr__, log_handle)
    print(f"[log] streaming runtime logs to {log_path}", flush=True)


def load_fields_cache(
    path: str,
    *,
    dataset_id: str,
    region: str,
    universe: str,
    instrument_type: str,
    delay: int,
) -> List[Dict[str, Any]]:
    """仅在数据集上下文完全匹配时加载字段缓存。
    Load cached field metadata only when the dataset context matches exactly.
    """
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    cache_key = payload.get("cache_key", {})
    expected_key = {
        "dataset_id": dataset_id,
        "region": region,
        "universe": universe,
        "instrument_type": instrument_type,
        "delay": delay,
    }
    if cache_key != expected_key:
        return []
    rows = payload.get("fields")
    return rows if isinstance(rows, list) else []


def save_fields_cache(
    path: str,
    *,
    dataset_id: str,
    region: str,
    universe: str,
    instrument_type: str,
    delay: int,
    fields: Sequence[Dict[str, Any]],
) -> None:
    """保存字段元数据及其缓存作用域键。
    Persist fetched field metadata along with the cache scope key.
    """
    if not path:
        return
    atomic_write_json(
        path,
        {
            "cache_key": {
                "dataset_id": dataset_id,
                "region": region,
                "universe": universe,
                "instrument_type": instrument_type,
                "delay": delay,
            },
            "count": len(fields),
            "fields": list(fields),
        },
    )


def fields_cache_refresh_reason(
    cached_fields: Sequence[Dict[str, Any]],
    *,
    requested_limit: int,
    requested_offset: int,
    force_refresh: bool,
) -> str:
    """判断字段缓存是否应刷新，并返回可打印的原因。
    Decide whether the fields cache should be refreshed and return a printable reason.
    """
    if force_refresh:
        return "forced by --refresh-fields-cache"
    if not cached_fields:
        return "cache missing or invalid"
    if requested_offset > 0:
        return "non-zero --offset requires an exact field fetch"
    if requested_limit == 0:
        return "all-fields request requires a complete field fetch"
    if requested_limit > 0 and len(cached_fields) < requested_limit:
        return f"cache has {len(cached_fields)} fields but current limit requests {requested_limit}"
    return ""


def merge_fields_by_id(existing_fields: Sequence[Dict[str, Any]], new_fields: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按字段 ID 合并缓存和新拉取字段，保持原始顺序并去重。
    Merge cached and newly fetched fields by field id while preserving order.
    """
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for field in list(existing_fields) + list(new_fields):
        field_id = str(first_non_empty(field.get("id"), field.get("name"), ""))
        if field_id and field_id in seen:
            continue
        if field_id:
            seen.add(field_id)
        merged.append(dict(field))
    return merged


def fetch_fields_with_cache(
    client: BrainClient,
    args: argparse.Namespace,
    run_paths: RunPaths,
    cached_fields: Sequence[Dict[str, Any]],
    cache_refresh_reason: str,
) -> List[Dict[str, Any]]:
    """根据缓存状态拉取字段；能补齐时补齐，必要时才覆盖刷新。
    Fetch fields based on cache state; append when possible and overwrite only when needed.
    """
    if not cache_refresh_reason:
        fields = list(cached_fields)
        print(f"[cache] loaded {len(fields)} fields from {run_paths.fields_cache_file}", flush=True)
        return fields

    print(f"[cache] refreshing fields cache: {cache_refresh_reason}", flush=True)
    append_to_cache = (
        bool(cached_fields)
        and not args.refresh_fields_cache
        and args.offset == 0
        and args.limit > len(cached_fields)
    )
    fetch_offset = len(cached_fields) if append_to_cache else args.offset
    fetch_limit = args.limit - len(cached_fields) if append_to_cache else args.limit
    if append_to_cache:
        print(
            f"[cache] extending cached fields from {len(cached_fields)} to {args.limit} using offset={fetch_offset} limit={fetch_limit}",
            flush=True,
        )

    # Fetching the field list is also wrapped so temporary API instability
    # does not abort the whole batch before it starts.
    fetched_fields = retry_operation(
        "fetch dataset fields",
        args.field_fetch_retries,
        lambda: client.fetch_dataset_fields(
            args.dataset_id,
            limit=fetch_limit,
            offset=fetch_offset,
            page_size=args.page_size,
            region=args.region,
            universe=args.universe,
            instrument_type=args.instrument_type,
            delay=args.delay,
        ),
        retry_wait_seconds=3.0,
    )
    fields = merge_fields_by_id(cached_fields, fetched_fields) if append_to_cache else fetched_fields
    save_fields_cache(
        run_paths.fields_cache_file,
        dataset_id=args.dataset_id,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
        fields=fields,
    )
    print(f"[cache] saved {len(fields)} fields to {run_paths.fields_cache_file}", flush=True)
    return fields


def build_settings_fingerprint(args: argparse.Namespace) -> str:
    """为当前模拟配置生成指纹，便于安全续跑与去重。
    Fingerprint the active simulation settings so reruns can resume safely.
    """
    return stable_fingerprint(
        {
            "dataset_id": args.dataset_id,
            "region": args.region,
            "universe": args.universe,
            "instrument_type": args.instrument_type,
            "delay": args.delay,
            "decay": args.decay,
            "neutralization": args.neutralization,
            "truncation": args.truncation,
            "nan_handling": args.nan_handling,
        }
    )


def build_settings_fingerprint_from_payload(payload: Dict[str, Any]) -> str:
    """为单个具体 settings 变体生成配置指纹。
    Fingerprint one concrete settings payload variant.
    """
    return stable_fingerprint(payload)


def wait_seconds(seconds: float, reason: str) -> None:
    """带日志地休眠，使退避与等待行为在输出中可见。
    Sleep with a log message so backoff decisions stay visible in stdout.
    """
    # Centralized sleep helper so every pause is visible in logs.
    seconds = max(seconds, 0.0)
    if seconds > 0:
        print(f"[wait] {reason}: sleeping {seconds:.1f}s", flush=True)
        time.sleep(seconds)


def extract_retry_after(headers: Dict[str, str], default: float = 5.0) -> float:
    """将 Retry-After 解析为秒数，失败时使用保守默认值。
    Parse Retry-After as seconds, falling back to a conservative default.
    """
    # Retry-After is not guaranteed to be present or numeric, so keep
    # a safe default for all rate-limit and async polling paths.
    value = headers.get("Retry-After")
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def doubled_retry_after(headers: Dict[str, str], default: float = 5.0) -> float:
    """将服务端给出的等待时间翻倍，采用更保守的退避窗口。
    Use a conservative backoff window by doubling the server hint.
    """
    # Be conservative when the API tells us to come back later; using 2x the
    # advised interval reduces repeated polling against slow backend queues.
    return extract_retry_after(headers, default=default) * 2.0


def polling_retry_after(headers: Dict[str, str], default: float = 5.0, buffer_seconds: float = 1.0) -> float:
    """按服务端 Retry-After 轮询异步任务，并添加小缓冲。
    Poll async jobs using the server Retry-After hint plus a small buffer.
    """
    # For simulation polling, the platform already tells us when to come back.
    # Add a small buffer for clock/network jitter without doubling queue time.
    return extract_retry_after(headers, default=default) + max(buffer_seconds, 0.0)


def first_non_empty(*values: Any) -> Optional[Any]:
    """从多个候选值中返回第一个非空值。
    Return the first non-empty candidate from inconsistent API payloads.
    """
    # The API is inconsistent across endpoints, so many parsers need
    # a "pick the first useful value" helper.
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def safe_json_bytes(content: bytes) -> Dict[str, Any]:
    """安全解码 JSON 字节内容，并保留可调试的原始文本回退。
    Decode JSON responses safely while preserving useful raw fallback text.
    """
    # Convert raw bytes into a dict whenever possible, but never let a
    # malformed body hide the original response text during debugging.
    try:
        data = json.loads(content.decode("utf-8"))
        if isinstance(data, dict):
            return data
        return {"data": data}
    except ValueError:
        return {"text": content.decode("utf-8", errors="replace")[:500]}


def simulation_payload_is_pending(payload: Dict[str, Any]) -> Tuple[bool, str, Any]:
    """从 simulation 响应体判断任务是否仍在等待。
    Decide from the simulation response body whether the job is still pending.
    """
    status = str(first_non_empty(payload.get("status"), payload.get("state"), "")).upper()
    progress = first_non_empty(payload.get("progress"), payload.get("stage"), "")
    return status in {"PENDING", "RUNNING", "QUEUED"}, status, progress


class BrainClient:
    """面向 WorldQuant Brain 认证与 Alpha 接口的轻量 HTTP 客户端。
    Small HTTP client for the WorldQuant Brain authentication and alpha APIs.
    """

    def __init__(
        self,
        email: str,
        password: str,
        min_request_interval: float = 0.0,
        rate_limit_max_retries: int = DEFAULT_RATE_LIMIT_MAX_RETRIES,
    ) -> None:
        """初始化客户端凭证、节流参数与 cookie/opener 状态。
        Initialize credentials, throttling settings, and cookie/opener state.
        """
        if not email or not password:
            raise BrainAPIError("Missing credentials. Set --email/--password or WQB_EMAIL/WQB_PASSWORD.")
        self.email = email
        self.password = password
        self.min_request_interval = max(min_request_interval, 0.0)
        self.rate_limit_max_retries = max(rate_limit_max_retries, 1)
        self.last_request_started_at = 0.0
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def login(self) -> None:
        """使用 basic auth 登录并初始化会话 cookie。
        Authenticate with basic auth and initialize the session cookie jar.
        """
        token = base64.b64encode(f"{self.email}:{self.password}".encode("utf-8")).decode("ascii")
        status, _, content = self.raw_request(
            "POST",
            AUTH_URL,
            headers={**DEFAULT_HEADERS, "Authorization": f"Basic {token}"},
            data=b"{}",
        )
        if status not in (200, 201):
            detail = safe_json_bytes(content)
            raise BrainAPIError(f"Login failed: {status} {detail}")
        print("[auth] login success", flush=True)

    def request(
        self,
        method: str,
        url: str,
        *,
        expected: Optional[Iterable[int]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: Optional[int] = None,
        **kwargs: Any,
    ) -> Tuple[int, Dict[str, str], bytes]:
        """发送带共享头、退避与重试策略的 HTTP 请求。
        Send an HTTP request with shared headers, backoff, and retry handling.
        """
        # Centralized HTTP wrapper:
        # - merges headers
        # - respects API rate-limit Retry-After
        # - retries transient server errors
        # - upgrades repeated 429s into a dedicated rate-limit exception
        merged_headers = dict(DEFAULT_HEADERS)
        if headers:
            merged_headers.update(headers)
        retries = self.rate_limit_max_retries if retries is None else max(retries, 1)

        last_response: Optional[Tuple[int, Dict[str, str], bytes]] = None
        for attempt in range(1, retries + 1):
            status, response_headers, content = self.raw_request(method, url, headers=merged_headers, **kwargs)
            last_response = (status, response_headers, content)
            if status == 429:
                print(
                    f"[rate-limit] {method} {url} attempt={attempt}/{retries} retry_after={response_headers.get('Retry-After')}",
                    flush=True,
                )
                wait_seconds(doubled_retry_after(response_headers, default=10.0), "rate limit")
                continue
            if status in (500, 502, 503, 504):
                wait_seconds(min(30.0, attempt * 3.0), f"server error {status}")
                continue
            if expected is None or status in expected:
                return status, response_headers, content
            break

        if last_response is None:
            raise BrainAPIError(f"No response from {method} {url}")
        status, response_headers, content = last_response
        if status == 429:
            retry_after = doubled_retry_after(response_headers, default=10.0)
            detail = safe_json_bytes(content)
            raise BrainRateLimitError(
                f"{method} {url} rate limited after {retries} attempts, skip current template: {detail}",
                retry_after,
            )
        detail = safe_json_bytes(content)
        raise BrainAPIError(f"{method} {url} failed: {status} {detail}")

    def raw_request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
    ) -> Tuple[int, Dict[str, str], bytes]:
        """执行一次不带高层重试策略的原始 HTTP 请求。
        Execute one raw HTTP request without high-level retry policy.
        """
        # Keep raw_request minimal so higher-level retry logic lives in request().
        if self.min_request_interval > 0:
            now = time.monotonic()
            elapsed = now - self.last_request_started_at
            remaining = self.min_request_interval - elapsed
            if remaining > 0:
                wait_seconds(remaining, "global request throttle")
            self.last_request_started_at = time.monotonic()
        if params:
            query = urlencode(params)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"

        request_data: Optional[bytes]
        if data is None:
            request_data = None
        elif isinstance(data, bytes):
            request_data = data
        else:
            request_data = str(data).encode("utf-8")

        request = Request(url=url, data=request_data, headers=headers or {}, method=method)
        try:
            with self.opener.open(request, timeout=90) as response:
                return response.getcode(), dict(response.headers.items()), response.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()
        except URLError as exc:
            raise BrainAPIError(f"{method} {url} failed: {exc}") from exc

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
    ) -> List[Dict[str, Any]]:
        """按分页拉取某个数据集的字段元数据。
        Fetch paginated field metadata for one dataset.
        """
        fields: List[Dict[str, Any]] = []
        current_offset = offset

        while True:
            batch_size = page_size
            if limit > 0:
                remaining = limit - len(fields)
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)

            # Pull one page at a time so a large dataset can be processed in batches.
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
            if len(batch) < batch_size:
                break
            if total is not None and current_offset >= total:
                break

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
    ) -> Dict[str, Any]:
        """获取一页字段元数据，并尝试几种已知可行的查询参数形态。
        Fetch one page of field metadata, trying a few known-good query variants.
        """
        last_error: Optional[Exception] = None

        # These query shapes are derived from the current frontend bundle:
        # - dataset.id is preserved in request query
        # - type=all is omitted
        # - common filters may include region/delay/universe/instrumentType
        # The API has been observed to reject some shapes with HTTP 400, so
        # we try a small set of plausible variants before failing.
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
            {
                "dataset.id": dataset_id,
                "limit": limit,
                "offset": offset,
            },
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
                print(f"[data] data-fields query accepted: {params}", flush=True)
                return safe_json_bytes(content)
            except BrainAPIError as exc:
                last_error = exc
                print(f"[data] data-fields query rejected: {params} -> {exc}", flush=True)

        raise BrainAPIError(f"Unable to fetch dataset fields for {dataset_id}: {last_error}")

    def create_simulation(self, payload: Dict[str, Any]) -> str:
        """创建模拟任务并返回后续轮询使用的 Location 地址。
        Create a simulation and return the Location URL used for polling.
        """
        # WorldQuant returns the newly created simulation through the Location header.
        _, response_headers, _ = self.request(
            "POST",
            SIMULATIONS_URL,
            data=json.dumps(payload),
            headers=SIM_ACCEPT_HEADER,
            expected={201},
        )
        location = response_headers.get("Location")
        if not location:
            raise BrainAPIError("Simulation created but Location header is missing.")
        return location

    def poll_simulation(
        self,
        location: str,
        *,
        max_polls: int,
        max_wait_seconds: float,
        max_pending_cycles: int,
        max_queue_seconds: float,
    ) -> Dict[str, Any]:
        """轮询单个模拟任务，直到完成或超出排队/等待预算。
        Poll one simulation until completion or until queue/wait budgets are exceeded.
        """
        url = location if location.startswith("http") else f"{API_BASE}{location}"
        poll_count = 0
        pending_cycles = 0
        started_at = time.monotonic()
        pending_started_at: Optional[float] = None
        while True:
            poll_count += 1
            if poll_count > max_polls:
                raise BrainAPIError(
                    f"Simulation polling exceeded max polls ({max_polls}) for {url}; skip current template."
                )
            if time.monotonic() - started_at > max_wait_seconds:
                raise BrainAPIError(
                    f"Simulation polling exceeded max wait ({max_wait_seconds:.1f}s) for {url}; skip current template."
                )
            # Parse the body first: some successful responses may still carry
            # Retry-After, and the body is the source of truth for completion.
            _, response_headers, content = self.request("GET", url, headers=SIM_ACCEPT_HEADER, expected={200, 202})
            payload = safe_json_bytes(content)
            is_pending, status, progress = simulation_payload_is_pending(payload)
            if is_pending:
                if pending_started_at is None:
                    pending_started_at = time.monotonic()
                pending_cycles += 1
                if pending_cycles > max_pending_cycles:
                    raise BrainQueueBusyError(
                        f"Simulation stayed queued too long ({pending_cycles} pending cycles) for {url}; skip current template."
                    )
                if max_queue_seconds > 0 and time.monotonic() - pending_started_at > max_queue_seconds:
                    raise BrainQueueBusyError(
                        f"Simulation exceeded queue budget ({max_queue_seconds:.0f}s) for {url}; skip current template."
                    )
                print(
                    f"[simulation-poll] pending simulation_location={url} status={status} progress={progress} "
                    f"retry_after={response_headers.get('Retry-After')}",
                    flush=True,
                )
                if response_headers.get("Retry-After"):
                    wait_seconds(polling_retry_after(response_headers, default=5.0), "simulation pending")
                else:
                    wait_seconds(3.0, f"simulation {status.lower()}")
                continue

            # Some API responses expose only Retry-After while omitting a clear
            # pending status. Treat those as pending only after confirming the
            # body did not already contain a completed simulation payload.
            if response_headers.get("Retry-After"):
                if pending_started_at is None:
                    pending_started_at = time.monotonic()
                pending_cycles += 1
                if pending_cycles > max_pending_cycles:
                    raise BrainQueueBusyError(
                        f"Simulation stayed queued too long ({pending_cycles} pending cycles) for {url}; skip current template."
                    )
                if max_queue_seconds > 0 and time.monotonic() - pending_started_at > max_queue_seconds:
                    raise BrainQueueBusyError(
                        f"Simulation exceeded queue budget ({max_queue_seconds:.0f}s) for {url}; skip current template."
                    )
                print(
                    f"[simulation-poll] pending simulation_location={url} retry_after={response_headers.get('Retry-After')}",
                    flush=True,
                )
                wait_seconds(polling_retry_after(response_headers, default=5.0), "simulation pending")
                continue
            return payload

    def get_alpha_detail(self, alpha_id: str) -> Dict[str, Any]:
        """获取 Alpha 详情，包括可用时的 check-submit 结果。
        Fetch alpha details, including check-submit results when available.
        """
        _, _, content = self.request("GET", f"{ALPHAS_URL}/{alpha_id}", headers=SIM_ACCEPT_HEADER, expected={200})
        return safe_json_bytes(content)

    def submit_alpha(self, alpha_id: str) -> Dict[str, Any]:
        """提交可提交的 Alpha，并在需要时跟随异步 Retry-After 轮询。
        Submit a submittable alpha, following async Retry-After polling if needed.
        """
        url = f"{ALPHAS_URL}/{alpha_id}/submit"
        method = "POST"

        while True:
            # Submission starts with POST and may continue as polling GET calls
            # if the platform answers with Retry-After.
            _, response_headers, content = self.request(method, url, headers=SIM_ACCEPT_HEADER, expected={200, 202})
            retry_after = response_headers.get("Retry-After")
            if retry_after:
                print(
                    f"[alpha-submit] pending alpha_id={alpha_id} method={method} retry_after={retry_after}",
                    flush=True,
                )
                wait_seconds(polling_retry_after(response_headers, default=5.0), "submission pending")
                method = "GET"
                continue
            return safe_json_bytes(content)


class WorkerClientFactory:
    """为每个工作线程提供独立且已认证的 BrainClient。
    Provide one authenticated BrainClient per worker thread.

    urllib opener/cookie state is not thread-safe enough to share across
    concurrent simulations, so each worker lazily creates and logs in its own
    client exactly once.
    """

    def __init__(self, args: argparse.Namespace, email: str, password: str) -> None:
        """记录线程级客户端创建所需的参数与凭证。
        Store args and credentials for thread-local client creation.
        """
        self.args = args
        self.email = email
        self.password = password
        self._local = threading.local()

    def get_client(self) -> BrainClient:
        """获取当前线程专属客户端，不存在时懒加载并登录。
        Get the current thread's client, creating and logging in lazily if needed.
        """
        client = getattr(self._local, "client", None)
        if client is not None:
            return client

        client = BrainClient(
            self.email,
            self.password,
            min_request_interval=self.args.min_request_interval,
            rate_limit_max_retries=self.args.rate_limit_max_retries,
        )
        login_with_retry(client, self.args.login_retries)
        self._local.client = client
        return client


def normalize_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从多种常见 API 返回结构中提取统一的列表结果。
    Extract a homogeneous list payload from several common API shapes.
    """
    # Different list endpoints use different container keys.
    for key in ("results", "items", "data", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    if isinstance(payload, list):
        return payload
    return []


def extract_total(payload: Dict[str, Any]) -> Optional[int]:
    """在接口提供时提取总数元数据。
    Extract total-count metadata when the endpoint exposes it.
    """
    # Preserve pagination support even if the API changes the total-count key.
    for key in ("count", "total", "total_count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return None


def choose_field_name(field: Dict[str, Any]) -> str:
    """从异构字段元数据中解析标准字段名或标识。
    Resolve the canonical field identifier/name from heterogeneous metadata.
    """
    # A field may expose its canonical name under different keys depending
    # on the source endpoint.
    return str(
        first_non_empty(
            field.get("id"),
            field.get("name"),
            field.get("mnemonic"),
            field.get("field"),
        )
    )


def choose_field_type(field: Dict[str, Any]) -> str:
    """将字段类型标准化为统一的大写标签，便于模板分发。
    Normalize a field type into one uppercase label for template routing.
    """
    # Normalize field type into one uppercase value so expression-building
    # logic stays simple.
    return str(
        first_non_empty(
            field.get("type"),
            field.get("fieldType"),
            field.get("category"),
            "UNKNOWN",
        )
    ).upper()


def tokenize_field_name(field_name: str) -> List[str]:
    """将字段名拆分为小写字母数字 token。
    Split a field name into lowercase alphanumeric tokens.
    """
    return [token for token in re.split(r"[^a-z0-9]+", field_name.lower()) if token]


def score_partner_candidate(field_name: str, partner_name: str) -> int:
    """启发式打分两个字段是否适合作为比值配对。
    Heuristically score whether two fields form a useful ratio pair.
    """
    if field_name == partner_name:
        return -10_000
    field_tokens = set(tokenize_field_name(field_name))
    partner_tokens = set(tokenize_field_name(partner_name))
    score = 0
    # Hard-code a few high-conviction ratio pairings so the search prefers
    # combinations already hinted by this account's submitted alpha history.
    preferred_partners = RATIO_PARTNER_CANDIDATES.get(field_name, ())
    if partner_name in preferred_partners:
        score += 180
        preferred_rank = preferred_partners.index(partner_name)
        score += max(0, 30 - preferred_rank * 5)
    if partner_name in RATIO_KEYWORDS.get(field_name, ()):
        score += 100
    if field_name in RATIO_KEYWORDS.get(partner_name, ()):
        score += 80
    if field_tokens & partner_tokens:
        score += 10 * len(field_tokens & partner_tokens)
    for token in field_tokens:
        if token and token in partner_name:
            score += 5
    if partner_name in {"assets", "equity", "debt", "liabilities", "cash", "enterprise_value", "cap"}:
        score += 15
    if partner_name in {"fnd6_mkvalt", "fnd6_mkvaltq", "liabilities_curr"}:
        score += 25
    return score


def discover_partner_fields(
    field_name: str,
    all_fields: Sequence[Dict[str, Any]],
    *,
    limit: int = 4,
    use_curated_heuristics: bool = True,
) -> List[str]:
    """为比值类模板扩展寻找可能合适的配对字段。
    Find likely companion fields for ratio-style template expansion.
    """
    if not use_curated_heuristics:
        return []

    candidates: List[Tuple[int, str]] = []
    available_by_name = {
        choose_field_name(item): item
        for item in all_fields
        if choose_field_type(item) == "MATRIX"
    }

    # Seed the candidate list with curated pairings first so extremely
    # important ratios like debt/cap are never crowded out by weaker matches.
    for partner_name in RATIO_PARTNER_CANDIDATES.get(field_name, ()):
        if partner_name == field_name or partner_name not in available_by_name:
            continue
        candidates.append((10_000 - len(candidates), partner_name))

    for item in all_fields:
        partner_name = choose_field_name(item)
        partner_type = choose_field_type(item)
        if partner_name == field_name or partner_type != "MATRIX":
            continue
        score = score_partner_candidate(field_name, partner_name)
        if score <= 0:
            continue
        candidates.append((score, partner_name))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    seen: set[str] = set()
    result: List[str] = []
    for _, partner_name in candidates:
        if partner_name in seen:
            continue
        seen.add(partner_name)
        result.append(partner_name)
        if len(result) >= limit:
            break
    return result


def sort_templates_by_priority(templates: Sequence[Tuple[str, str, int]]) -> List[Tuple[str, str, int]]:
    """按有效优先级从高到低排序候选模板。
    Sort candidate templates from highest to lowest effective priority.
    """
    # Higher-priority templates run first so likely winners are tested earlier.
    return sorted(templates, key=lambda item: (-item[2], item[0], item[1]))


def limit_templates(
    templates: List[Tuple[str, str, int]],
    max_templates_per_field: int,
) -> List[Tuple[str, str, int]]:
    """在排序与多样化之后应用字段级模板数量上限。
    Apply the field-level hard cap after ranking and diversification.
    """
    if max_templates_per_field <= 0:
        return templates
    return templates[:max_templates_per_field]


def classify_expression_family(template_name: str, expression: str) -> str:
    """将表达式归类到粗粒度家族，用于剪枝与排序。
    Map an expression into a coarse family used for pruning and ranking.
    """
    lower_name = template_name.lower()
    lower_expr = expression.lower()
    if "group_rank(ts_delta(rank(" in lower_expr:
        return "group_rank_delta"
    if "rank(ts_delta(rank(" in lower_expr:
        return "rank_delta"
    if lower_name in {"raw_field", "neg_raw_field", "rank_raw_field"}:
        return "legacy_level"
    if lower_name.startswith("raw_ratio_") or lower_name.startswith("ratio_") or lower_name.startswith("rank_ratio_"):
        return "legacy_ratio"
    if lower_name.startswith("neg_ratio_"):
        return "legacy_neg_ratio"
    if lower_name.startswith("group_rank_ratio_"):
        return "group_ratio_level"
    if lower_name.startswith("group_rank_") or "group_rank(" in lower_expr:
        if "ts_zscore" in lower_expr:
            return "group_zscore"
        if "ts_delta" in lower_expr and "ts_std_dev" in lower_expr:
            return "group_vol_scaled_delta"
        if "ts_mean" in lower_expr and "-" in lower_expr:
            return "group_mean_spread"
        return "legacy_group_level"
    if "ts_delta" in lower_expr and "ts_std_dev" in lower_expr:
        return "vol_scaled_delta"
    if "ts_mean" in lower_expr and "-" in lower_expr:
        return "mean_spread"
    if "ts_rank" in lower_expr and "-" in lower_expr:
        return "rank_spread"
    if "ts_zscore" in lower_expr:
        return "zscore_time"
    if "ts_decay_linear" in lower_expr and "ts_delta" in lower_expr:
        return "decayed_delta"
    if "/" in lower_expr and "ts_decay_linear" in lower_expr:
        return "decayed_ratio"
    if "ts_mean" in lower_expr and "/" in lower_expr:
        return "mean_ratio"
    prefix = lower_name.split("_", 1)[0]
    return prefix or "other"


def is_legacy_family(template_name: str, expression: str) -> bool:
    """判断模板是否属于历史上较易过度使用的 legacy 家族。
    Return whether a template belongs to historically overused legacy families.
    """
    return classify_expression_family(template_name, expression) in {
        "legacy_level",
        "legacy_group_level",
        "legacy_ratio",
        "legacy_neg_ratio",
        "group_ratio_level",
    }


def apply_similarity_penalty(
    templates: Sequence[Tuple[str, str, int]],
    legacy_similarity_penalty: int,
) -> List[Tuple[str, str, int]]:
    """对 legacy 形态模板施加相似度惩罚，让多样化候选优先运行。
    Demote legacy-shaped templates so diversified candidates run earlier.
    """
    penalized: List[Tuple[str, str, int]] = []
    for name, expression, priority in templates:
        family = classify_expression_family(name, expression)
        penalty = 0
        if family == "legacy_level":
            penalty = legacy_similarity_penalty
        elif family == "legacy_group_level":
            penalty = max(legacy_similarity_penalty - 6, 0)
        elif family == "legacy_ratio":
            penalty = max(legacy_similarity_penalty - 10, 0)
        elif family == "legacy_neg_ratio":
            penalty = max(legacy_similarity_penalty - 8, 0)
        elif family == "group_ratio_level":
            penalty = max(legacy_similarity_penalty - 14, 0)
        penalized.append((name, expression, priority - penalty))
    return penalized


def cap_templates_per_family(
    templates: Sequence[Tuple[str, str, int]],
    max_templates_per_family: int,
) -> List[Tuple[str, str, int]]:
    """限制每个结构家族仅保留前 N 个候选模板。
    Keep only the top-N candidates within each structural expression family.
    """
    if max_templates_per_family <= 0:
        return list(templates)
    kept: List[Tuple[str, str, int]] = []
    family_counts: Dict[str, int] = {}
    for name, expression, priority in templates:
        family = classify_expression_family(name, expression)
        used = family_counts.get(family, 0)
        if used >= max_templates_per_family:
            continue
        kept.append((name, expression, priority))
        family_counts[family] = used + 1
    return kept


def build_expression_candidates(
    field: Dict[str, Any],
    template_library: TemplateLibrary,
    max_templates_per_field: int,
    max_templates_per_family: int,
    legacy_similarity_penalty: int,
    all_fields: Optional[Sequence[Dict[str, Any]]] = None,
    field_feedback: Optional[Dict[str, Any]] = None,
    use_dataset_heuristics: bool = True,
) -> List[Tuple[str, str, int]]:
    """为单个字段构建、变异、多样化并排序表达式候选。
    Build, mutate, diversify, and rank expression candidates for one field.
    """
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    all_fields = all_fields or []

    # Template selection is now driven by an externalizable library so we can
    # expand or shrink search coverage between runs without changing code.
    raw_templates = template_library.get(field_type) or template_library.get("default", [])
    templates = [
        (
            str(item["name"]),
            str(item["expression"]).format(field=field_name),
            int(item.get("priority", 0)),
        )
        for item in raw_templates
        if isinstance(item, dict) and "name" in item and "expression" in item
    ]
    templates.extend(build_feedback_mutations(field_name, field_feedback))

    # Favor structural diversity over copying already-submitted shapes:
    # - de-emphasize raw level / simple group-rank / plain ratio expressions
    # - prioritize time-normalized, vol-scaled, and short-vs-long horizon spreads
    diversified_templates: List[Tuple[str, str, int]] = []
    legacy_templates: List[Tuple[str, str, int]] = []
    if field_type == "MATRIX":
        diversified_templates.extend(
            [
                (
                    "group_delta_over_std_subindustry_20_60",
                    f"group_rank(ts_delta(ts_backfill({field_name}, 120), 20) / ts_std_dev(ts_backfill({field_name}, 120), 60), subindustry)",
                    168,
                ),
                (
                    "group_short_long_mean_spread_subindustry_20_120",
                    f"group_rank(ts_mean(ts_backfill({field_name}, 120), 20) - ts_mean(ts_backfill({field_name}, 120), 120), subindustry)",
                    164,
                ),
                (
                    "group_zscore_subindustry_60",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, 120), 60), subindustry)",
                    161,
                ),
                (
                    "rank_mean_spread_over_std_20_120_60",
                    f"rank((ts_mean(ts_backfill({field_name}, 120), 20) - ts_mean(ts_backfill({field_name}, 120), 120)) / ts_std_dev(ts_backfill({field_name}, 120), 60))",
                    158,
                ),
                (
                    "rank_zscore_spread_20_120",
                    f"rank(ts_zscore(ts_backfill({field_name}, 120), 20) - ts_zscore(ts_backfill({field_name}, 120), 120))",
                    154,
                ),
                (
                    "group_rank_delta_of_rank_20",
                    f"group_rank(ts_delta(rank(ts_backfill({field_name}, 120)), 20), subindustry)",
                    150,
                ),
            ]
        )
        legacy_templates.extend(
            [
                ("raw_field", field_name, 145),
                ("group_rank_subindustry", f"group_rank({field_name}, subindustry)", 143),
                ("group_rank_industry", f"group_rank({field_name}, industry)", 141),
                ("rank_raw_field", f"rank({field_name})", 118),
            ]
        )
        if use_dataset_heuristics and field_name in POSITIVE_RAW_FIELDS:
            legacy_templates.append(("neg_raw_field", f"-{field_name}", 132))
        elif use_dataset_heuristics and field_name in NEGATIVE_RAW_FIELDS:
            legacy_templates.append(("neg_raw_field", f"-{field_name}", 144))
        elif use_dataset_heuristics:
            legacy_templates.append(("neg_raw_field", f"-{field_name}", 128))

        fields_by_name = {choose_field_name(item): item for item in all_fields}
        partner_names = discover_partner_fields(
            field_name,
            all_fields,
            limit=4,
            use_curated_heuristics=use_dataset_heuristics,
        )
        for partner in partner_names:
            if partner not in fields_by_name:
                continue
            diversified_templates.extend(
                [
                    (
                        f"group_ratio_delta_rank_3_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(rank(ts_backfill({field_name}/{partner}, 120)), 3), subindustry)",
                        188,
                    ),
                    (
                        f"group_ratio_delta_rank_5_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(rank(ts_backfill({field_name}/{partner}, 120)), 5), subindustry)",
                        184,
                    ),
                    (
                        f"group_ratio_delta_rank_10_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(rank(ts_backfill({field_name}/{partner}, 120)), 10), subindustry)",
                        176,
                    ),
                    (
                        f"group_ratio_delta_over_std_{field_name}_over_{partner}",
                        f"group_rank(ts_delta(ts_backfill({field_name}/{partner}, 120), 20) / ts_std_dev(ts_backfill({field_name}/{partner}, 120), 60), subindustry)",
                        172,
                    ),
                    (
                        f"group_ratio_zscore_{field_name}_over_{partner}",
                        f"group_rank(ts_zscore(ts_backfill({field_name}/{partner}, 120), 60), subindustry)",
                        160,
                    ),
                    (
                        f"ratio_mean_spread_over_std_{field_name}_over_{partner}",
                        f"rank((ts_mean(ts_backfill({field_name}/{partner}, 120), 20) - ts_mean(ts_backfill({field_name}/{partner}, 120), 120)) / ts_std_dev(ts_backfill({field_name}/{partner}, 120), 60))",
                        156,
                    ),
                    (
                        f"ratio_zscore_spread_{field_name}_over_{partner}",
                        f"rank(ts_zscore(ts_backfill({field_name}/{partner}, 120), 20) - ts_zscore(ts_backfill({field_name}/{partner}, 120), 120))",
                        152,
                    ),
                ]
            )
            legacy_templates.extend(
                [
                    (f"raw_ratio_{field_name}_over_{partner}", f"{field_name}/{partner}", 154),
                    (f"group_rank_ratio_{field_name}_over_{partner}", f"group_rank({field_name}/{partner}, subindustry)", 152),
                    (f"ratio_{field_name}_over_{partner}", f"rank({field_name}/{partner})", 148),
                    (f"rank_ratio_{field_name}_over_{partner}", f"rank({field_name}/{partner})", 138),
                    (
                        f"decay_ratio_{field_name}_over_{partner}",
                        f"rank(ts_decay_linear(ts_backfill({field_name}/{partner}, 120), 10))",
                        126,
                    ),
                ]
            )
            if use_dataset_heuristics and (field_name in NEGATIVE_RAW_FIELDS or partner in POSITIVE_RAW_FIELDS):
                legacy_templates.append(
                    (
                        f"neg_ratio_{field_name}_over_{partner}",
                        f"-({field_name}/{partner})",
                        148,
                    )
                )

    templates = diversified_templates + templates + legacy_templates

    # Lightweight adaptive expansion: for a few productive template families,
    # automatically add nearby windows so we can search local variants without
    # hand-authoring every single one in the JSON template library.
    adaptive_templates: List[Tuple[str, str, int]] = []
    for name, expression, priority in templates:
        adaptive_templates.append((name, expression, priority))
        if name.startswith("ts_mean_"):
            for extra_window in (10, 40, 80, 160):
                adaptive_templates.append(
                    (
                        f"ts_mean_{extra_window}",
                        f"rank(ts_mean({field_name}, {extra_window}))",
                        max(priority - 10, 0),
                    )
                )
        elif name.startswith("ts_rank_"):
            for extra_window in (20, 40, 80, 160):
                adaptive_templates.append(
                    (
                        f"ts_rank_{extra_window}",
                        f"rank(ts_rank({field_name}, {extra_window}))",
                        max(priority - 10, 0),
                    )
                )
        elif name.startswith("delta_"):
            for extra_window in (5, 10, 40, 80):
                adaptive_templates.append(
                    (
                        f"delta_{extra_window}",
                        f"rank(ts_delta({field_name}, {extra_window}))",
                        max(priority - 10, 0),
                    )
                )
        elif name.startswith("decay_"):
            for extra_window in (10, 30, 40, 60):
                adaptive_templates.append(
                    (
                        f"decay_{extra_window}",
                        f"rank(ts_decay_linear(ts_backfill({field_name}, 120), {extra_window}))",
                        max(priority - 10, 0),
                    )
                )
        elif name.startswith("stddev_"):
            for extra_window in (20, 40, 80, 120):
                adaptive_templates.append(
                    (
                        f"stddev_{extra_window}",
                        f"rank(ts_std_dev({field_name}, {extra_window}))",
                        max(priority - 10, 0),
                    )
                )

    deduped = apply_similarity_penalty(
        [(name, expression, priority) for name, expression, priority in adaptive_templates],
        legacy_similarity_penalty,
    )
    unique_by_expression = []
    seen_expressions: set[str] = set()
    for name, expression, priority in deduped:
        if expression in seen_expressions:
            continue
        seen_expressions.add(expression)
        unique_by_expression.append((name, expression, priority))
    filtered = [
        (name, expression, priority)
        for name, expression, priority in unique_by_expression
        if should_keep_template_for_feedback(name, expression, priority, field_feedback)
    ]
    prioritized = sort_templates_by_priority(filtered)
    diversified = cap_templates_per_family(prioritized, max_templates_per_family)
    return limit_templates(diversified, max_templates_per_field)


def load_existing_results(path: str) -> List[FieldTestResult]:
    """加载历史运行结果，以便续跑和复用反馈信息。
    Load prior run results so the script can resume and learn from history.
    """
    if not path or not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:  # noqa: BLE001
        raise BrainAPIError(f"Failed to read existing results file {path}: {exc}") from exc

    rows = payload.get("results")
    if not isinstance(rows, list):
        return []

    results: List[FieldTestResult] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            results.append(
                FieldTestResult(
                    field_id=str(row.get("field_id", "UNKNOWN")),
                    field_type=str(row.get("field_type", "UNKNOWN")),
                    field_name=str(row.get("field_name", "UNKNOWN")),
                    template_name=str(row.get("template_name", "")),
                    simulation_id=row.get("simulation_id"),
                    alpha_id=row.get("alpha_id"),
                    status=str(row.get("status", "unknown")),
                    submittable=row.get("submittable"),
                    submitted=bool(row.get("submitted", False)),
                    message=str(row.get("message", "")),
                    expression=str(row.get("expression", "")),
                    settings_fingerprint=str(row.get("settings_fingerprint", "")),
                    template_library_fingerprint=str(row.get("template_library_fingerprint", "")),
                    failed_stage=row.get("failed_stage"),
                    failed_checks=row.get("failed_checks"),
                )
            )
        except Exception:
            continue
    return results


def result_identity(result: FieldTestResult) -> Tuple[str, str, str, str]:
    """返回单次字段-模板-settings 尝试的稳定去重键。
    Return the stable dedupe key for one attempted field-template-settings combo.
    """
    return (
        result.field_id,
        result.template_name,
        result.expression,
        result.settings_fingerprint,
    )


def is_queue_timeout_result(result: FieldTestResult) -> bool:
    """判断结果是否只是平台队列超时，而非 Alpha 质量反馈。
    Return whether a result is only a platform queue timeout, not alpha-quality feedback.
    """
    message = str(result.message or "").lower()
    return result.failed_stage == "simulate" and (
        "queue budget" in message
        or "queued too long" in message
        or "stayed queued too long" in message
    )


def is_informative_result(result: FieldTestResult) -> bool:
    """判断结果是否应参与模板/字段质量学习。
    Return whether a result should be used for template/field quality learning.
    """
    return not is_queue_timeout_result(result)


def attempted_template_keys(results: Sequence[FieldTestResult]) -> set[Tuple[str, str, str, str]]:
    """收集已经持久化记录过的模板尝试键集合。
    Collect the set of template attempts already recorded on disk.
    """
    return {result_identity(result) for result in results if is_informative_result(result)}


def compile_template_stats(results: Sequence[FieldTestResult]) -> Dict[str, Dict[str, int]]:
    """按模板名聚合历史上的粗粒度统计信息。
    Aggregate coarse historical stats per template name.
    """
    stats: Dict[str, Dict[str, int]] = {}
    for result in results:
        stat = stats.setdefault(
            result.template_name,
            {
                "attempted": 0,
                "submittable": 0,
                "submitted": 0,
                "errors": 0,
                "simulated": 0,
                "queue_timeouts": 0,
                "low_sharpe": 0,
                "low_fitness": 0,
                "concentrated_weight": 0,
                "low_sub_universe_sharpe": 0,
            },
        )
        if is_queue_timeout_result(result):
            stat["queue_timeouts"] += 1
            continue
        stat["attempted"] += 1
        if result.submittable:
            stat["submittable"] += 1
        if result.submitted:
            stat["submitted"] += 1
        if result.status in {"simulated", "submitted"}:
            stat["simulated"] += 1
        if result.status == "error":
            stat["errors"] += 1
        failed_check_names = {str(check.get("name", "")) for check in result.failed_checks or []}
        if "LOW_SHARPE" in failed_check_names:
            stat["low_sharpe"] += 1
        if "LOW_FITNESS" in failed_check_names:
            stat["low_fitness"] += 1
        if "CONCENTRATED_WEIGHT" in failed_check_names:
            stat["concentrated_weight"] += 1
        if "LOW_SUB_UNIVERSE_SHARPE" in failed_check_names:
            stat["low_sub_universe_sharpe"] += 1
    return stats


def historical_template_priority_bonus(
    template_name: str,
    template_stats: Dict[str, Dict[str, int]],
) -> int:
    """为历史上模拟成功或通过检查的模板提供优先级奖励。
    Reward templates that previously simulated or passed checksubmit.
    """
    # Reuse past outcomes so templates that actually reached checksubmit move
    # ahead of families that have only burned time in the simulation queue.
    stat = template_stats.get(template_name)
    if not stat:
        return 0
    if stat["submittable"] > 0:
        return 200
    if stat["simulated"] > 0:
        bonus = 40 + min(stat["simulated"], 5) * 8
        if stat.get("submittable", 0) == 0 and stat.get("simulated", 0) >= 3:
            if stat.get("low_sharpe", 0) >= 3 and stat.get("low_fitness", 0) >= 3:
                bonus -= 90
            if stat.get("concentrated_weight", 0) >= 2:
                bonus -= 60
        return bonus
    if stat["errors"] >= 3 and stat["simulated"] == 0:
        return -20
    return 0


def compile_template_performance_summary(results: Sequence[FieldTestResult]) -> List[Dict[str, Any]]:
    """构建适合写入 JSON 的模板层表现汇总。
    Build a JSON-friendly summary of template-level performance.
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    for result in results:
        summary = grouped.setdefault(
            result.template_name,
            {
                "template_name": result.template_name,
                "attempted": 0,
                "submittable": 0,
                "submitted": 0,
                "errors": 0,
                "queue_timeouts": 0,
                "failed_check_counts": {},
            },
        )
        if is_queue_timeout_result(result):
            summary["queue_timeouts"] += 1
            continue
        summary["attempted"] += 1
        if result.submittable:
            summary["submittable"] += 1
        if result.submitted:
            summary["submitted"] += 1
        if result.status == "error":
            summary["errors"] += 1
        for check in result.failed_checks or []:
            name = str(check.get("name", "UNKNOWN"))
            summary["failed_check_counts"][name] = summary["failed_check_counts"].get(name, 0) + 1

    rows = list(grouped.values())
    for row in rows:
        counts = row["failed_check_counts"]
        row["top_failed_checks"] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    return sorted(rows, key=lambda row: (-row["submittable"], -row["submitted"], -row["attempted"], row["template_name"]))


def compile_field_performance_summary(results: Sequence[FieldTestResult]) -> List[Dict[str, Any]]:
    """构建适合写入 JSON 的字段层表现汇总。
    Build a JSON-friendly summary of field-level performance.
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    for result in results:
        summary = grouped.setdefault(
            result.field_id,
            {
                "field_id": result.field_id,
                "field_name": result.field_name,
                "field_type": result.field_type,
                "attempted_templates": 0,
                "submittable": 0,
                "submitted": 0,
                "errors": 0,
                "queue_timeouts": 0,
                "failed_check_counts": {},
            },
        )
        if is_queue_timeout_result(result):
            summary["queue_timeouts"] += 1
            continue
        summary["attempted_templates"] += 1
        if result.submittable:
            summary["submittable"] += 1
        if result.submitted:
            summary["submitted"] += 1
        if result.status == "error":
            summary["errors"] += 1
        for check in result.failed_checks or []:
            name = str(check.get("name", "UNKNOWN"))
            summary["failed_check_counts"][name] = summary["failed_check_counts"].get(name, 0) + 1

    rows = list(grouped.values())
    for row in rows:
        counts = row["failed_check_counts"]
        row["top_failed_checks"] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    return sorted(rows, key=lambda row: (-row["submittable"], -row["submitted"], -row["attempted_templates"], row["field_id"]))


def score_failed_checks(failed_checks: Optional[Sequence[Dict[str, Any]]]) -> float:
    """根据失败检查项估计一个 Alpha 距离可提交状态还有多近。
    Estimate how close a failed alpha was to submission based on its checks.
    """
    # Higher is better. We use this to prioritize fields/expressions that are
    # already close to passing instead of spending most of the queue budget on
    # obviously weak candidates.
    checks = list(failed_checks or [])
    if not checks:
        return -10.0

    score = 0.0
    counted = 0
    for check in checks:
        name = str(check.get("name", "UNKNOWN"))
        value = check.get("value")
        limit = check.get("limit")
        if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)):
            continue
        counted += 1
        if name.startswith("LOW_") and limit != 0:
            score += value / limit
        elif name == "CONCENTRATED_WEIGHT":
            score += max(0.0, 1.0 - ((value - limit) / max(abs(limit), 1e-9)))
    if counted == 0:
        return -10.0
    return score / counted


def failed_check_closeness(check: Dict[str, Any]) -> Optional[float]:
    """计算单个失败检查离通过阈值有多近，返回 0-1 左右的分数。
    Calculate how close one failed check is to its passing threshold.
    """
    name = str(check.get("name", "UNKNOWN"))
    value = check.get("value")
    limit = check.get("limit")
    if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)) or limit == 0:
        return None
    if name.startswith("LOW_"):
        return value / limit
    if value == 0:
        return None
    return limit / value


def failed_check_gap(check: Dict[str, Any]) -> Optional[float]:
    """计算失败检查到阈值的原始差距，正数表示还差多少。
    Calculate the raw gap to the threshold; positive means how much is missing.
    """
    name = str(check.get("name", "UNKNOWN"))
    value = check.get("value")
    limit = check.get("limit")
    if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)):
        return None
    if name.startswith("LOW_"):
        return limit - value
    return value - limit


def summarize_failed_check(check: Dict[str, Any]) -> Dict[str, Any]:
    """把失败检查转换成适合分析排序的紧凑结构。
    Convert one failed check into a compact structure suitable for analysis ranking.
    """
    return {
        "name": check.get("name"),
        "value": check.get("value"),
        "limit": check.get("limit"),
        "gap": failed_check_gap(check),
        "closeness": failed_check_closeness(check),
    }


def compile_failed_check_leaderboard(results: Sequence[FieldTestResult]) -> List[Dict[str, Any]]:
    """统计失败检查排行榜，帮助判断整体策略主要卡在哪里。
    Compile a failed-check leaderboard to show where the strategy is getting stuck.
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    for result in results:
        if is_queue_timeout_result(result):
            continue
        for check in result.failed_checks or []:
            name = str(check.get("name", "UNKNOWN"))
            row = grouped.setdefault(
                name,
                {
                    "name": name,
                    "count": 0,
                    "values": [],
                    "limits": [],
                    "gaps": [],
                    "closeness_scores": [],
                    "example_alpha_ids": [],
                },
            )
            row["count"] += 1
            value = check.get("value")
            limit = check.get("limit")
            gap = failed_check_gap(check)
            closeness = failed_check_closeness(check)
            if isinstance(value, (int, float)):
                row["values"].append(value)
            if isinstance(limit, (int, float)):
                row["limits"].append(limit)
            if gap is not None:
                row["gaps"].append(gap)
            if closeness is not None:
                row["closeness_scores"].append(closeness)
            if result.alpha_id and result.alpha_id not in row["example_alpha_ids"] and len(row["example_alpha_ids"]) < 5:
                row["example_alpha_ids"].append(result.alpha_id)

    leaderboard: List[Dict[str, Any]] = []
    for row in grouped.values():
        values = row.pop("values")
        limits = row.pop("limits")
        gaps = row.pop("gaps")
        closeness_scores = row.pop("closeness_scores")
        row["avg_value"] = sum(values) / len(values) if values else None
        row["avg_limit"] = sum(limits) / len(limits) if limits else None
        row["avg_gap"] = sum(gaps) / len(gaps) if gaps else None
        row["avg_closeness"] = sum(closeness_scores) / len(closeness_scores) if closeness_scores else None
        leaderboard.append(row)
    return sorted(leaderboard, key=lambda row: (-row["count"], -(row["avg_closeness"] or -999.0), row["name"]))


def compile_near_pass_summary(results: Sequence[FieldTestResult], limit: int = 20) -> List[Dict[str, Any]]:
    """列出最接近通过检查的 Alpha，用于指导下一轮变体搜索。
    List alphas closest to passing checks so the next run can focus mutations.
    """
    rows: List[Dict[str, Any]] = []
    for result in results:
        if result.status != "simulated" or result.submittable or not result.failed_checks:
            continue
        if is_queue_timeout_result(result):
            continue
        score = score_failed_checks(result.failed_checks)
        rows.append(
            {
                "score": score,
                "field_id": result.field_id,
                "field_name": result.field_name,
                "field_type": result.field_type,
                "template_name": result.template_name,
                "alpha_id": result.alpha_id,
                "expression": result.expression,
                "message": result.message,
                "failed_checks": [summarize_failed_check(check) for check in result.failed_checks or []],
            }
        )
    return sorted(rows, key=lambda row: (-row["score"], row["field_id"], row["template_name"]))[:limit]


def compile_optimization_hints(
    failed_check_leaderboard: Sequence[Dict[str, Any]],
    near_pass_summary: Sequence[Dict[str, Any]],
) -> List[str]:
    """根据失败分布生成下一轮搜索建议。
    Generate next-run search hints from the failed-check distribution.
    """
    dominant_names = {str(row.get("name")) for row in failed_check_leaderboard[:3]}
    hints: List[str] = []
    if not failed_check_leaderboard:
        return ["No failed checks recorded yet; run a wider exploration sample first."]
    if "LOW_SHARPE" in dominant_names or "LOW_SUB_UNIVERSE_SHARPE" in dominant_names:
        hints.append("Sharpe is the dominant blocker; prioritize group-neutralized, zscore/spread, and less raw level-like templates.")
    if "LOW_FITNESS" in dominant_names:
        hints.append("Fitness is weak; prioritize expressions that improve both Sharpe and turnover instead of only smoothing levels.")
    if "LOW_TURNOVER" in dominant_names:
        hints.append("Turnover is too low; try shorter delta windows, rank-then-delta variants, or lower decay.")
    if "HIGH_TURNOVER" in dominant_names:
        hints.append("Turnover is too high; try longer windows, higher decay, or smoother ts_mean/ts_decay structures.")
    if "CONCENTRATED_WEIGHT" in dominant_names:
        hints.append("Weight concentration is high; prefer group_rank/group_zscore variants and avoid raw ratios or sparse level signals.")
    if near_pass_summary:
        best = near_pass_summary[0]
        hints.append(
            f"Best near-pass candidate: field={best['field_id']} template={best['template_name']} score={best['score']:.3f}; prioritize local variants of this expression."
        )
    return hints


def compile_field_feedback(results: Sequence[FieldTestResult]) -> Dict[str, Dict[str, Any]]:
    """将历史接近通过的结果转为按字段组织的优化反馈。
    Convert historical near-pass results into per-field optimization hints.
    """
    feedback: Dict[str, Dict[str, Any]] = {}
    for result in results:
        summary = feedback.setdefault(
            result.field_id,
            {
                "field_name": result.field_name,
                "best_score": -999.0,
                "best_expression": "",
                "best_template_name": "",
                "failed_check_counts": {},
            },
        )
        for check in result.failed_checks or []:
            name = str(check.get("name", "UNKNOWN"))
            summary["failed_check_counts"][name] = summary["failed_check_counts"].get(name, 0) + 1
        if result.status != "simulated" or not result.failed_checks:
            continue
        score = score_failed_checks(result.failed_checks)
        if score > summary["best_score"]:
            summary["best_score"] = score
            summary["best_expression"] = result.expression
            summary["best_template_name"] = result.template_name
    return feedback


def field_priority(field_id: str, field_feedback: Dict[str, Dict[str, Any]]) -> float:
    """返回字段在续跑排序中使用的历史优先级分数。
    Return the historical priority score used to sort fields for reruns.
    """
    summary = field_feedback.get(field_id)
    if not summary:
        return -999.0
    return float(summary.get("best_score", -999.0))


def current_submittable_count(results: Sequence[FieldTestResult]) -> int:
    """统计当前结果集中已经可提交的 Alpha 数量。
    Count how many results in the current run are already submittable.
    """
    return sum(1 for result in results if result.submittable)


def build_historical_run_state(output_path: str, feedback_output_path: str) -> HistoricalRunState:
    """加载历史结果并构建续跑与反馈所需的状态对象。
    Load persisted results and derive resume/feedback state for the new run.
    """
    existing_results = load_existing_results(output_path)
    attempted_keys = attempted_template_keys(existing_results)
    template_stats = compile_template_stats(existing_results)
    feedback_results = existing_results if feedback_output_path == output_path else load_existing_results(feedback_output_path)
    field_feedback = compile_field_feedback(feedback_results)
    return HistoricalRunState(
        existing_results=existing_results,
        attempted_keys=attempted_keys,
        template_stats=template_stats,
        field_feedback=field_feedback,
    )


def choose_settings_variant_budget(field_feedback: Optional[Dict[str, Any]]) -> int:
    """根据字段历史反馈决定每个模板应该尝试多少个 settings 变体。
    Decide how many settings variants to try for a template based on field feedback.
    """
    if not field_feedback:
        return 1
    best_score = float(field_feedback.get("best_score", -999.0))
    if best_score >= 0.55:
        return 3
    if best_score >= 0.20:
        return 2
    return 1


def should_stop_after_submittable(args: argparse.Namespace, results: Sequence[FieldTestResult]) -> bool:
    """判断当前运行是否已达到要求的可提交数量上限。
    Return whether the run has already reached the requested submittable target.
    """
    return args.stop_after_submittable > 0 and current_submittable_count(results) >= args.stop_after_submittable


def is_template_disabled(
    template_name: str,
    template_stats: Dict[str, Dict[str, int]],
    disable_after: int,
) -> bool:
    """禁用历史尝试足够多但从未产生可提交结果的模板。
    Disable templates with enough history and zero submittable outcomes.
    """
    if disable_after <= 0:
        return False
    stat = template_stats.get(template_name)
    if not stat:
        return False
    if (
        stat.get("simulated", 0) >= 3
        and stat.get("submittable", 0) == 0
        and (
            ("mean_spread" in template_name and stat.get("low_sharpe", 0) >= 3 and stat.get("low_fitness", 0) >= 3)
            or stat.get("concentrated_weight", 0) >= 2
        )
    ):
        return True
    return stat["attempted"] >= disable_after and stat["submittable"] == 0


def is_legacy_family_disabled(
    template_name: str,
    expression: str,
    template_stats: Dict[str, Dict[str, int]],
    disable_after: int,
) -> bool:
    """当整个 legacy 家族消耗过多预算却没有收益时进行禁用。
    Disable the whole legacy family when it burns too much budget without wins.
    """
    if disable_after <= 0 or not is_legacy_family(template_name, expression):
        return False
    attempted = 0
    submittable = 0
    for prior_template_name, stat in template_stats.items():
        if not is_legacy_family(prior_template_name, ""):
            continue
        attempted += int(stat.get("attempted", 0))
        submittable += int(stat.get("submittable", 0))
    return attempted >= disable_after and submittable == 0


def invert_expression(expression: str) -> str:
    """对表达式取反，同时避免产生冗余双重负号。
    Invert an expression while avoiding redundant double negatives.
    """
    stripped = expression.strip()
    if stripped.startswith("-(") and stripped.endswith(")"):
        return stripped[2:-1]
    if stripped.startswith("-") and stripped.count("(") == stripped.count(")") == 0:
        return stripped[1:]
    return f"-({stripped})"


def build_feedback_mutations(
    field_name: str,
    field_feedback: Optional[Dict[str, Any]],
) -> List[Tuple[str, str, int]]:
    """基于历史失败检查结果生成额外的表达式变异候选。
    Generate extra candidate expressions informed by prior failed checks.
    """
    # Use failed-check feedback to bias the search toward higher-turnover,
    # less-concentrated, better-neutralized variants.
    mutations: List[Tuple[str, str, int]] = [
        (
            "iter_group_rank_delta_of_rank_3",
            f"group_rank(ts_delta(rank(ts_backfill({field_name}, 120)), 3), subindustry)",
            182,
        ),
        (
            "iter_group_rank_delta_of_rank_5",
            f"group_rank(ts_delta(rank(ts_backfill({field_name}, 120)), 5), subindustry)",
            180,
        ),
        (
            "iter_group_mean_spread_over_std_5_20_20",
            f"group_rank((ts_mean(ts_backfill({field_name}, 120), 5) - ts_mean(ts_backfill({field_name}, 120), 20)) / ts_std_dev(ts_backfill({field_name}, 120), 20), subindustry)",
            178,
        ),
        (
            "iter_rank_mean_spread_over_std_5_20_20",
            f"rank((ts_mean(ts_backfill({field_name}, 120), 5) - ts_mean(ts_backfill({field_name}, 120), 20)) / ts_std_dev(ts_backfill({field_name}, 120), 20))",
            176,
        ),
        (
            "iter_rank_zscore_spread_5_40",
            f"rank(ts_zscore(ts_backfill({field_name}, 120), 5) - ts_zscore(ts_backfill({field_name}, 120), 40))",
            174,
        ),
    ]

    if not field_feedback:
        return mutations

    failed_counts = field_feedback.get("failed_check_counts", {})
    dominant_names = {
        name
        for name, _ in sorted(failed_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    }
    best_expression = str(field_feedback.get("best_expression", "")).strip()
    best_score = float(field_feedback.get("best_score", -999.0))

    if best_score >= 0.15:
        mutations.extend(
            [
                (
                    "iter_nearpass_group_rank_delta_of_rank_10",
                    f"group_rank(ts_delta(rank(ts_backfill({field_name}, 120)), 10), subindustry)",
                    194,
                ),
                (
                    "iter_nearpass_group_rank_delta_of_rank_20",
                    f"group_rank(ts_delta(rank(ts_backfill({field_name}, 120)), 20), subindustry)",
                    190,
                ),
                (
                    "iter_nearpass_group_delta_zscore_5_60",
                    f"group_rank(ts_delta(ts_zscore(ts_backfill({field_name}, 120), 60), 5), subindustry)",
                    188,
                ),
                (
                    "iter_nearpass_group_delta_zscore_10_60",
                    f"group_rank(ts_delta(ts_zscore(ts_backfill({field_name}, 120), 60), 10), subindustry)",
                    186,
                ),
            ]
        )

    if "LOW_TURNOVER" in dominant_names:
        mutations.extend(
            [
                ("iter_rank_delta_3", f"rank(ts_delta(ts_backfill({field_name}, 120), 3))", 186),
                ("iter_rank_delta_5", f"rank(ts_delta(ts_backfill({field_name}, 120), 5))", 184),
                ("iter_rank_then_delta_3", f"rank(ts_delta(rank(ts_backfill({field_name}, 120)), 3))", 183),
            ]
        )

    if "LOW_SUB_UNIVERSE_SHARPE" in dominant_names or "CONCENTRATED_WEIGHT" in dominant_names:
        mutations.extend(
            [
                ("iter_group_zscore_20", f"group_rank(ts_zscore(ts_backfill({field_name}, 120), 20), subindustry)", 185),
                (
                    "iter_group_zscore_spread_5_20",
                    f"group_rank(ts_zscore(ts_backfill({field_name}, 120), 5) - ts_zscore(ts_backfill({field_name}, 120), 20), subindustry)",
                    183,
                ),
            ]
        )

    if best_expression:
        mutations.extend(
            [
                ("iter_flip_best", invert_expression(best_expression), 172),
                ("iter_group_flip_best", f"group_rank({invert_expression(best_expression)}, subindustry)", 174),
                ("iter_group_decay_best_5", f"group_rank(ts_decay_linear(ts_backfill({best_expression}, 120), 5), subindustry)", 170),
            ]
        )

    return mutations


def should_keep_template_for_feedback(
    template_name: str,
    expression: str,
    priority: int,
    field_feedback: Optional[Dict[str, Any]],
) -> bool:
    """在字段反馈足够后剪掉低信号、低价值的模板。
    Prune low-signal templates once enough field-specific feedback exists.
    """
    # Once we have evidence about a field, aggressively cut low-signal and
    # low-turnover structures so queue budget stays on templates that can
    # actually move Sharpe/fitness.
    if not field_feedback:
        return True

    dominant_counts = field_feedback.get("failed_check_counts", {})
    dominant_names = {
        name
        for name, _ in sorted(dominant_counts.items(), key=lambda item: (-item[1], item[0]))[:4]
    }
    family = classify_expression_family(template_name, expression)
    lower_name = template_name.lower()
    lower_expr = expression.lower()

    always_keep_families = {
        "group_rank_delta",
        "group_vol_scaled_delta",
        "group_mean_spread",
        "group_zscore",
        "vol_scaled_delta",
        "mean_spread",
        "zscore_time",
        "rank_delta",
        "decayed_delta",
        "rank_spread",
    }
    if family in always_keep_families:
        return True
    if lower_name.startswith("iter_"):
        return True

    # Historical results show these shapes are repeatedly too slow.
    if "LOW_TURNOVER" in dominant_names:
        if lower_name.startswith(("ts_mean_", "backfill_", "sum_", "stddev_")):
            return False
        if lower_name in {"zscore", "scale", "rank_raw", "raw_field", "rank_raw_field"}:
            return False
        if "ts_mean(" in lower_expr and "-" not in lower_expr and "/" not in lower_expr:
            return False
        if "ts_backfill(" in lower_expr and "ts_delta" not in lower_expr and "ts_zscore" not in lower_expr:
            return False

    # These shapes have repeatedly concentrated or broken sub-universe quality.
    if "LOW_SUB_UNIVERSE_SHARPE" in dominant_names or "CONCENTRATED_WEIGHT" in dominant_names:
        if family in {"legacy_level", "legacy_group_level", "legacy_ratio", "legacy_neg_ratio", "group_ratio_level"}:
            return False
        if lower_name.startswith(("raw_ratio_", "ratio_", "rank_ratio_", "group_rank_ratio_")):
            return False
        if lower_name in {"argmax_60", "argmin_60"}:
            return False

    # In focused mode, keep only reasonably strong candidates.
    return priority >= 120


def should_skip_field_template_family(
    field_name: str,
    template_name: str,
    expression: str,
    *,
    use_dataset_heuristics: bool,
) -> bool:
    """对已经证明偏弱的字段-模板家族组合做先验剪枝。
    Apply prior pruning to field-template-family combinations that already look weak.
    """
    if not use_dataset_heuristics:
        return False
    family = classify_expression_family(template_name, expression)
    weak_mean_spread_fields = {"assets", "assets_curr", "cash", "bookvalue_ps", "capex"}
    if field_name in weak_mean_spread_fields and family in {"group_mean_spread", "mean_spread", "rank_spread"}:
        return True
    if field_name in {"assets", "assets_curr"} and family in {"zscore_time", "group_zscore"}:
        return True
    return False


def build_simulation_payload(args: argparse.Namespace, expression: str) -> Dict[str, Any]:
    """为单个表达式构建完整的模拟请求体。
    Build the full simulation request body for one expression.
    """
    # Keep simulation settings centralized so all field tests are comparable.
    return {
        "type": "REGULAR",
        "settings": {
            "instrumentType": args.instrument_type,
            "region": args.region,
            "universe": args.universe,
            "delay": args.delay,
            "decay": args.decay,
            "neutralization": args.neutralization,
            "truncation": args.truncation,
            "pasteurization": "ON",
            "unitHandling": "VERIFY",
            "nanHandling": args.nan_handling,
            "maxTrade": "OFF",
            "maxPosition": "OFF",
            "language": "FASTEXPR",
            "visualization": False,
            "startDate": "2019-01-01",
            "endDate": "2023-12-31",
        },
        "regular": expression,
    }


def build_setting_variants(args: argparse.Namespace, template_name: str, expression: str) -> List[SettingsVariant]:
    """为一个表达式生成少量且多样化的 settings 变体。
    Produce a small diversified set of settings variants for one expression.
    """
    # Keep only a few settings variants per expression family.
    # The diversified templates below often work better with lower truncation
    # and time-normalized inputs than plain raw/ratio shapes do.
    base = build_simulation_payload(args, expression)["settings"]
    variants: List[SettingsVariant] = []

    def push_variant(**overrides: Any) -> None:
        merged = dict(base)
        merged.update(overrides)
        variants.append(merged)

    family = classify_expression_family(template_name, expression)

    if family in {"group_vol_scaled_delta", "group_mean_spread", "group_zscore"}:
        push_variant(decay=0, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=3, truncation=0.08, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=0, truncation=0.12, nanHandling="ON", neutralization="INDUSTRY")
    elif family in {"vol_scaled_delta", "mean_spread", "zscore_time", "rank_delta", "decayed_delta"}:
        push_variant(decay=0, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=5, truncation=0.08, nanHandling="OFF", neutralization="SUBINDUSTRY")
        push_variant(decay=0, truncation=0.12, nanHandling="ON", neutralization="INDUSTRY")
    elif family in {"group_ratio_level", "legacy_ratio"}:
        push_variant(decay=5, truncation=0.08, nanHandling="OFF", neutralization="SUBINDUSTRY")
        push_variant(decay=7, truncation=0.08, nanHandling="OFF", neutralization="SUBINDUSTRY")
        push_variant(decay=0, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
    elif family in {"legacy_level", "legacy_group_level"}:
        push_variant(decay=0, truncation=0.05, nanHandling="ON", neutralization="SUBINDUSTRY")
        push_variant(decay=5, truncation=0.08, nanHandling="OFF", neutralization="SUBINDUSTRY")
        push_variant(decay=0, truncation=0.12, nanHandling="ON", neutralization="INDUSTRY")
    else:
        push_variant()

    deduped: List[SettingsVariant] = []
    seen: set[str] = set()
    for variant in variants:
        fingerprint = build_settings_fingerprint_from_payload(variant)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(variant)
    return deduped


def extract_alpha_id(payload: Dict[str, Any]) -> Optional[str]:
    """从结构不稳定的模拟返回中提取 Alpha ID。
    Extract the alpha id from simulation payloads with unstable shapes.
    """
    # Simulation responses are not fully stable, so inspect several likely shapes.
    candidates = [
        payload.get("alpha"),
        payload.get("alphaId"),
        payload.get("id") if payload.get("type") == "ALPHA" else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
        if isinstance(candidate, dict):
            candidate_id = first_non_empty(candidate.get("id"), candidate.get("alpha"))
            if isinstance(candidate_id, str) and candidate_id:
                return candidate_id

    children = payload.get("children")
    if isinstance(children, list):
        for child in children:
            alpha_id = extract_alpha_id(child if isinstance(child, dict) else {})
            if alpha_id:
                return alpha_id

    location = payload.get("location")
    if isinstance(location, str):
        match = re.search(r"/alphas/([^/]+)", location)
        if match:
            return match.group(1)
    return None


def extract_checks(alpha_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从嵌套或顶层 Alpha 结构中提取 check-submit 检查项。
    Extract check-submit checks from either nested or top-level alpha payloads.
    """
    # Checks sometimes live under alpha.is.checks and sometimes at top level.
    is_section = alpha_payload.get("is")
    if isinstance(is_section, dict) and isinstance(is_section.get("checks"), list):
        return is_section["checks"]
    checks = alpha_payload.get("checks")
    if isinstance(checks, list):
        return checks
    return []


def extract_failed_checks(alpha_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """仅提取失败检查项，并转换为适合结果持久化的紧凑结构。
    Return only failed checks in a compact result-friendly structure.
    """
    failed_checks: List[Dict[str, Any]] = []
    for check in extract_checks(alpha_payload):
        if str(check.get("result", "")).upper() != "FAIL":
            continue
        failed_checks.append(
            {
                "name": check.get("name"),
                "result": check.get("result"),
                "value": check.get("value"),
                "limit": first_non_empty(check.get("limit"), check.get("threshold")),
            }
        )
    return failed_checks


def is_submittable_from_checks(checks: List[Dict[str, Any]]) -> Optional[bool]:
    """将检查项列表折叠为 True、False 或 None 三态结果。
    Collapse a list of checks into True, False, or None when unavailable.
    """
    if not checks:
        return None
    for check in checks:
        if str(check.get("result", "")).upper() == "FAIL":
            return False
    return True


def summarize_failure(payload: Dict[str, Any]) -> str:
    """将冗长的 API 失败负载压缩为简短的运维可读消息。
    Convert a verbose API failure payload into a short operator-facing message.
    """
    # Produce a short operator-friendly error string for JSON results and logs.
    detail = first_non_empty(payload.get("detail"), payload.get("message"), payload.get("error"))
    if detail:
        return str(detail)

    checks = extract_checks(payload)
    failed = [check for check in checks if str(check.get("result", "")).upper() == "FAIL"]
    if failed:
        names = ", ".join(str(check.get("name", "UNKNOWN")) for check in failed[:5])
        return f"failed checks: {names}"

    text = json.dumps(payload, ensure_ascii=False)[:300]
    return text or "unknown error"


def retry_operation(
    name: str,
    retries: int,
    func: Any,
    *,
    retry_wait_seconds: float = 2.0,
) -> Any:
    """以有限重试执行单个阶段，并特殊处理限流与排队拥塞。
    Run one stage with bounded retries and special handling for queue/rate limits.
    """
    # Generic stage wrapper used by login/simulate/check/submit:
    # - logs each failure
    # - respects explicit rate-limit retry windows
    # - fails only after the configured number of attempts
    last_error: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        try:
            return func()
        except BrainRateLimitError as exc:
            last_error = exc
            print(f"[retry] {name} rate limited on attempt {attempt}/{retries}: {exc}", flush=True)
            # Once an inner API call has already exhausted its own rate-limit
            # retries, skip the current template immediately instead of
            # re-running the whole stage again.
            break
        except BrainQueueBusyError as exc:
            last_error = exc
            print(f"[retry] {name} queue busy on attempt {attempt}/{retries}: {exc}", flush=True)
            # Queue congestion should also skip the current template immediately
            # so the main loop can reduce runtime concurrency and cool down.
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(f"[retry] {name} failed on attempt {attempt}/{retries}: {exc}", flush=True)
            if attempt < retries:
                wait_seconds(retry_wait_seconds, f"retry {name}")

    raise BrainAPIError(f"{name} failed after {retries} attempts: {last_error}")


def is_invalid_credentials_error(error: Exception) -> bool:
    """判断异常是否表示 Brain 登录凭据无效。
    Return whether an exception indicates invalid Brain login credentials.
    """
    return "INVALID_CREDENTIALS" in str(error) or "401" in str(error)


def login_with_retry(client: BrainClient, retries: int) -> None:
    """通过统一的重试封装完成客户端登录。
    Authenticate a client using the shared retry wrapper.
    """
    # Login is separated so callers can give it its own retry policy and a
    # clearer final message than the lower-level HTTP error.
    attempts = max(retries, 1)
    try:
        retry_operation("login", attempts, client.login, retry_wait_seconds=3.0)
    except BrainAPIError as exc:
        if is_invalid_credentials_error(exc):
            raise BrainAPIError(
                "登录失败：账号或密码无效，脚本已重试 "
                f"{attempts} 次并停止。请确认官网可以登录；如果本地保存的是错误凭据，"
                "请删除 worldquant_brain_credentials.json 和 "
                "worldquant_brain_credentials.key 后重新运行脚本输入账号密码。"
            ) from exc
        raise BrainAPIError(
            f"登录失败：脚本已重试 {attempts} 次并停止。最后一次错误：{exc}"
        ) from exc


def create_simulation_with_retry(client: BrainClient, payload: Dict[str, Any], retries: int) -> Tuple[str, str]:
    """创建模拟任务，并返回轮询地址与可读 simulation ID。
    Create a simulation and return both polling URL and readable simulation id.
    """
    # Wrap simulation creation because this is one of the most common stages
    # to hit temporary API-side issues or rate limits.
    simulation_location = retry_operation(
        "create simulation",
        retries,
        lambda: client.create_simulation(payload),
        retry_wait_seconds=3.0,
    )
    # Store a readable simulation id in results, but keep the full location for polling.
    simulation_id_match = re.search(r"/simulations/([^/]+)", simulation_location)
    simulation_id = simulation_id_match.group(1) if simulation_id_match else simulation_location
    print(
        f"[simulation] created simulation_id={simulation_id} location={simulation_location}",
        flush=True,
    )
    return simulation_location, simulation_id


def poll_simulation_with_retry(
    client: BrainClient,
    simulation_location: str,
    retries: int,
    *,
    max_polls: int,
    max_wait_seconds: float,
    max_pending_cycles: int,
    max_queue_seconds: float,
) -> Dict[str, Any]:
    """按独立的重试预算与排队限制轮询模拟任务。
    Poll a simulation with its own retry budget and queue limits.
    """
    # Keep polling retry policy separate from creation retry policy because
    # long-running jobs are normal here.
    return retry_operation(
        "poll simulation",
        retries,
        lambda: client.poll_simulation(
            simulation_location,
            max_polls=max_polls,
            max_wait_seconds=max_wait_seconds,
            max_pending_cycles=max_pending_cycles,
            max_queue_seconds=max_queue_seconds,
        ),
        retry_wait_seconds=3.0,
    )


def check_submit_with_retry(
    client: BrainClient,
    alpha_id: str,
    retries: int,
) -> Tuple[Optional[bool], str, List[Dict[str, Any]]]:
    """获取 Alpha 检查结果并转成可提交状态输出。
    Fetch alpha checks and convert them into submission readiness output.
    """
    # "Check submit" means reading alpha checks and converting them into
    # a simple submittable True/False/None outcome for the batch runner.
    alpha_detail = retry_operation(
        "check submit",
        retries,
        lambda: client.get_alpha_detail(alpha_id),
        retry_wait_seconds=3.0,
    )
    checks = extract_checks(alpha_detail)
    submittable = is_submittable_from_checks(checks)
    failed_checks = extract_failed_checks(alpha_detail)
    message = "checks unavailable" if submittable is None else "checks passed" if submittable else "checks failed"
    print(
        f"[alpha-check] alpha_id={alpha_id} submittable={submittable} message={message}",
        flush=True,
    )
    return submittable, message, failed_checks


def submit_alpha_with_retry(client: BrainClient, alpha_id: str, retries: int) -> str:
    """带重试地提交 Alpha，并返回紧凑状态消息。
    Submit an alpha with retries and return a compact status message.
    """
    # Submission is the final side-effecting stage, so keep its retry handling
    # explicit and separate from read-only checks.
    submit_result = retry_operation(
        "submit alpha",
        retries,
        lambda: client.submit_alpha(alpha_id),
        retry_wait_seconds=3.0,
    )
    if submit_result.get("status") == "failed":
        return summarize_failure(submit_result)
    return "submitted"


def build_failure_result(
    *,
    field_id: str,
    field_type: str,
    field_name: str,
    template_name: str,
    simulation_id: Optional[str],
    alpha_id: Optional[str],
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    failed_stage: str,
    message: str,
    status: str = "error",
    failed_checks: Optional[List[Dict[str, Any]]] = None,
) -> FieldTestResult:
    """构建标准化失败结果对象，简化后续落盘与统计逻辑。
    Create a normalized failure result so downstream persistence stays simple.
    """
    # Normalize stage failures so downstream result dumping stays simple.
    return FieldTestResult(
        field_id=field_id,
        field_type=field_type,
        field_name=field_name,
        template_name=template_name,
        simulation_id=simulation_id,
        alpha_id=alpha_id,
        status=status,
        submittable=False,
        submitted=False,
        message=message,
        expression=expression,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        failed_stage=failed_stage,
        failed_checks=failed_checks,
    )


def build_pending_templates_for_field(
    args: argparse.Namespace,
    field: Dict[str, Any],
    *,
    all_fields: Sequence[Dict[str, Any]],
    template_library: TemplateLibrary,
    field_feedback: Optional[Dict[str, Any]],
    include_templates: set[str],
    exclude_templates: set[str],
    template_stats: Dict[str, Dict[str, int]],
    attempted_keys: set[Tuple[str, str, str, str]],
    prior_results: Sequence[FieldTestResult],
    use_dataset_heuristics: bool,
) -> Tuple[List[Tuple[str, str, int, SettingsVariant, str]], int, int]:
    """为单个字段构建真正可执行的模板与 settings 队列。
    Build the runnable template/settings queue for one field.
    """
    field_id = str(first_non_empty(field.get("id"), "UNKNOWN"))
    field_name = choose_field_name(field)
    templates = build_expression_candidates(
        field,
        template_library,
        args.max_templates_per_field,
        args.max_templates_per_family,
        args.legacy_similarity_penalty,
        all_fields=all_fields,
        field_feedback=field_feedback,
        use_dataset_heuristics=use_dataset_heuristics,
    )
    pending_templates: List[Tuple[str, str, int, SettingsVariant, str]] = []
    disabled_templates = 0
    max_setting_variants = choose_settings_variant_budget(field_feedback)
    for template_name, expression, priority in templates:
        if include_templates and template_name not in include_templates:
            continue
        if template_name in exclude_templates:
            continue
        if should_skip_field_template_family(
            field_name,
            template_name,
            expression,
            use_dataset_heuristics=use_dataset_heuristics,
        ):
            disabled_templates += 1
            continue
        if is_template_disabled(template_name, template_stats, args.template_disable_after):
            disabled_templates += 1
            continue
        if is_legacy_family_disabled(
            template_name,
            expression,
            template_stats,
            args.disable_legacy_after,
        ):
            disabled_templates += 1
            continue
        if should_skip_expression_by_history(field_id, template_name, expression, prior_results):
            disabled_templates += 1
            continue
        effective_priority = priority + historical_template_priority_bonus(template_name, template_stats)
        for settings_variant in build_setting_variants(args, template_name, expression)[:max_setting_variants]:
            variant_fingerprint = build_settings_fingerprint_from_payload(settings_variant)
            if (field_id, template_name, expression, variant_fingerprint) in attempted_keys:
                continue
            pending_templates.append((template_name, expression, effective_priority, settings_variant, variant_fingerprint))
    pending_templates.sort(key=lambda item: (-item[2], item[0], item[1], item[4]))
    return pending_templates, disabled_templates, len(templates)


def should_skip_expression_by_history(
    field_id: str,
    template_name: str,
    expression: str,
    prior_results: Sequence[FieldTestResult],
) -> bool:
    """对历史上已明显偏弱的同字段同表达式，续跑时直接跳过剩余变体。
    Skip rerunning more variants when the same field-expression is already clearly weak.
    """
    for result in prior_results:
        if result.field_id != field_id or result.template_name != template_name or result.expression != expression:
            continue
        if result.submittable:
            return False
        failed_checks = result.failed_checks or []
        if not failed_checks:
            continue
        values = {str(check.get("name")): check.get("value") for check in failed_checks}
        low_sharpe = values.get("LOW_SHARPE")
        low_fitness = values.get("LOW_FITNESS")
        if isinstance(low_sharpe, (int, float)) and isinstance(low_fitness, (int, float)):
            if low_sharpe < 0.0 and low_fitness < 0.0:
                return True
        if "CONCENTRATED_WEIGHT" in values and "LOW_SUB_UNIVERSE_SHARPE" in values:
            return True
    return False


def should_skip_field(
    field_id: str,
    field_name: str,
    filters: RunFilters,
    skipped_fields_due_to_queue: set[str],
) -> bool:
    """判断某个字段是否应在生成模板前被直接跳过。
    Return whether a field should be skipped before template generation begins.
    """
    if field_id in skipped_fields_due_to_queue:
        print(f"[skip] field={field_id} skipped after repeated queue-busy simulations", flush=True)
        return True
    if filters.include_fields and field_id not in filters.include_fields and field_name not in filters.include_fields:
        print(f"[skip] field={field_id} excluded by include-fields filter", flush=True)
        return True
    if field_id in filters.exclude_fields or field_name in filters.exclude_fields:
        print(f"[skip] field={field_id} excluded by exclude-fields filter", flush=True)
        return True
    return False


def run_field_test(
    client: BrainClient,
    args: argparse.Namespace,
    field: Dict[str, Any],
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: Optional[SettingsVariant] = None,
    create_semaphore: Optional[threading.Semaphore] = None,
) -> FieldTestResult:
    """执行单个候选表达式的创建、轮询、检查与可选提交流程。
    Execute create, poll, checksubmit, and optional submit for one candidate.
    """
    # This function intentionally returns a result object for every field,
    # including stage failures, so the whole batch can continue end-to-end.
    field_id = str(first_non_empty(field.get("id"), "UNKNOWN"))
    field_name = str(first_non_empty(field.get("name"), field_id))
    field_type = choose_field_type(field)

    print(
        f"[field] testing {field_id} ({field_type}) template={template_name} expression: {expression}",
        flush=True,
    )

    try:
        payload = build_simulation_payload(args, expression)
        if simulation_settings is not None:
            payload["settings"] = dict(simulation_settings)
        # Stage 1: create a simulation job.
        if create_semaphore is not None:
            print(
                f"[simulation] waiting for create slot field={field_id} template={template_name}",
                flush=True,
            )
            create_semaphore.acquire()
        try:
            simulation_location, simulation_id = create_simulation_with_retry(
                client,
                payload,
                args.simulation_create_retries,
            )
        finally:
            if create_semaphore is not None:
                create_semaphore.release()
    except Exception as exc:  # noqa: BLE001
        return build_failure_result(
            field_id=field_id,
            field_type=field_type,
            field_name=field_name,
            template_name=template_name,
            simulation_id=None,
            alpha_id=None,
            expression=expression,
            settings_fingerprint=settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            failed_stage="simulate",
            message=str(exc),
        )

    try:
        # Stage 2: wait for the simulation to finish and resolve the alpha id.
        simulation_result = poll_simulation_with_retry(
            client,
            simulation_location,
            args.simulation_poll_retries,
            max_polls=args.simulation_max_polls,
            max_wait_seconds=args.simulation_max_wait_seconds,
            max_pending_cycles=args.simulation_max_pending_cycles,
            max_queue_seconds=args.simulation_max_queue_seconds,
        )
        progress = first_non_empty(
            simulation_result.get("progress"),
            simulation_result.get("status"),
            simulation_result.get("state"),
        )
        print(
            f"[simulation-poll] completed simulation_id={simulation_id} simulation_location={simulation_location} progress={progress}",
            flush=True,
        )
        alpha_id = extract_alpha_id(simulation_result)
        if not alpha_id:
            # If a simulation completes without a usable alpha id, treat it as
            # a simulation-stage failure rather than a check/submit failure.
            return build_failure_result(
                field_id=field_id,
                field_type=field_type,
                field_name=field_name,
                template_name=template_name,
                simulation_id=simulation_id,
                alpha_id=None,
                expression=expression,
                settings_fingerprint=settings_fingerprint,
                template_library_fingerprint=template_library_fingerprint,
                failed_stage="simulate",
                message=summarize_failure(simulation_result),
                status="simulation_failed",
            )
    except Exception as exc:  # noqa: BLE001
        return build_failure_result(
            field_id=field_id,
            field_type=field_type,
            field_name=field_name,
            template_name=template_name,
            simulation_id=simulation_id,
            alpha_id=None,
            expression=expression,
            settings_fingerprint=settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            failed_stage="simulate",
            message=str(exc),
        )

    try:
        # Stage 3: inspect platform checks to see whether submission is allowed.
        submittable, message, failed_checks = check_submit_with_retry(client, alpha_id, args.check_submit_retries)
    except Exception as exc:  # noqa: BLE001
        return build_failure_result(
            field_id=field_id,
            field_type=field_type,
            field_name=field_name,
            template_name=template_name,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
            expression=expression,
            settings_fingerprint=settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            failed_stage="checksubmit",
            message=str(exc),
        )

    submitted = False
    status = "simulated"

    if args.submit and submittable:
        try:
            # Stage 4: only submit when the caller asked for it and checks passed.
            print(
                f"[alpha-submit] eligible alpha_id={alpha_id} simulation_id={simulation_id} simulation_location={simulation_location}",
                flush=True,
            )
            message = submit_alpha_with_retry(client, alpha_id, args.submit_retries)
            submitted = True
            status = "submitted"
        except Exception as exc:  # noqa: BLE001
            return build_failure_result(
                field_id=field_id,
                field_type=field_type,
                field_name=field_name,
                template_name=template_name,
                simulation_id=simulation_id,
                alpha_id=alpha_id,
                expression=expression,
                settings_fingerprint=settings_fingerprint,
                template_library_fingerprint=template_library_fingerprint,
                failed_stage="submit",
                message=str(exc),
            )

    if submittable:
        print(
            f"[alpha-submit] submittable alpha_id={alpha_id} simulation_id={simulation_id} simulation_location={simulation_location}",
            flush=True,
        )

    return FieldTestResult(
        field_id=field_id,
        field_type=field_type,
        field_name=field_name,
        template_name=template_name,
        simulation_id=simulation_id,
        alpha_id=alpha_id,
        status=status,
        submittable=submittable,
        submitted=submitted,
        message=message,
        expression=expression,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        failed_checks=failed_checks,
    )


def run_field_test_in_worker(
    client_factory: WorkerClientFactory,
    args: argparse.Namespace,
    field: Dict[str, Any],
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: Optional[SettingsVariant] = None,
    create_semaphore: Optional[threading.Semaphore] = None,
) -> FieldTestResult:
    """工作线程入口，先解析线程本地客户端再执行测试。
    Worker entrypoint that resolves a thread-local client before testing.
    """
    # Each worker thread resolves its own authenticated client so concurrent
    # simulation/poll/check/submit calls do not share cookies or connection state.
    client = client_factory.get_client()
    return run_field_test(
        client,
        args,
        field,
        template_name,
        expression,
        settings_fingerprint,
        template_library_fingerprint,
        simulation_settings,
        create_semaphore,
    )


def dump_results(
    path: str,
    dataset_id: str,
    results: List[FieldTestResult],
    *,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: Optional[Dict[str, Any]] = None,
) -> None:
    """持久化完整运行结果，并写入一个统一分析文件。
    Persist the full run and one consolidated analysis file.
    """
    # Keep raw results in the main file for resume/dedupe, and keep analysis
    # in one companion file so the directory stays easy to understand.
    sidecar_paths = build_output_sidecar_paths(path)
    submittable_results = [result.__dict__ for result in results if result.submittable]
    submitted_results = [result.__dict__ for result in results if result.submitted]
    failed_checks_summary = [
        {
            "field_id": result.field_id,
            "template_name": result.template_name,
            "expression": result.expression,
            "failed_checks": result.failed_checks or [],
        }
        for result in results
        if result.failed_checks
    ]
    template_performance_summary = compile_template_performance_summary(results)
    field_performance_summary = compile_field_performance_summary(results)
    failed_check_leaderboard = compile_failed_check_leaderboard(results)
    near_pass_summary = compile_near_pass_summary(results)
    optimization_hints = compile_optimization_hints(failed_check_leaderboard, near_pass_summary)
    summary = {
        "dataset_id": dataset_id,
        "run_config": run_config or {},
        "settings_fingerprint": settings_fingerprint,
        "template_library_fingerprint": template_library_fingerprint,
        "tested": len(results),
        "unique_fields_tested": len({result.field_id for result in results}),
        "submittable": sum(1 for result in results if result.submittable),
        "submitted": sum(1 for result in results if result.submitted),
        "errors": sum(1 for result in results if result.status == "error"),
        "queue_timeouts": sum(1 for result in results if is_queue_timeout_result(result)),
        "results": [result.__dict__ for result in results],
    }
    analysis = {
        "dataset_id": dataset_id,
        "settings_fingerprint": settings_fingerprint,
        "template_library_fingerprint": template_library_fingerprint,
        "tested": summary["tested"],
        "unique_fields_tested": summary["unique_fields_tested"],
        "submittable_count": summary["submittable"],
        "submitted_count": summary["submitted"],
        "error_count": summary["errors"],
        "queue_timeout_count": summary["queue_timeouts"],
        "submittable": submittable_results,
        "submitted": submitted_results,
        "failed_checks_summary": failed_checks_summary,
        "failed_check_leaderboard": failed_check_leaderboard,
        "near_pass_summary": near_pass_summary,
        "optimization_hints": optimization_hints,
        "template_performance_summary": template_performance_summary,
        "field_performance_summary": field_performance_summary,
    }
    atomic_write_json(path, summary)
    atomic_write_json(sidecar_paths["analysis"], analysis)
    cleanup_legacy_sidecar_files(path)
    print(f"[done] wrote results to {path}", flush=True)
    print(f"[done] wrote analysis to {sidecar_paths['analysis']}", flush=True)


def ensure_analysis_synced(output_path: str) -> None:
    """确保 analysis 派生文件与主结果文件一致。
    Ensure the derived analysis file is synchronized from the main results file.
    """
    if not output_path or not os.path.exists(output_path):
        return
    sidecar_paths = build_output_sidecar_paths(output_path)
    try:
        with open(output_path, "r", encoding="utf-8") as handle:
            summary = json.load(handle)
    except Exception as exc:  # noqa: BLE001
        print(f"[analysis] skipped sync; failed to read main results: {exc}", flush=True)
        return

    should_rebuild = not os.path.exists(sidecar_paths["analysis"])
    if not should_rebuild:
        try:
            with open(sidecar_paths["analysis"], "r", encoding="utf-8") as handle:
                analysis = json.load(handle)
            should_rebuild = (
                analysis.get("tested") != summary.get("tested")
                or analysis.get("settings_fingerprint") != summary.get("settings_fingerprint")
                or analysis.get("template_library_fingerprint") != summary.get("template_library_fingerprint")
            )
        except Exception:
            should_rebuild = True

    if not should_rebuild:
        return

    results = load_existing_results(output_path)
    dump_results(
        output_path,
        str(summary.get("dataset_id", DEFAULT_DATASET_ID)),
        results,
        settings_fingerprint=str(summary.get("settings_fingerprint", "")),
        template_library_fingerprint=str(summary.get("template_library_fingerprint", "")),
        run_config=summary.get("run_config") if isinstance(summary.get("run_config"), dict) else {},
    )
    print(f"[analysis] rebuilt analysis from main results: {sidecar_paths['analysis']}", flush=True)


def handle_completed_future(
    future: Future[FieldTestResult],
    *,
    results: List[FieldTestResult],
    attempted_keys: set[Tuple[str, str, str, str]],
    template_stats: Dict[str, Dict[str, int]],
    args: argparse.Namespace,
    pending_contexts: Dict[Future[FieldTestResult], Dict[str, Any]],
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, int]], bool, Optional[str]]:
    """收尾一个 worker future，落盘结果并回传拥塞信号。
    Finalize one worker future, persist results, and report congestion signals.
    """
    context = pending_contexts.pop(future)
    field_id = context["field_id"]
    template_name = context["template_name"]

    try:
        result = future.result()
    except Exception as exc:  # noqa: BLE001
        # Workers should normally return a FieldTestResult even on API errors,
        # but keep a final defensive wrapper so one unexpected exception does
        # not stop the whole batch.
        result = build_failure_result(
            field_id=field_id,
            field_type=context["field_type"],
            field_name=context["field_name"],
            template_name=template_name,
            simulation_id=None,
            alpha_id=None,
            expression=context["expression"],
            settings_fingerprint=context["settings_fingerprint"],
            template_library_fingerprint=template_library_fingerprint,
            failed_stage="worker",
            message=str(exc),
        )

    results.append(result)
    if is_informative_result(result):
        attempted_keys.add(result_identity(result))
    template_stats = compile_template_stats(results)
    print(
        f"[result] field={result.field_id} template={result.template_name} status={result.status} "
        f"submittable={result.submittable} submitted={result.submitted} message={result.message}",
        flush=True,
    )
    dump_results(
        args.output,
        args.dataset_id,
        results,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
    )
    congestion_detected = False
    if "CONCURRENT_SIMULATION_LIMIT_EXCEEDED" in result.message:
        congestion_detected = True
    if isinstance(result.message, str) and "queued too long" in result.message.lower():
        congestion_detected = True
    if result.failed_stage == "simulate" and isinstance(result.message, str) and "rate limited" in result.message.lower():
        congestion_detected = True
    queue_busy_field_id = None
    if result.failed_stage == "simulate" and isinstance(result.message, str):
        lowered = result.message.lower()
        if "queued too long" in lowered or "queue budget" in lowered:
            queue_busy_field_id = result.field_id
    return template_stats, congestion_detected, queue_busy_field_id


def maybe_restore_runtime_concurrency(state: RuntimeConcurrencyState) -> None:
    """在拥塞冷却结束后恢复正常并发度。
    Restore normal worker concurrency after the congestion cooldown expires.
    """
    if state.cooldown_until and time.monotonic() >= state.cooldown_until and state.runtime_max_workers != state.max_workers:
        state.runtime_max_workers = state.max_workers
        state.cooldown_until = 0.0
        print(
            f"[cooldown] restored runtime concurrency to {state.runtime_max_workers}",
            flush=True,
        )


def register_queue_busy_field(
    field_id: Optional[str],
    args: argparse.Namespace,
    field_queue_busy_counts: Dict[str, int],
    skipped_fields_due_to_queue: set[str],
) -> None:
    """记录重复的排队拥塞字段，并在达到阈值后跳过该字段。
    Track repeated queue-busy failures and skip fields that keep stalling the queue.
    """
    if not field_id or args.field_queue_busy_skip_after <= 0:
        return
    field_queue_busy_counts[field_id] = field_queue_busy_counts.get(field_id, 0) + 1
    if field_queue_busy_counts[field_id] >= args.field_queue_busy_skip_after:
        skipped_fields_due_to_queue.add(field_id)
        print(
            f"[skip] field={field_id} hit queue-busy limit {field_queue_busy_counts[field_id]}/{args.field_queue_busy_skip_after}",
            flush=True,
        )


def apply_congestion_cooldown(args: argparse.Namespace, state: RuntimeConcurrencyState) -> None:
    """检测到拥塞后，临时切换到单 worker 运行模式。
    Temporarily force single-worker execution after queue congestion is observed.
    """
    state.runtime_max_workers = 1
    state.cooldown_until = time.monotonic() + max(args.queue_busy_cooldown_seconds, 0.0)
    print(
        f"[cooldown] detected queue congestion, runtime concurrency -> 1 for {args.queue_busy_cooldown_seconds:.0f}s",
        flush=True,
    )


def throttle_before_submission(args: argparse.Namespace, execution_state: ExecutionState) -> None:
    """在提交新任务前控制节奏，避免阻塞已完成任务处理。
    Pace new task submission without delaying completed-future handling.
    """
    if args.sleep_between_fields <= 0:
        return
    if execution_state.last_submission_at <= 0:
        return
    elapsed = time.monotonic() - execution_state.last_submission_at
    remaining = args.sleep_between_fields - elapsed
    if remaining > 0:
        wait_seconds(remaining, "before next template submission")


def drain_completed_futures(
    *,
    completed_futures: Sequence[Future[FieldTestResult]],
    execution_state: ExecutionState,
    args: argparse.Namespace,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: Optional[Dict[str, Any]],
    runtime_state: RuntimeConcurrencyState,
) -> Dict[str, Dict[str, int]]:
    """消费已完成的 future，落盘结果并更新队列退避状态。
    Consume finished futures, persist their results, and update queue backoff state.
    """
    for done_future in completed_futures:
        execution_state.template_stats, congestion_detected, queue_busy_field_id = handle_completed_future(
            done_future,
            results=execution_state.results,
            attempted_keys=execution_state.attempted_keys,
            template_stats=execution_state.template_stats,
            args=args,
            pending_contexts=execution_state.pending_futures,
            settings_fingerprint=settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            run_config=run_config,
        )
        register_queue_busy_field(
            queue_busy_field_id,
            args,
            execution_state.field_queue_busy_counts,
            execution_state.skipped_fields_due_to_queue,
        )
        if congestion_detected:
            apply_congestion_cooldown(args, runtime_state)
    return execution_state.template_stats


def print_dry_run_plan(
    *,
    args: argparse.Namespace,
    fields: Sequence[Dict[str, Any]],
    filters: RunFilters,
    template_library: TemplateLibrary,
    historical_state: HistoricalRunState,
    execution_state: ExecutionState,
    use_dataset_heuristics: bool,
    sample_limit: int = 20,
) -> None:
    """打印本轮计划执行的字段/模板，不创建任何 simulation。
    Print the planned field/template work without creating any simulations.
    """
    planned_fields = 0
    planned_templates = 0
    disabled_templates = 0
    samples: List[Dict[str, Any]] = []

    for field in fields:
        field_id = str(first_non_empty(field.get("id"), "UNKNOWN"))
        field_name = choose_field_name(field)
        if should_skip_field(field_id, field_name, filters, execution_state.skipped_fields_due_to_queue):
            continue
        pending_templates, disabled_count, template_count = build_pending_templates_for_field(
            args,
            field,
            all_fields=fields,
            template_library=template_library,
            field_feedback=historical_state.field_feedback.get(field_id),
            include_templates=filters.include_templates,
            exclude_templates=filters.exclude_templates,
            template_stats=execution_state.template_stats,
            attempted_keys=execution_state.attempted_keys,
            prior_results=execution_state.results,
            use_dataset_heuristics=use_dataset_heuristics,
        )
        if not pending_templates and template_count == 0:
            continue
        planned_fields += 1
        planned_templates += len(pending_templates)
        disabled_templates += disabled_count
        for template_name, expression, priority, _settings_variant, variant_fingerprint in pending_templates:
            if len(samples) >= sample_limit:
                break
            samples.append(
                {
                    "field_id": field_id,
                    "field_name": field_name,
                    "template_name": template_name,
                    "priority": priority,
                    "settings": variant_fingerprint,
                    "expression": expression,
                }
            )

    print("[dry-run] simulation creation is disabled; this is a plan only", flush=True)
    print(f"[dry-run] planned_fields={planned_fields}", flush=True)
    print(f"[dry-run] planned_simulations={planned_templates}", flush=True)
    print(f"[dry-run] disabled_templates={disabled_templates}", flush=True)
    print(f"[dry-run] existing_results={len(execution_state.results)}", flush=True)
    print(f"[dry-run] attempted_keys={len(execution_state.attempted_keys)}", flush=True)
    for index, sample in enumerate(samples, start=1):
        print(
            f"[dry-run] sample {index}/{len(samples)} field={sample['field_id']} "
            f"template={sample['template_name']} priority={sample['priority']} settings={sample['settings']} "
            f"expression={sample['expression']}",
            flush=True,
        )


def main() -> int:
    """编排凭证加载、字段发现、候选测试与结果持久化的主流程。
    Orchestrate credential loading, field discovery, candidate testing, and persistence.
    """
    # Main flow:
    # 1. load credentials
    # 2. authenticate
    # 3. fetch dataset fields
    # 4. simulate/check/submit each field-template candidate independently
    # 5. persist a JSON report for later inspection
    args = parse_args()
    run_paths = normalize_args_paths(args)
    cleanup_legacy_sidecar_files(run_paths.output, verbose=True)
    setup_runtime_logging(build_output_sidecar_paths(run_paths.output)["run_log"])
    ensure_analysis_synced(run_paths.output)
    run_config = build_run_config_snapshot(args, run_paths)
    print("[config] run config will be embedded in the main results file", flush=True)
    email, password = load_credentials(args)
    template_library = load_template_library(run_paths.template_library_file)
    filters = load_run_filters(run_paths)
    use_dataset_heuristics = use_fundamental6_heuristics(args.dataset_id)
    template_library_fingerprint = stable_fingerprint(template_library)
    settings_fingerprint = build_settings_fingerprint(args)
    feedback_output = run_paths.feedback_output or run_paths.output
    historical_state = build_historical_run_state(run_paths.output, feedback_output)
    bootstrap_client = BrainClient(
        email,
        password,
        min_request_interval=args.min_request_interval,
        rate_limit_max_retries=args.rate_limit_max_retries,
    )
    login_with_retry(bootstrap_client, args.login_retries)
    client_factory = WorkerClientFactory(args, email, password)

    cached_fields = load_fields_cache(
        run_paths.fields_cache_file,
        dataset_id=args.dataset_id,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
    )
    cache_refresh_reason = fields_cache_refresh_reason(
        cached_fields,
        requested_limit=args.limit,
        requested_offset=args.offset,
        force_refresh=args.refresh_fields_cache,
    )
    fields = fetch_fields_with_cache(
        bootstrap_client,
        args,
        run_paths,
        cached_fields,
        cache_refresh_reason,
    )
    if not fields:
        raise BrainAPIError(f"No fields returned for dataset {args.dataset_id}")

    fields.sort(
        key=lambda item: (
            -field_priority(str(first_non_empty(item.get("id"), "UNKNOWN")), historical_state.field_feedback),
            choose_field_name(item),
        )
    )
    if args.top_fields_by_feedback > 0:
        focused_fields = [
            field
            for field in fields
            if field_priority(str(first_non_empty(field.get("id"), "UNKNOWN")), historical_state.field_feedback) > -999.0
        ]
        fields = focused_fields[: args.top_fields_by_feedback]
        print(
            f"[focus] restricted run to top {len(fields)} fields ranked by prior feedback",
            flush=True,
        )

    print(f"[data] fetched {len(fields)} fields from dataset {args.dataset_id}", flush=True)

    if historical_state.existing_results:
        print(
            f"[resume] loaded {len(historical_state.existing_results)} existing results from {args.output}",
            flush=True,
        )

    execution_state = ExecutionState(
        results=list(historical_state.existing_results),
        attempted_keys=set(historical_state.attempted_keys),
        template_stats=dict(historical_state.template_stats),
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )
    max_workers = max(1, args.max_concurrent_simulations)
    runtime_state = RuntimeConcurrencyState(
        max_workers=max_workers,
        runtime_max_workers=max_workers,
    )
    max_create_workers = max(1, args.max_concurrent_creates)
    create_semaphore = threading.Semaphore(max_create_workers)
    print(f"[config] max_concurrent_simulations={max_workers}", flush=True)
    print(f"[config] max_concurrent_creates={max_create_workers}", flush=True)
    print(f"[config] simulation_max_pending_cycles={args.simulation_max_pending_cycles}", flush=True)

    if args.dry_run_plan:
        print_dry_run_plan(
            args=args,
            fields=fields,
            filters=filters,
            template_library=template_library,
            historical_state=historical_state,
            execution_state=execution_state,
            use_dataset_heuristics=use_dataset_heuristics,
        )
        return 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for field_index, field in enumerate(fields, start=1):
            if should_stop_after_submittable(args, execution_state.results):
                print(
                    f"[stop] reached stop-after-submittable={args.stop_after_submittable}",
                    flush=True,
                )
                break
            field_id = str(first_non_empty(field.get("id"), "UNKNOWN"))
            field_name = choose_field_name(field)
            field_type = choose_field_type(field)
            if should_skip_field(field_id, field_name, filters, execution_state.skipped_fields_due_to_queue):
                continue

            pending_templates, disabled_templates, template_count = build_pending_templates_for_field(
                args,
                field,
                all_fields=fields,
                template_library=template_library,
                field_feedback=historical_state.field_feedback.get(field_id),
                include_templates=filters.include_templates,
                exclude_templates=filters.exclude_templates,
                template_stats=execution_state.template_stats,
                attempted_keys=execution_state.attempted_keys,
                prior_results=execution_state.results,
                use_dataset_heuristics=use_dataset_heuristics,
            )
            print(
                f"[progress] field {field_index}/{len(fields)} field_id={field_id} "
                f"templates={template_count} pending={len(pending_templates)} disabled={disabled_templates}",
                flush=True,
            )

            for template_index, (template_name, expression, priority, settings_variant, variant_fingerprint) in enumerate(pending_templates, start=1):
                if should_stop_after_submittable(args, execution_state.results):
                    print(
                        f"[stop] reached stop-after-submittable={args.stop_after_submittable}",
                        flush=True,
                    )
                    break
                if field_id in execution_state.skipped_fields_due_to_queue:
                    print(f"[skip] field={field_id} stopping remaining templates after queue-busy limit", flush=True)
                    break
                maybe_restore_runtime_concurrency(runtime_state)

                while len(execution_state.pending_futures) >= runtime_state.runtime_max_workers:
                    done, _ = wait(set(execution_state.pending_futures), return_when=FIRST_COMPLETED)
                    drain_completed_futures(
                        completed_futures=list(done),
                        execution_state=execution_state,
                        args=args,
                        settings_fingerprint=settings_fingerprint,
                        template_library_fingerprint=template_library_fingerprint,
                        run_config=run_config,
                        runtime_state=runtime_state,
                    )
                    if field_id in execution_state.skipped_fields_due_to_queue:
                        break

                print(
                    f"[progress] field={field_id} template {template_index}/{len(pending_templates)} "
                    f"name={template_name} priority={priority} queued={len(execution_state.pending_futures) + 1}/{runtime_state.runtime_max_workers} "
                    f"settings={variant_fingerprint}",
                    flush=True,
                )
                throttle_before_submission(args, execution_state)
                future = executor.submit(
                    run_field_test_in_worker,
                    client_factory,
                    args,
                    field,
                    template_name,
                    expression,
                    variant_fingerprint,
                    template_library_fingerprint,
                    settings_variant,
                    create_semaphore,
                )
                execution_state.last_submission_at = time.monotonic()
                execution_state.pending_futures[future] = {
                    "field_id": field_id,
                    "field_name": field_name,
                    "field_type": field_type,
                    "template_name": template_name,
                    "expression": expression,
                    "settings_fingerprint": variant_fingerprint,
                }

        while execution_state.pending_futures:
            done, _ = wait(set(execution_state.pending_futures), return_when=FIRST_COMPLETED)
            drain_completed_futures(
                completed_futures=list(done),
                execution_state=execution_state,
                args=args,
                settings_fingerprint=settings_fingerprint,
                template_library_fingerprint=template_library_fingerprint,
                run_config=run_config,
                runtime_state=runtime_state,
            )

    # Completed futures are persisted as they finish, so avoid writing the
    # same result set again and duplicating the final [done] log lines.
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[abort] interrupted by user", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
