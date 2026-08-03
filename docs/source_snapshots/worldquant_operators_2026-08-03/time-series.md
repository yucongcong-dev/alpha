# Time Series Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-03

| Name | Level | Scope | Definition | Documentation |
|---|---|---|---|---|
| `days_from_last_change` | ALL | REGULAR | `days_from_last_change(x)` | [/operators/days_from_last_change](https://platform.worldquantbrain.com/learn/operators/operators/days_from_last_change) |
| `hump` | ALL | REGULAR | `hump(x, hump = 0.01)` | [/operators/hump](https://platform.worldquantbrain.com/learn/operators/operators/hump) |
| `kth_element` | ALL | REGULAR | `kth_element(x, d, k, ignore=“NaN”)` | [/operators/kth_element](https://platform.worldquantbrain.com/learn/operators/operators/kth_element) |
| `last_diff_value` | ALL | REGULAR | `last_diff_value(x, d)` | [/operators/last_diff_value](https://platform.worldquantbrain.com/learn/operators/operators/last_diff_value) |
| `ts_arg_max` | ALL | REGULAR | `ts_arg_max(x, d)` | [/operators/ts_arg_max](https://platform.worldquantbrain.com/learn/operators/operators/ts_arg_max) |
| `ts_arg_min` | ALL | REGULAR | `ts_arg_min(x, d)` | [/operators/ts_arg_min](https://platform.worldquantbrain.com/learn/operators/operators/ts_arg_min) |
| `ts_av_diff` | ALL | REGULAR | `ts_av_diff(x, d)` | [/operators/ts_av_diff](https://platform.worldquantbrain.com/learn/operators/operators/ts_av_diff) |
| `ts_backfill` | ALL | REGULAR | `ts_backfill(x,lookback = d, k=1)` | [/operators/ts_backfill](https://platform.worldquantbrain.com/learn/operators/operators/ts_backfill) |
| `ts_corr` | ALL | REGULAR | `ts_corr(x, y, d)` | [/operators/ts_corr](https://platform.worldquantbrain.com/learn/operators/operators/ts_corr) |
| `ts_count_nans` | ALL | REGULAR | `ts_count_nans(x ,d)` | [/operators/ts_count_nans](https://platform.worldquantbrain.com/learn/operators/operators/ts_count_nans) |
| `ts_covariance` | ALL | REGULAR | `ts_covariance(y, x, d)` | [/operators/ts_covariance](https://platform.worldquantbrain.com/learn/operators/operators/ts_covariance) |
| `ts_decay_linear` | ALL | REGULAR | `ts_decay_linear(x, d, dense = false)` | [/operators/ts_decay_linear](https://platform.worldquantbrain.com/learn/operators/operators/ts_decay_linear) |
| `ts_delay` | ALL | REGULAR | `ts_delay(x, d)` | [/operators/ts_delay](https://platform.worldquantbrain.com/learn/operators/operators/ts_delay) |
| `ts_delta` | ALL | REGULAR | `ts_delta(x, d)` | [/operators/ts_delta](https://platform.worldquantbrain.com/learn/operators/operators/ts_delta) |
| `ts_mean` | ALL | REGULAR | `ts_mean(x, d)` | [/operators/ts_mean](https://platform.worldquantbrain.com/learn/operators/operators/ts_mean) |
| `ts_product` | ALL | REGULAR | `ts_product(x, d)` | [/operators/ts_product](https://platform.worldquantbrain.com/learn/operators/operators/ts_product) |
| `ts_quantile` | ALL | REGULAR | `ts_quantile(x,d, driver="gaussian" )` | [/operators/ts_quantile](https://platform.worldquantbrain.com/learn/operators/operators/ts_quantile) |
| `ts_rank` | ALL | REGULAR | `ts_rank(x, d, constant = 0)` | [/operators/ts_rank](https://platform.worldquantbrain.com/learn/operators/operators/ts_rank) |
| `ts_regression` | ALL | REGULAR | `ts_regression(y, x, d, lag = 0, rettype = 0)` | [/operators/ts_regression](https://platform.worldquantbrain.com/learn/operators/operators/ts_regression) |
| `ts_scale` | ALL | REGULAR | `ts_scale(x, d, constant = 0)` | [/operators/ts_scale](https://platform.worldquantbrain.com/learn/operators/operators/ts_scale) |
| `ts_std_dev` | ALL | REGULAR | `ts_std_dev(x, d)` | [/operators/ts_std_dev](https://platform.worldquantbrain.com/learn/operators/operators/ts_std_dev) |
| `ts_step` | ALL | REGULAR | `ts_step(1)` | [/operators/ts_step](https://platform.worldquantbrain.com/learn/operators/operators/ts_step) |
| `ts_sum` | ALL | REGULAR | `ts_sum(x, d)` |  |
| `ts_zscore` | ALL | REGULAR | `ts_zscore(x, d)` | [/operators/ts_zscore](https://platform.worldquantbrain.com/learn/operators/operators/ts_zscore) |

## Details

### `days_from_last_change`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `days_from_last_change(x)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/days_from_last_change

Calculates the number of days since the last change in the value of a given variable.

### `hump`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `hump(x, hump = 0.01)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/hump

Limits amount and magnitude of changes in input (thus reducing turnover)

### `kth_element`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `kth_element(x, d, k, ignore=“NaN”)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/kth_element

Returns the K-th value from a time series by looking back over a specified number of (‘d’) days, with the option to ignore certain values. Commonly used for backfilling missing data.

### `last_diff_value`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `last_diff_value(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/last_diff_value

Returns the most recent value of x from the past d days that is different from the current value of x.

### `ts_arg_max`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_arg_max(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_arg_max

Returns the number of days since the maximum value occurred in the last d days of a time series. If today's value is the maximum, returns 0; if it was yesterday, returns 1, and so on.

### `ts_arg_min`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_arg_min(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_arg_min

Returns the number of days since the minimum value occurred in a time series over the past d days. If today's value is the minimum, returns 0; if it was yesterday, returns 1, and so on.

### `ts_av_diff`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_av_diff(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_av_diff

Calculates the difference between a value and its mean over a specified period, ignoring NaN values in the mean calculation. In short, it returns x – ts_mean(x, d) with NaNs ignored.

### `ts_backfill`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_backfill(x,lookback = d, k=1)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_backfill

Replaces missing (NaN) values in a time series with the most recent valid value from a specified lookback window, improving data coverage and reducing risk from missing data.

### `ts_corr`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_corr(x, y, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_corr

Calculates the Pearson correlation between two variables, x and y, over the past d days, showing how closely they move together.

### `ts_count_nans`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_count_nans(x ,d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_count_nans

Counts the number of missing (NaN) values in a data series over a specified number of days.

### `ts_covariance`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_covariance(y, x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_covariance

Calculates the covariance between two time-series variables, y and x, over the past d days. Useful for measuring how two variables move together within a specified historical window.

### `ts_decay_linear`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_decay_linear(x, d, dense = false)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_decay_linear

Applies a linear decay to time-series data over a set number of days, smoothing the data by averaging recent values and reducing the impact of older or missing data.

### `ts_delay`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_delay(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_delay

Returns the value of a variable x from d days ago. Use this operator to access historical data points by specifying the desired time lag in days.

### `ts_delta`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_delta(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_delta

Calculates the difference between a value and its delayed version over a specified period. Useful for measuring changes or momentum in time-series data.

### `ts_mean`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_mean(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_mean

Calculates the simple average (mean) value of a variable x over the past d days.

### `ts_product`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_product(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_product

Returns the product of the values of x over the past d days. Useful for calculating geometric means and compounding returns or growth rates.

### `ts_quantile`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_quantile(x,d, driver="gaussian" )`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_quantile

Calculates the ts_rank of the input and transforms it using the inverse cumulative distribution function (quantile function) of a specified probability distribution (default: Gaussian/normal). This helps to normalize or reshape the distribution of your data over a rolling window.

### `ts_rank`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_rank(x, d, constant = 0)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_rank

Ranks the value of a variable for each instrument over a specified number of past days, returning the rank of the current value (optionally adjusted by a constant). Useful for normalizing time-series data and highlighting relative performance over time.

### `ts_regression`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_regression(y, x, d, lag = 0, rettype = 0)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_regression

Returns various parameters related to regression function

### `ts_scale`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_scale(x, d, constant = 0)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_scale

Scales a time series to a 0–1 range based on its minimum and maximum values over a specified period, with an optional constant shift.

### `ts_std_dev`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_std_dev(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_std_dev

Calculates the standard deviation of a data series x over the past d days, measuring how much the values deviate from their mean during that period.

### `ts_step`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_step(1)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_step

Returns a counter of days, incrementing by one each day.

### `ts_sum`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_sum(x, d)`

Sum values of x for the past d days.

### `ts_zscore`

- Category: Time Series
- Level: ALL
- Scope: REGULAR
- Definition: `ts_zscore(x, d)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/ts_zscore

Calculates the Z-score of a time series, showing how far today's value is from the recent average, measured in standard deviations. Useful for standardizing and comparing values over time.
