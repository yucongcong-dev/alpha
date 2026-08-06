# Time Series Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-06

## `days_from_last_change`

- **Definition**: `days_from_last_change(x)`
- **Description**: Calculates the number of days since the last change in the value of a given variable.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/days_from_last_change

## `hump`

- **Definition**: `hump(x, hump = 0.01)`
- **Description**: Limits amount and magnitude of changes in input (thus reducing turnover)
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/hump

## `kth_element`

- **Definition**: `kth_element(x, d, k, ignore=“NaN”)`
- **Description**: Returns the K-th value from a time series by looking back over a specified number of (‘d’) days, with the option to ignore certain values. Commonly used for backfilling missing data.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/kth_element

## `last_diff_value`

- **Definition**: `last_diff_value(x, d)`
- **Description**: Returns the most recent value of x from the past d days that is different from the current value of x.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/last_diff_value

## `ts_arg_max`

- **Definition**: `ts_arg_max(x, d)`
- **Description**: Returns the number of days since the maximum value occurred in the last d days of a time series. If today's value is the maximum, returns 0; if it was yesterday, returns 1, and so on.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_arg_max

## `ts_arg_min`

- **Definition**: `ts_arg_min(x, d)`
- **Description**: Returns the number of days since the minimum value occurred in a time series over the past d days. If today's value is the minimum, returns 0; if it was yesterday, returns 1, and so on.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_arg_min

## `ts_av_diff`

- **Definition**: `ts_av_diff(x, d)`
- **Description**: Calculates the difference between a value and its mean over a specified period, ignoring NaN values in the mean calculation. In short, it returns x – ts_mean(x, d) with NaNs ignored.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_av_diff

## `ts_backfill`

- **Definition**: `ts_backfill(x,lookback = d, k=1)`
- **Description**: Replaces missing (NaN) values in a time series with the most recent valid value from a specified lookback window, improving data coverage and reducing risk from missing data.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_backfill

## `ts_corr`

- **Definition**: `ts_corr(x, y, d)`
- **Description**: Calculates the Pearson correlation between two variables, x and y, over the past d days, showing how closely they move together.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_corr

## `ts_count_nans`

- **Definition**: `ts_count_nans(x ,d)`
- **Description**: Counts the number of missing (NaN) values in a data series over a specified number of days.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_count_nans

## `ts_covariance`

- **Definition**: `ts_covariance(y, x, d)`
- **Description**: Calculates the covariance between two time-series variables, y and x, over the past d days. Useful for measuring how two variables move together within a specified historical window.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_covariance

## `ts_decay_linear`

- **Definition**: `ts_decay_linear(x, d, dense = false)`
- **Description**: Applies a linear decay to time-series data over a set number of days, smoothing the data by averaging recent values and reducing the impact of older or missing data.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_decay_linear

## `ts_delay`

- **Definition**: `ts_delay(x, d)`
- **Description**: Returns the value of a variable x from d days ago. Use this operator to access historical data points by specifying the desired time lag in days.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_delay

## `ts_delta`

- **Definition**: `ts_delta(x, d)`
- **Description**: Calculates the difference between a value and its delayed version over a specified period. Useful for measuring changes or momentum in time-series data.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_delta

## `ts_mean`

- **Definition**: `ts_mean(x, d)`
- **Description**: Calculates the simple average (mean) value of a variable x over the past d days.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_mean

## `ts_product`

- **Definition**: `ts_product(x, d)`
- **Description**: Returns the product of the values of x over the past d days. Useful for calculating geometric means and compounding returns or growth rates.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_product

## `ts_quantile`

- **Definition**: `ts_quantile(x,d, driver="gaussian" )`
- **Description**: Calculates the ts_rank of the input and transforms it using the inverse cumulative distribution function (quantile function) of a specified probability distribution (default: Gaussian/normal). This helps to normalize or reshape the distribution of your data over a rolling window.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_quantile

## `ts_rank`

- **Definition**: `ts_rank(x, d, constant = 0)`
- **Description**: Ranks the value of a variable for each instrument over a specified number of past days, returning the rank of the current value (optionally adjusted by a constant). Useful for normalizing time-series data and highlighting relative performance over time.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_rank

## `ts_regression`

- **Definition**: `ts_regression(y, x, d, lag = 0, rettype = 0)`
- **Description**: Returns various parameters related to regression function
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_regression

## `ts_scale`

- **Definition**: `ts_scale(x, d, constant = 0)`
- **Description**: Scales a time series to a 0–1 range based on its minimum and maximum values over a specified period, with an optional constant shift.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_scale

## `ts_std_dev`

- **Definition**: `ts_std_dev(x, d)`
- **Description**: Calculates the standard deviation of a data series x over the past d days, measuring how much the values deviate from their mean during that period.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_std_dev

## `ts_step`

- **Definition**: `ts_step(1)`
- **Description**: Returns a counter of days, incrementing by one each day.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_step

## `ts_sum`

- **Definition**: `ts_sum(x, d)`
- **Description**: Sum values of x for the past d days.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com

## `ts_zscore`

- **Definition**: `ts_zscore(x, d)`
- **Description**: Calculates the Z-score of a time series, showing how far today's value is from the recent average, measured in standard deviations. Useful for standardizing and comparing values over time.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/ts_zscore
