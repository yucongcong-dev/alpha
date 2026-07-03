"""
配置包兼容出口。

保留原有 `alpha.config` 导入面，内部实现按静态常量、策略构建、
YAML getter 等职责拆分到子模块。

所有常量现已统一从 YAML 文件读取 (config/constants_defaults.yaml 提供默认值，
config/settings.yaml 提供覆盖)。修改 YAML 后重启即可生效。
"""

from __future__ import annotations

from .constants import *
from .defaults import apply_yaml_global_defaults as apply_yaml_global_defaults
from .getters import *
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
    clear_yaml_caches as clear_yaml_caches,
)
from .yaml import get_yaml_config as get_yaml_config
from .yaml import (
    load_yaml_config as load_yaml_config,
)
from .yaml import (
    validate_yaml_config as validate_yaml_config,
)
from .runtime_values import (
    clear_runtime_config_cache as clear_runtime_config_cache,
)
from .runtime_values import (
    get_runtime_config as get_runtime_config,
)
from .runtime_values import (
    RuntimeConfig as RuntimeConfig,
)

# 统一配置管理器接口
from .unified_manager import (
    ConfigSource as ConfigSource,
    ConfigValue as ConfigValue,
    ConfigChangeEvent as ConfigChangeEvent,
    UnifiedConfigManager as UnifiedConfigManager,
    get_config_manager as get_config_manager,
    get_config as get_config,
    set_config as set_config,
    reload_config as reload_config,
)

from .schema import (
    ConfigType as ConfigType,
    ConfigField as ConfigField,
    ConfigSchema as ConfigSchema,
    AlphaConfigSchemaBuilder as AlphaConfigSchemaBuilder,
    APIConfig as APIConfig,
    SimulationConfig as SimulationConfig,
    QualityConfig as QualityConfig,
    OperationConfig as OperationConfig,
    RuntimeConfig as RuntimeConfig,
    FullConfig as FullConfig,
    validate_config_with_schema as validate_config_with_schema,
    get_default_config as get_default_config,
    describe_schema as describe_schema,
)
