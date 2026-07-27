# Dataset 工作区

每个数据集拥有独立的研究资产与运行产物：

```text
datasets/<dataset_id>/
├── README.md              # 数据集策略与研究结论
├── templates/             # template.json 与 refine 模板包
├── blacklist.json         # 数据集专属学习黑名单
├── profiles/              # 人工维护的字段、模板筛选清单
├── cache/fields/          # 按市场上下文生成的字段缓存（不进仓）
└── runs/<run_name>/       # summary、journal、分析、日志与恢复状态（不进仓）
```

约定：

- 可复用、需要审阅的策略资产放在 `templates/`、`blacklist.json`、`profiles/`。
- API 字段缓存只放在 `cache/fields/<market_scope>/fields.json`。
- 每次运行使用独立的 `runs/<run_name>/`，不要让多个实验共享同一组 sidecar。
- `alpha clean` 只清理 `cache/` 和 `runs/`，不会删除数据集策略资产。
