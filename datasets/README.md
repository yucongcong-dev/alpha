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
- 暂停的数据集不保留历史 preset，重新开启时按新的研究假设重新建立；唯一例外是明确
  标注为「仅复现」的历史 preset（当前为 `fundamental6` 的 `cicurr_refine` 与
  `cashflow_decorrelate`），须在该数据集 README 中说明用途，不代表现役提交策略。
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

当前所有数据集均已暂停，没有现役 preset。`option9` 的 `forward_curve_seed`
首轮（2026-08-13，`forward_price_90/270` 的 4 个候选）全部失败：Sharpe 0.15~0.55、
Fitness 0.03~0.12、权重集中度全部 FAIL，期限结构变体 Sub-universe Sharpe 0.12/-0.32；
该 preset 已随方向关闭删除，结论见
[option9 README](option9/README.md) 与 [research_history](option9/research_history.md)。
跨市场筛选仍受账号 Region 权限限制；此前 `news18` USA / TOP1000 / Delay 0 的四个
独立事件种子均已失败，不恢复该 D1/D0 新闻方向。

2026-08-07 的官网只读筛选还比较了 USA 的 TOP2000、TOP1000、TOP500、TOP200 和
TOPSP500。D1 均返回同一组 14 个数据集，D0 均返回同一组 11 个数据集；更换 Universe
只改变 Alpha/User Count，没有暴露新的经济信息源。不要因为小 Universe 下计数下降，
就把已失败的数据集重新解释为独立低拥挤方向。官方文档中的 `option6` 当前也未由账号接口
返回，因此不能建立不可运行的本地 preset。
