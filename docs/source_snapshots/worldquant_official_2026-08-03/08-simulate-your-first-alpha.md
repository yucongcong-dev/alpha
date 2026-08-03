# Simulate your first Alpha

Source: https://platform.worldquantbrain.com/learn/documentation/create-alphas/running-your-first-alpha
API Source: https://api.worldquantbrain.com/tutorial-pages/running-your-first-alpha
Captured: 2026-08-03
Official source: WorldQuant BRAIN Learn Documentation API
Section: Create Alphas
Last modified: 2026-03-09T06:50:21.997260-04:00

## Metadata
```json
{
  "id": "running-your-first-alpha",
  "tutorial": "create-alphas",
  "tutorial_title": "Create Alphas",
  "title": "Simulate your first Alpha",
  "url": "https://platform.worldquantbrain.com/learn/documentation/create-alphas/running-your-first-alpha",
  "lastModified": "2026-03-09T06:50:21.997260-04:00",
  "duration": "PT3M",
  "api_source": "https://api.worldquantbrain.com/tutorial-pages/running-your-first-alpha"
}
```

## Content

Alphas are created and simulated on the Simulate page in the Alphas dropdown tab. To run your first simulation, click on the gear icon at the top right-hand side corner. This will open the settings panel. Here, select “US: TOP3000” for Region and Universe, “Subindustry” for Neutralization and apply your settings. Make sure both Code and Result are ticked by clicking on them. In the Alpha expression text box, enter -Delta(close, 5) for now and click on "Simulate". The Simulation Result page will show a graph for Cumulative Profit. This graph can be zoomed in to plot area for shorter time periods (1 month or 1 year).

The display consists of 2 graphs, one for PnL vs. Time and the other for Sharpe Ratio vs. Time.
In the Stats tab, a good Alpha tend to have consistently increasing PnL and high Annual Return, Sharpe Ratio, % Profitable Days and Profit per Dollar Traded. It should have low Drawdown and Turnover. And more importantly, it shouldn’t have high fluctuations in the cumulative profit graph. If the standard deviation is low, there tends to be lesser fluctuations in the graph. If the graph shows high fluctuations/volatility, despite the returns being high, the Alpha will not be deemed good enough. An Alpha is considered to be “good” if:
Its turnover is low, but not less than 1%
Its Percentage Drawdown is less than 10%
Its Sharpe is greater than 2.0 for delay 0 Alphas and greater than 1.25 for delay 1 Alphas
The graph above for Alpha expression -Delta(close, 5) shows several significant drawdowns, as well as a flattening of returns in 2017. The table below marks this Alpha as Inferior (Needs Improvement). PnL and Sharpe for 2017 drop low, and drawdown is large in 2014 and 2015. This Alpha is Inferior (Needs Improvement) due to high volatility and low returns.

### Simulation Example

Settings:
```json
{
  "instrumentType": "EQUITY",
  "region": "USA",
  "universe": "TOP3000",
  "delay": 1,
  "decay": 0,
  "neutralization": "MARKET",
  "truncation": 0.08,
  "pasteurization": "ON",
  "unitHandling": "VERIFY",
  "nanHandling": "OFF",
  "language": "FASTEXPR",
  "maxTrade": "OFF"
}
```

Expression:
```text
-ts_delta(close, 5)
```

### Image
- **title**: stats
- **width**: 899
- **height**: 562
- **fileSize**: 27562
- **url**: https://api.worldquantbrain.com/content/images/HzFKTKGCaOl6F8AlLV6YxEYz__8=/43/original/first_alpha_stats.PNG

Use the green refreshing button in the Correlation block to get the information about the correlation of the currently simulated Alpha with the Alphas in your own OS (Out-of-Sample) pool. This will be explained further in the Simulation Results page.
The image below shows the Properties of the Alpha. You can name your Alpha, assign a category and color code, and add user-defined tags to them. You can add a brief description about your Alpha for your reference. Suggestion - keep the number of user-defined tags low so that they don't proliferate and are easily searchable in the My Alphas page.

### Image
- **title**: properties
- **width**: 876
- **height**: 391
- **fileSize**: 13990
- **url**: https://api.worldquantbrain.com/content/images/0GwoWmmrVu0sFznPm174F8fz4bg=/44/original/first_alpha_properties.PNG

To Submit Alpha for OS Test, click the "Submit Alpha" button in the Submission tab of the results panel. This will check if the Alpha meets the Correlation and Sharpe criteria before submitting it.

Check out the below video for another example.
