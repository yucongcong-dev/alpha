"""
API 客户端包

封装与 WorldQuant Brain API 的交互逻辑。

子模块：
    - client: BrainClient 与 WorkerClientFactory
    - session: 登录、底层 request、全局节流
    - fields: dataset 字段分页查询
    - simulations: simulation 创建与轮询
    - alphas: alpha 详情与提交
    - payloads: API payload 解析
    - timing: Retry-After 与等待策略
"""

from __future__ import annotations
