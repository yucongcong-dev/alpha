# Dataset 工作区

每个数据集拥有独立的研究资产与运行产物：

```text
datasets/<dataset_id>/
├── README.md              # 数据集策略与研究结论
├── template.json          # 默认模板库
├── blacklist.json         # 数据集专属学习黑名单
├── presets/               # 可选；只保留仍在使用的专项策略入口
├── cache/                 # <market_scope>.json 字段缓存（不进仓）
├── feedback/              # <market_scope>/ 跨 run 聚合反馈、journal 与 run 索引（不进仓）
└── runs/<run_name>/       # summary、journal、分析、日志与恢复状态（不进仓）
```

约定：

- 可复用、需要审阅的策略资产放在 `template.json`、`presets/` 和 `blacklist.json`。
- 每个 preset 以研究目的命名，并按需包含 `template.json`、`fields.txt`、`templates.txt`。
- `fields.txt` 和 `templates.txt` 支持以 `#` 开头的说明行，空行和重复项会自动忽略。
- API 字段缓存只放在 `cache/<market_scope>.json`。
- 跨 run 反馈只在相同 `<market_scope>` 内聚合，避免不同 universe、region 或 delay 相互污染。
- 每次运行使用独立的 `runs/<run_name>/`，不要让多个实验共享同一组 sidecar。
- 实验结论写入数据集 README 后，可以删除对应 `runs/`；运行目录不是长期知识资产。
- 暂停的数据集不保留历史 preset，重新开启时按新的研究假设重新建立。
- `alpha clean` 只清理 `cache/` 和 `runs/`，不会删除数据集策略资产。

当前状态：

| 数据集 | 状态 | 现役 preset |
| --- | --- | --- |
| `analyst4` | 暂停 | 无 |
| `fundamental2` | 暂停 | 无 |
| `fundamental6` | 暂停 | 无 |
| `option8` | 基线保留 | `subindustry_refine` |
| `model16` | 暂停 | 无 |
| `model51` | 暂停 | 无 |
| `socialmedia12` | 暂停 | 无 |
| `socialmedia8` | 暂停 | 无 |
| `pv13` | 暂停 | 无 |
| `news12` | 暂停 | 无 |
| `option9` | 暂停 | 无 |
| `news18` | 暂停 | 无 |

当前没有现役 explore 数据集。`news12` 的新闻价格反应与首发新闻新颖度两个方向
均未形成可继续优化的基线；完整依据见其 `research_history.md`。下一轮应筛选新数据集，
不恢复已失败方向，也不扫描完整字段池。
