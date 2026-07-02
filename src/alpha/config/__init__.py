"""
配置包兼容出口。

保留原有 `alpha.config` 导入面，内部实现按静态常量、策略构建、
YAML getter 等职责拆分到子模块。
"""

from __future__ import annotations

from .constants import *
from .defaults import apply_yaml_global_defaults as apply_yaml_global_defaults
from .getters import *
from .models import (
    DatasetExpressionPolicy,
    FeedbackLoopPolicy,
    FeedbackPhasePolicy,
    FieldTransformSpec,
    FieldTransformStage,
)
from .policy import (
    get_dataset_expression_policy,
    resolve_feedback_stage,
    use_fundamental6_heuristics,
)
from .profiles import (
    DATASET_PROFILES as DATASET_PROFILES,
    DEFAULT_PROFILE as DEFAULT_PROFILE,
    get_dataset_profile as get_dataset_profile,
)
from .yaml import (
    _config_file_signature as _config_file_signature,
    _resolve_yaml_path as _resolve_yaml_path,
    get_yaml_config,
    load_yaml_config as load_yaml_config,
)
