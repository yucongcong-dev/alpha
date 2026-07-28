"""文件系统路径常量。

来源: config/constants_defaults.yaml 的 paths.* 段。
"""

from __future__ import annotations

from ._constants_core import _yaml_str

CREDENTIALS_DIR: str = _yaml_str("paths", "credentials_dir", default=".credentials")
DATASETS_DIR: str = _yaml_str("paths", "datasets_dir", default="datasets")
CREDENTIALS_FILENAME: str = _yaml_str(
    "paths", "credentials_filename", default="worldquant_brain_credentials.json"
)
CREDENTIALS_KEY_FILENAME: str = _yaml_str(
    "paths", "credentials_key_filename", default="worldquant_brain_credentials.key"
)
ANALYSIS_SUFFIX: str = _yaml_str("paths", "analysis_suffix", default="_analysis.json")
RESULTS_JOURNAL_SUFFIX: str = _yaml_str("paths", "results_journal_suffix", default="_results.jsonl")
STATE_SUFFIX: str = _yaml_str("paths", "state_suffix", default="_state.json")
