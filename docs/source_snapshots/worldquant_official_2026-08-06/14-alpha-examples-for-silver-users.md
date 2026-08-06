# ⭐ Alpha Examples for Silver Users🥈

Official URL: https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas
API Source: https://api.worldquantbrain.com/tutorial-pages/example-expression-alphas
Captured: 2026-08-06
Official source: WorldQuant BRAIN rendered Learn page via Chrome
Capture method: rendered_website
Section: Examples
Last modified: None

## Metadata
```json
{
  "id": "example-expression-alphas",
  "tutorial": "examples",
  "tutorial_title": "Examples",
  "title": "⭐ Alpha Examples for Silver Users🥈",
  "url": "https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas",
  "lastModified": null,
  "duration": null,
  "api_source": "https://api.worldquantbrain.com/tutorial-pages/example-expression-alphas",
  "capture_source": "rendered_website"
}
```

## Content

```text
Table of Contents
Implied Volatility Spread as a predictor
6-Month Call–Put Volatility Skew
5-Day Peer vs. Stock Performance Gap
Investing for the Future
Free Cash Flow Quality and Inventory Efficiency Signal
Bull Trap
Implied Volatility Spread as a predictor

Hypothesis
If the Call Open interest is higher than the Put Open interest, the stock may rise based on the intensity of the implied volatility spread or vice versa.

Implementation
Use 'trade_when' operator, with condition on the call-put open interest ratio. If it is less than unity, go long on stock based on intensity of the (Implied Volatility) IV spread, using option data.

Hint to improve the Alpha

Can using custom neutralization on the Alpha based on self-created groups (like historical volatility) help improve sub-universe performance? Use floor or bucket operator combined with rank operator to implement custom neutralization

1
trade_when(pcr_oi_270 < 1, (implied_volatility_call_270-implied_volatility_put_270), -1)
Open example alpha in Simulate
Simulation Settings
Region	Universe	Language	Decay	Delay	Truncation	Neutralization	Pasteurization	Lookback	Max Trade	Max Position
USA	TOP3000	Fast Expression	4	1	0.08	Market	On		OFF
6-Month Call–Put Volatility Skew

Hypothesis
When call implied volatility is higher than put implied volatility relative to average ATM volatility, options traders may be more focused on upside moves than downside risk, indicating bullish sentiment.

Implementation
Take the ratio of the difference between 6‑month call implied volatility and 6‑month put implied volatility over the 6‑month mean implied volatility and prefer stocks with higher values.

Hint to improve the Alpha

Preprocess data with ts_backfill() to pass the Weight Test. Also, the turnover is too high, can you come up with ideas to reduce it?

1
(implied_volatility_call_180- implied_volatility_put_180)/implied_volatility_mean_180
Open example alpha in Simulate
Simulation Settings
Region	Universe	Language	Decay	Delay	Truncation	Neutralization	Pasteurization	Lookback	Max Trade	Max Position
USA	TOP3000	Fast Expression	0	0	0.08	Subindustry	On		OFF
5-Day Peer vs. Stock Performance Gap

Hypothesis
If peers have done much better than the stock, the stock may be a short-term laggard that could mean-revert up

Implementation
Comparing the 5-day cumulative return of peer group to the 5-day cumulative return of the stock

Hint to improve the Alpha

When the gap is small and volatile, the signal may trade too much. Can you use trade_when to execute trades only when the gap is significant?

1
2
3
cum_rel_return = (1+ts_delay(rel_ret_all,4))*(1+ts_delay(rel_ret_all,3))*(1+ts_delay(rel_ret_all,2))*(1+ts_delay(rel_ret_all,1))*(1+rel_ret_all);
cum_return = (1+ts_delay(returns,4))*(1+ts_delay(returns,3))*(1+ts_delay(returns,2))*(1+ts_delay(returns,1))*(1+returns);
cum_rel_return -cum_return
Open example alpha in Simulate
Simulation Settings
Region	Universe	Language	Decay	Delay	Truncation	Neutralization	Pasteurization	Lookback	Max Trade	Max Position
USA	TOP3000	Fast Expression	0	1	0.08	Sector	On		OFF
Investing for the Future

Hypothesis
The firms those invest more and more to the long-term may get more profit in the future than those who do not thus we should long them

Implementation
Use fnd6_newqv1300_ivltq as the long-term investment measure. Backfill it over 60 days and sum over 252 days to create a rolling yearly long-term investment series.

Run ts_regression( … , ts_step(1), 756, rettype = 2) over 3 years with ts_step(1) as the time variable; this extracts the trend of yearly long-term investment.

Hint to improve the Alpha

Can you boost performance by adding more weight to firms that also have recently increasing revenue?

1
ts_regression(ts_sum(ts_backfill(fnd6_newqv1300_ivltq,60),252),ts_step(1),756,rettype = 2)
Open example alpha in Simulate
Simulation Settings
Region	Universe	Language	Decay	Delay	Truncation	Neutralization	Pasteurization	Lookback	Max Trade	Max Position
USA	TOP3000	Fast Expression	0	1	0.08	Subindustry	On		OFF
Free Cash Flow Quality and Inventory Efficiency Signal

Hypothesis
Companies with persistently high estimated operating cash flow relative to their capital expenditure are expected to outperform. This reflects superior free cash flow generation, which the market tends to reward with higher valuations over time.

Implementation
Using est_cashflow_op - est_capex as Proxy for Free Cash Flow quality then normalize across time series (252-day window) and smooth signal with ts_decay.

Hint to improve the Alpha

When those same companies also show a dramatic improvement in inventory turnover (>50% better than a year ago), the signal is amplified — suggesting accelerating business momentum.

1
ts_decay_linear(ts_scale(est_cashflow_op,252),22)-ts_decay_linear(ts_scale(est_capex,252),22)
Open example alpha in Simulate
Simulation Settings
Region	Universe	Language	Decay	Delay	Truncation	Neutralization	Pasteurization	Lookback	Max Trade	Max Position
USA	TOP3000	Fast Expression	2	1	0.08	Industry	On		OFF
Bull Trap

Hypothesis
When the multi-day slope of first-minute reactions is deteriorating but a large up-spike occurs today, it flags potential trap.

Implementation
Compute the 5‑day slope of first‑minute news reactions using ts_regression on news_pct_1min with rettype =2, then multiply the negative of the recent max post‑news upside return by the absolute value of this slope. Finally, winsorize the result with std = 4 to normalize extreme values and use it to flag potential bull traps.

Hint to improve the Alpha

Try to improve turnover.

1
2
slope = ts_regression(ts_backfill(news_pct_1min,60), ts_step(1), 5, rettype=2);
winsorize(-ts_backfill(news_max_up_ret,60) * abs(slope),std = 4)
Open example alpha in Simulate
Simulation Settings
Region	Universe	Language	Decay	Delay	Truncation	Neutralization	Pasteurization	Lookback	Max Trade	Max Position
USA	TOP3000	Fast Expression	0	1	0.08	Industry	On		OFF
```

## Links
- [Implied Volatility Spread as a predictor](https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas#implied-volatility-spread-as-a-predictor)
- [6-Month Call–Put Volatility Skew](https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas#6-month-callput-volatility-skew)
- [5-Day Peer vs. Stock Performance Gap](https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas#5-day-peer-vs-stock-performance-gap)
- [Investing for the Future](https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas#investing-for-the-future)
- [Free Cash Flow Quality and Inventory Efficiency Signal](https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas#free-cash-flow-quality-and-inventory-efficiency-signal)
- [Bull Trap](https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas#bull-trap)
