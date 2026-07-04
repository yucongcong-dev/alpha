"""
配置schema定义和验证工具
提供类型安全的配置访问和验证
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from .types import ConfigSource


class ConfigType(Enum):
    """配置类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    ENUM = "enum"
    PATH = "path"
    URL = "url"
    EMAIL = "email"
    DURATION = "duration"
    FILE_SIZE = "file_size"


@dataclass
class ConfigField:
    """配置字段定义"""
    name: str
    type: ConfigType
    description: str
    default: Any = None
    required: bool = False
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    enum_values: Optional[list[Any]] = None
    allowed_sources: Optional[list[ConfigSource]] = None
    deprecated: bool = False
    deprecated_message: Optional[str] = None

    def validate(self, value: Any, source: ConfigSource) -> list[str]:
        """验证字段值，返回错误信息列表"""
        errors = []

        # 检查来源权限
        if self.allowed_sources and source not in self.allowed_sources:
            errors.append(f"Field '{self.name}' cannot be set from source '{source.value}'")

        # 检查类型
        if self.type == ConfigType.STRING:
            if not isinstance(value, str):
                errors.append(f"Field '{self.name}' must be a string")
            else:
                if self.min_length is not None and len(value) < self.min_length:
                    errors.append(f"Field '{self.name}' must be at least {self.min_length} characters")
                if self.max_length is not None and len(value) > self.max_length:
                    errors.append(f"Field '{self.name}' must be at most {self.max_length} characters")
                if self.pattern is not None and not re.match(self.pattern, value):
                    errors.append(f"Field '{self.name}' must match pattern: {self.pattern}")

        elif self.type == ConfigType.INTEGER:
            if not isinstance(value, int):
                errors.append(f"Field '{self.name}' must be an integer")
            else:
                if self.min_value is not None and value < self.min_value:
                    errors.append(f"Field '{self.name}' must be >= {self.min_value}")
                if self.max_value is not None and value > self.max_value:
                    errors.append(f"Field '{self.name}' must be <= {self.max_value}")

        elif self.type == ConfigType.FLOAT:
            if not isinstance(value, (int, float)):
                errors.append(f"Field '{self.name}' must be a number")
            else:
                if self.min_value is not None and value < self.min_value:
                    errors.append(f"Field '{self.name}' must be >= {self.min_value}")
                if self.max_value is not None and value > self.max_value:
                    errors.append(f"Field '{self.name}' must be <= {self.max_value}")

        elif self.type == ConfigType.BOOLEAN:
            if not isinstance(value, bool):
                errors.append(f"Field '{self.name}' must be a boolean")

        elif self.type == ConfigType.LIST:
            if not isinstance(value, list):
                errors.append(f"Field '{self.name}' must be a list")
            else:
                if self.min_length is not None and len(value) < self.min_length:
                    errors.append(f"Field '{self.name}' must have at least {self.min_length} items")
                if self.max_length is not None and len(value) > self.max_length:
                    errors.append(f"Field '{self.name}' must have at most {self.max_length} items")

        elif self.type == ConfigType.DICT:
            if not isinstance(value, dict):
                errors.append(f"Field '{self.name}' must be a dictionary")

        elif self.type == ConfigType.ENUM:
            if self.enum_values is None:
                errors.append(f"Field '{self.name}' enum values not defined")
            elif value not in self.enum_values:
                errors.append(f"Field '{self.name}' must be one of {self.enum_values}")

        elif self.type == ConfigType.PATH:
            if not isinstance(value, str):
                errors.append(f"Field '{self.name}' must be a string path")

        elif self.type == ConfigType.URL:
            if not isinstance(value, str):
                errors.append(f"Field '{self.name}' must be a string")
            elif not re.match(r'^https?://', value):
                errors.append(f"Field '{self.name}' must be a valid URL starting with http:// or https://")

        elif self.type == ConfigType.EMAIL:
            if not isinstance(value, str):
                errors.append(f"Field '{self.name}' must be a string")
            elif not re.match(r'^[^@]+@[^@]+\.[^@]+$', value):
                errors.append(f"Field '{self.name}' must be a valid email address")

        elif self.type == ConfigType.DURATION:
            if not isinstance(value, (int, float)):
                errors.append(f"Field '{self.name}' must be a number")
            elif value <= 0:
                errors.append(f"Field '{self.name}' must be positive")

        elif self.type == ConfigType.FILE_SIZE:
            if not isinstance(value, (int, float)):
                errors.append(f"Field '{self.name}' must be a number")
            elif value < 0:
                errors.append(f"Field '{self.name}' must be non-negative")

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConfigField:
        """从字典创建字段定义"""
        return cls(
            name=data.get('name', ''),
            type=ConfigType(data.get('type', 'string')),
            description=data.get('description', ''),
            default=data.get('default'),
            required=data.get('required', False),
            min_value=data.get('min_value'),
            max_value=data.get('max_value'),
            min_length=data.get('min_length'),
            max_length=data.get('max_length'),
            pattern=data.get('pattern'),
            enum_values=data.get('enum_values'),
            allowed_sources=data.get('allowed_sources'),
            deprecated=data.get('deprecated', False),
            deprecated_message=data.get('deprecated_message'),
        )


class ConfigSchema:
    """配置schema定义"""

    def __init__(self):
        self.fields: dict[str, ConfigField] = {}
        self.nested_schemas: dict[str, ConfigSchema] = {}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConfigSchema:
        """从字典创建schema"""
        schema = cls()
        for value in data.values():
            if isinstance(value, dict) and 'type' in value:
                schema.add_field(ConfigField.from_dict(value))
        return schema

    def add_field(self, field: ConfigField) -> None:
        """添加字段定义"""
        self.fields[field.name] = field

    def add_nested_schema(self, name: str, schema: ConfigSchema) -> None:
        """添加嵌套schema"""
        self.nested_schemas[name] = schema

    def validate(self, config: dict[str, Any], source: ConfigSource, path: str = "") -> list[str]:
        """验证配置数据，返回错误信息列表"""
        errors = []

        for key, value in config.items():
            full_path = f"{path}.{key}" if path else key

            # 检查是否是嵌套schema
            if key in self.nested_schemas:
                if isinstance(value, dict):
                    nested_errors = self.nested_schemas[key].validate(value, source, full_path)
                    errors.extend(nested_errors)
                else:
                    errors.append(f"{full_path}: Expected dict for nested schema")
                continue

            # 检查字段定义
            if key not in self.fields:
                # 未知字段，发出警告但不报错
                print(f"Warning: Unknown config field '{full_path}' from source '{source.value}'")
                continue

            field = self.fields[key]

            # 检查是否已弃用
            if field.deprecated:
                msg = f"Field '{full_path}' is deprecated"
                if field.deprecated_message:
                    msg += f": {field.deprecated_message}"
                print(f"Warning: {msg}")

            # 验证字段值
            field_errors = field.validate(value, source)
            errors.extend(f"{full_path}: {error}" for error in field_errors)

        # 检查必填字段
        for field_name, field_def in self.fields.items():
            if field_def.required and field_name not in config:
                errors.append(f"Required field '{field_name}' is missing")

        return errors

    def get_default_config(self) -> dict[str, Any]:
        """获取默认配置"""
        config = {}

        for field_name, field_def in self.fields.items():
            if field_def.default is not None:
                config[field_name] = field_def.default

        for schema_name, schema in self.nested_schemas.items():
            config[schema_name] = schema.get_default_config()

        return config

    def describe(self) -> str:
        """生成schema描述文档"""
        lines = ["Configuration Schema:"]

        for field_name, field_def in sorted(self.fields.items()):
            lines.append(f"\n  {field_name}:")
            lines.append(f"    Type: {field_def.type.value}")
            lines.append(f"    Description: {field_def.description}")
            if field_def.default is not None:
                lines.append(f"    Default: {field_def.default}")
            lines.append(f"    Required: {field_def.required}")
            if field_def.deprecated:
                lines.append("    Deprecated: Yes")
                if field_def.deprecated_message:
                    lines.append(f"    Deprecation message: {field_def.deprecated_message}")

        for schema_name, schema in sorted(self.nested_schemas.items()):
            lines.append(f"\n  {schema_name} (nested):")
            nested_lines = schema.describe().split('\n')
            lines.extend(f"    {nested_line}" for nested_line in nested_lines[1:])

        return '\n'.join(lines)


# 预定义schema构建器
class AlphaConfigSchemaBuilder:
    """Alpha项目配置schema构建器"""

    @classmethod
    def build_api_schema(cls) -> ConfigSchema:
        """构建API配置schema"""
        schema = ConfigSchema()

        schema.add_field(ConfigField(
            name="base_url",
            type=ConfigType.URL,
            description="API基础URL",
            default="https://api.brain.worldquant.com",
            required=True
        ))

        schema.add_field(ConfigField(
            name="timeout",
            type=ConfigType.DURATION,
            description="API请求超时时间（秒）",
            default=30,
            min_value=1,
            max_value=300
        ))

        schema.add_field(ConfigField(
            name="max_retries",
            type=ConfigType.INTEGER,
            description="最大重试次数",
            default=3,
            min_value=0,
            max_value=10
        ))

        schema.add_field(ConfigField(
            name="retry_delay",
            type=ConfigType.DURATION,
            description="重试延迟时间（秒）",
            default=1.0,
            min_value=0.1,
            max_value=10.0
        ))

        return schema

    @classmethod
    def build_simulation_schema(cls) -> ConfigSchema:
        """构建模拟配置schema"""
        schema = ConfigSchema()

        schema.add_field(ConfigField(
            name="language",
            type=ConfigType.STRING,
            description="模拟语言",
            default="python",
            enum_values=["python", "matlab", "r"]
        ))

        schema.add_field(ConfigField(
            name="universe",
            type=ConfigType.STRING,
            description="模拟宇宙",
            default="TOP3000",
            enum_values=["TOP3000", "TOP2000", "TOP1000", "TOP500"]
        ))

        schema.add_field(ConfigField(
            name="neutralization",
            type=ConfigType.STRING,
            description="中性化方法",
            default="SUBINDUSTRY",
            enum_values=["SUBINDUSTRY", "INDUSTRY", "COUNTRY", "SECTOR", "NONE"]
        ))

        schema.add_field(ConfigField(
            name="delay",
            type=ConfigType.INTEGER,
            description="延迟天数",
            default=1,
            min_value=0,
            max_value=10
        ))

        return schema

    @classmethod
    def build_quality_schema(cls) -> ConfigSchema:
        """构建质量配置schema"""
        schema = ConfigSchema()

        schema.add_field(ConfigField(
            name="min_sharpe",
            type=ConfigType.FLOAT,
            description="最小Sharpe比率",
            default=1.0,
            min_value=0.0,
            max_value=10.0
        ))

        schema.add_field(ConfigField(
            name="min_fitness",
            type=ConfigType.FLOAT,
            description="最小适应度分数",
            default=0.5,
            min_value=0.0,
            max_value=1.0
        ))

        schema.add_field(ConfigField(
            name="max_turnover",
            type=ConfigType.FLOAT,
            description="最大换手率",
            default=0.5,
            min_value=0.0,
            max_value=1.0
        ))

        schema.add_field(ConfigField(
            name="max_weight",
            type=ConfigType.FLOAT,
            description="最大权重限制",
            default=0.1,
            min_value=0.0,
            max_value=1.0
        ))

        return schema

    @classmethod
    def build_operation_schema(cls) -> ConfigSchema:
        """构建运维配置schema"""
        schema = ConfigSchema()

        schema.add_field(ConfigField(
            name="concurrent_jobs",
            type=ConfigType.INTEGER,
            description="并发作业数",
            default=4,
            min_value=1,
            max_value=32
        ))

        schema.add_field(ConfigField(
            name="batch_size",
            type=ConfigType.INTEGER,
            description="批处理大小",
            default=10,
            min_value=1,
            max_value=100
        ))

        schema.add_field(ConfigField(
            name="checkpoint_interval",
            type=ConfigType.INTEGER,
            description="检查点间隔（秒）",
            default=300,
            min_value=60,
            max_value=3600
        ))

        schema.add_field(ConfigField(
            name="max_runtime_hours",
            type=ConfigType.FLOAT,
            description="最大运行时间（小时）",
            default=24.0,
            min_value=0.1,
            max_value=168.0  # 7天
        ))

        return schema

    @classmethod
    def build_full_schema(cls) -> ConfigSchema:
        """构建完整配置schema"""
        schema = ConfigSchema()

        # API配置
        api_schema = cls.build_api_schema()
        schema.add_nested_schema("api", api_schema)

        # 模拟配置
        simulation_schema = cls.build_simulation_schema()
        schema.add_nested_schema("simulation", simulation_schema)

        # 质量配置
        quality_schema = cls.build_quality_schema()
        schema.add_nested_schema("quality", quality_schema)

        # 运维配置
        operation_schema = cls.build_operation_schema()
        schema.add_nested_schema("operation", operation_schema)

        # 运行时开关
        schema.add_field(ConfigField(
            name="submit_enabled",
            type=ConfigType.BOOLEAN,
            description="是否启用提交",
            default=False
        ))

        schema.add_field(ConfigField(
            name="smoke_test",
            type=ConfigType.BOOLEAN,
            description="是否运行冒烟测试",
            default=False
        ))

        schema.add_field(ConfigField(
            name="full_run",
            type=ConfigType.BOOLEAN,
            description="是否运行完整测试",
            default=True
        ))

        schema.add_field(ConfigField(
            name="debug_mode",
            type=ConfigType.BOOLEAN,
            description="是否启用调试模式",
            default=False
        ))

        schema.add_field(ConfigField(
            name="log_level",
            type=ConfigType.STRING,
            description="日志级别",
            default="INFO",
            enum_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        ))

        return schema


# Pydantic模型用于类型安全的配置访问
class APIConfig(BaseModel):
    """API配置模型"""
    model_config = ConfigDict(extra="forbid")
    base_url: str = Field(default="https://api.brain.worldquant.com")
    timeout: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.1, le=10.0)


class SimulationConfig(BaseModel):
    """模拟配置模型"""
    model_config = ConfigDict(extra="forbid")
    language: Literal["python", "matlab", "r"] = "python"
    universe: Literal["TOP3000", "TOP2000", "TOP1000", "TOP500"] = "TOP3000"
    neutralization: Literal["SUBINDUSTRY", "INDUSTRY", "COUNTRY", "SECTOR", "NONE"] = "SUBINDUSTRY"
    delay: int = Field(default=1, ge=0, le=10)


class QualityConfig(BaseModel):
    """质量配置模型"""
    model_config = ConfigDict(extra="forbid")
    min_sharpe: float = Field(default=1.0, ge=0.0, le=10.0)
    min_fitness: float = Field(default=0.5, ge=0.0, le=1.0)
    max_turnover: float = Field(default=0.5, ge=0.0, le=1.0)
    max_weight: float = Field(default=0.1, ge=0.0, le=1.0)


class OperationConfig(BaseModel):
    """运维配置模型"""
    model_config = ConfigDict(extra="forbid")
    concurrent_jobs: int = Field(default=4, ge=1, le=32)
    batch_size: int = Field(default=10, ge=1, le=100)
    checkpoint_interval: int = Field(default=300, ge=60, le=3600)
    max_runtime_hours: float = Field(default=24.0, ge=0.1, le=168.0)


class RuntimeConfig(BaseModel):
    """运行时配置模型"""
    model_config = ConfigDict(extra="forbid")
    submit_enabled: bool = False
    smoke_test: bool = False
    full_run: bool = True
    debug_mode: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


class FullConfig(BaseModel):
    """完整配置模型"""
    api: APIConfig = Field(default_factory=APIConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    operation: OperationConfig = Field(default_factory=OperationConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FullConfig:
        """从字典创建配置模型"""
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return self.dict()


def validate_config_with_schema(config: dict[str, Any]) -> list[str]:
    """使用schema验证配置"""
    schema = AlphaConfigSchemaBuilder.build_full_schema()
    return schema.validate(config, ConfigSource.SETTINGS)


def get_default_config() -> dict[str, Any]:
    """获取默认配置"""
    schema = AlphaConfigSchemaBuilder.build_full_schema()
    return schema.get_default_config()


def describe_schema() -> str:
    """获取schema描述"""
    schema = AlphaConfigSchemaBuilder.build_full_schema()
    return schema.describe()
