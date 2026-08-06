# ⭐ Alpha Examples for Bronze Users 🥉

Official URL: https://platform.worldquantbrain.com/learn/documentation/examples/sample-alpha-concepts
API Source: https://api.worldquantbrain.com/tutorial-pages/sample-alpha-concepts
Captured: 2026-08-06
Official source: WorldQuant BRAIN rendered Learn page via Chrome
Capture method: rendered_website
Section: Examples
Last modified: None

## Metadata
```json
{
  "id": "sample-alpha-concepts",
  "tutorial": "examples",
  "tutorial_title": "Examples",
  "title": "⭐ Alpha Examples for Bronze Users 🥉",
  "url": "https://platform.worldquantbrain.com/learn/documentation/examples/sample-alpha-concepts",
  "lastModified": null,
  "duration": null,
  "api_source": "https://api.worldquantbrain.com/tutorial-pages/sample-alpha-concepts",
  "capture_source": "rendered_website"
}
```

## Content

```text
Table of Contents
Valuation based on cash flow
Overpriced stocks
Volatility arbitrage
Valuation based on cash flow

Hypothesis

A lower EV/CF usually suggests the company is becoming cheaper relative to its cash-generating ability; a higher multiple suggests it’s getting more expensive.

Implementation

Use ts_zscore to standardize the chang of the ratio and group_rank to control the turnover.

Hint to Improve Alpha

There are various types of cash flow, and switching the type used in the metric may improve its performance.

1
group_rank(-ts_zscore(enterprise_value/cashflow, 63),industry)
Open example alpha in Simulate
Simulation Settings
Region	Universe	Language	Decay	Delay	Truncation	Neutralization	Pasteurization	Lookback	Max Trade	Max Position
USA	TOP3000	Fast Expression	0	1	0.08	Industry	On		OFF
Overpriced stocks

Hypothesis

When analyst price target estimates (est_ptp) and free cashflow estimates (est_fcf) move highly in sync over the past month (high positive correlation), it may signal that the market has already fully priced in the cash flow expectations into price targets — leaving little room for further upside.

Implementation

Using est_ptp to capture price estimate and est_fcf to capture free cash flow and calculate the dynamics between them with ts_corr.

Hint to Improve Alpha

The window of 1 year might be too long to react on the price correction. Try shorter window.

1
-ts_corr(est_ptp,est_fcf,252)
Open example alpha in Simulate
Simulation Settings
Region	Universe	Language	Decay	Delay	Truncation	Neutralization	Pasteurization	Lookback	Max Trade	Max Position
USA	TOP3000	Fast Expression	0	1	0.08	Market	On		OFF
Volatility arbitrage

Hypothesis

Higher volatility is often observed during bearish markets, while lower volatility is typically seen during bullish markets. A lower Parkinson's volatility coupled with a higher implied volatility may suggest that there could be a stronger bullish sentiment for the stock in the future.

Implementation

Long the stock if its implied volatility significantly exceeds its historical volatility and short the opposite

Hint to Improve Alpha

Can you use ts_backfill to avoid missing data on certain days?

1
implied_volatility_call_120/parkinson_volatility_120
Open example alpha in Simulate
Simulation Settings
Region	Universe	Language	Decay	Delay	Truncation	Neutralization	Pasteurization	Lookback	Max Trade	Max Position
USA	TOP200	Fast Expression	0	1	0.08	Sector	On		OFF
```

## Links
- [Valuation based on cash flow](https://platform.worldquantbrain.com/learn/documentation/examples/sample-alpha-concepts#valuation-based-on-cash-flow)
- [Overpriced stocks](https://platform.worldquantbrain.com/learn/documentation/examples/sample-alpha-concepts#overpriced-stocks)
- [Volatility arbitrage](https://platform.worldquantbrain.com/learn/documentation/examples/sample-alpha-concepts#volatility-arbitrage)
