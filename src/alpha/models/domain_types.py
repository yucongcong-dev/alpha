"""Dynamic domain payload aliases.

This module centralizes the JSON-like payload shapes that are shared across
analysis, reporting, and persistence code. Keeping them out of ``domain.py``
helps the core domain objects focus on dataclasses and behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

FieldFeedbackSummary = dict[str, Any]
"""单个字段的历史反馈画像。"""

ResultRow = dict[str, Any]
"""结果落盘 / 分析阶段使用的通用行对象。"""

TemplateMetadata = Mapping[str, object]
"""模板候选或字段视图附带的只读元数据视图。"""

FieldFeedbackMap = dict[str, FieldFeedbackSummary]
"""按字段 ID 聚合的反馈画像映射。"""

AnalysisInputs = dict[str, list[ResultRow]]
"""analysis sidecar 构建前的中间聚合输入。"""

SummaryPayload = dict[str, Any]
"""主结果文件 summary payload。"""

AnalysisPayload = dict[str, Any]
"""analysis sidecar payload。"""
