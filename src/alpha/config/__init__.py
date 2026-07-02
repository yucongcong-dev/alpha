"""
配置包兼容出口。

保留原有 `alpha.config` 导入面，内部实现按静态常量、策略构建、
YAML getter 等职责拆分到子模块。
"""

from __future__ import annotations

from .constants import *  # noqa: F403 - compatibility export surface
from .defaults import apply_yaml_global_defaults as apply_yaml_global_defaults
from .getters import *  # noqa: F403 - compatibility export surface
from .models import (
    DatasetExpressionPolicy as DatasetExpressionPolicy,
)
from .models import (
    FeedbackLoopPolicy as FeedbackLoopPolicy,
)
from .models import (
    FeedbackPhasePolicy as FeedbackPhasePolicy,
)
from .models import (
    FieldTransformSpec as FieldTransformSpec,
)
from .models import (
    FieldTransformStage as FieldTransformStage,
)
from .policy import (
    get_dataset_expression_policy as get_dataset_expression_policy,
)
from .policy import (
    resolve_feedback_stage as resolve_feedback_stage,
)
from .policy import (
    use_curated_heuristics_for_dataset as use_curated_heuristics_for_dataset,
)
from .policy import (
    use_fundamental6_heuristics as use_fundamental6_heuristics,  # deprecated backward-compat alias
)
from .profiles import (
    DATASET_PROFILES as DATASET_PROFILES,
)
from .profiles import (
    DEFAULT_PROFILE as DEFAULT_PROFILE,
)
from .profiles import (
    get_dataset_profile as get_dataset_profile,
)
from .yaml import (
    _config_file_signature as _config_file_signature,
)
from .yaml import (
    _resolve_yaml_path as _resolve_yaml_path,
)
from .yaml import get_yaml_config as get_yaml_config
from .yaml import (
    load_yaml_config as load_yaml_config,
)
