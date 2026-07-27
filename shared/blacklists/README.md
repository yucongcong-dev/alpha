# 跨数据集黑名单规则

- `default_rules.json`：所有数据集共享的默认表达式规避规则。
- 数据集学习得到的黑名单不放在这里，而是放在
  `datasets/<dataset_id>/blacklists/blacklist.json`。

共享规则需要保持通用；只对单一数据集成立的经验应留在该数据集目录内。
