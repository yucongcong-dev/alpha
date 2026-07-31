增大 Decay 参数值

当日（T）数据，并在当日收盘前完成交易

组内向量值之和为 0（多空均衡）

权重绝对值之和为 1

这个表达式有 3 个语法/类型问题：

1. vec_avg(close) 不合法
原因：
vec_avg 只能用于 Vector 类型字段，而 close 是 Matrix 字段，不能对 close 使用 vec_avg。

2. group_zscore(vec_avg(close), 10) 不合法
原因：
group_zscore 的第二个参数应该是分组变量/分组字段，例如 sector、industry、subindustry，而不是数字 10。

3. ts_backfill(..., .01) 不合法
原因：
ts_backfill 的第二个参数应是回看天数（整数，如 10、60），不是小数 .01。

如何改正：
如果你想对普通价格字段做分组标准化再回填，可以写成：
ts_backfill(group_zscore(close, sector), 10)

如果你本来想处理的是 Vector 字段，那么应该先把 close 换成真正的 Vector 字段，再写成类似：
ts_backfill(group_zscore(vec_avg(vector_field), sector), 10)

总结：
- close 是 Matrix，不能配 vec_avg
- group_zscore 的第二个参数要用 group 字段
- ts_backfill 的窗口参数要用整数天数


search、sort、submit（查找、排序、可提交）
在 BRAIN 中，Decay 是一个用于平滑信号、降低换手的模拟参数，通常取非负整数；常见合法取值是 0 到 15。

它对换手的影响：
- Decay 越小，组合越快跟随当天信号变化，换手通常越高。
- Decay 越大，组合会更多参考过去几天的信号，持仓变化更慢，换手通常越低。

怎么理解：
Decay 本质上是在做时间上的平滑。它不会改变 Alpha 的核心逻辑，但会改变调仓速度。

过大时的副作用：
- 信号会变钝、变慢
- 可能错过短期机会
- Returns 和 Sharpe 可能被拖弱
- 容易把原本有效的短周期 Alpha 过度平滑

实战上怎么用：
- 高换手 Alpha 往往可以适当增加 Decay 来改善 Turnover 和 Fitness
- 但不能一味调大，因为过大的 Decay 会稀释信号强度
- 所以 Decay 需要在“降低换手”和“保留信号敏感度”之间做平衡

BRAIN 中的自相关性（Self-correlation）是用来衡量你当前 Alpha 与你自己之前已提交、且符合 OS 测试资格的 Alpha 在表现或行为上有多相似的指标。

它衡量什么：
它主要衡量 Alpha 的“重复度”或“相似度”，帮助判断这个 Alpha 是否只是你历史研究的轻微变体，而不是一个真正新的想法。自相关性越高，通常说明它和你以前的 Alpha 越像，多样性越差。

如何理解和使用：
在回测结果页或 Alpha 页面中，可以展开 Self-correlation 相关信息，平台会列出最多 5 个与你当前 Alpha 最相近的、你已提交过的 Alpha 的统计数据。这个功能的目的，是帮助你检查自己的研究是否足够多样化。

提交时如何用：
提交前应该主动查看自相关性。
- 如果自相关性很高，说明这个 Alpha 很可能只是旧 Alpha 的重复或小改版，提交价值较低。
- 如果自相关性较低，说明它和你已有研究区分度更高，更值得保留或提交。

实战上，自相关性不是看收益强弱，而是看“新不新”。所以提交前除了看 Sharpe、Fitness、Turnover，还要看 Self-correlation，避免把很多本质相同的 Alpha 重复提交。


Igor Tulchinsky，2007 年
在 BRAIN 中，Sharpe 是 IR（Information Ratio，信息比率）的年化版本。

计算方式：
IR = mean(PnL) / stdev(PnL)
Sharpe = sqrt(252) × IR ≈ 15.8 × IR

其中：
- PnL 是每日盈亏（美元口径）
- mean(PnL) 是每日平均盈亏
- stdev(PnL) 是每日盈亏的标准差
- 252 代表美国市场一年平均交易日数量

它衡量什么：
Sharpe 衡量的是 Alpha 的风险调整后收益和收益一致性。Sharpe 越高，说明 Alpha 不只是赚钱，而且赚钱更稳定、更持续。相比单纯高 Returns，BRAIN 更看重高 Sharpe。


