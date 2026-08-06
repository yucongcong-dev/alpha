# WorldQuant BRAIN Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-06
Official source: WorldQuant BRAIN Operators API
Capture method: local_snapshot_fallback
Fallback source: docs/source_snapshots/worldquant_operators_2026-08-06/operators.json

Total operators: 66

## Categories

- [Arithmetic](arithmetic.md) - 15 operators
- [Cross Sectional](cross-sectional.md) - 6 operators
- [Group](group.md) - 6 operators
- [Logical](logical.md) - 11 operators
- [Time Series](time-series.md) - 24 operators
- [Transformational](transformational.md) - 2 operators
- [Vector](vector.md) - 2 operators

## Operator Index

- `abs` - Arithmetic; `abs(x)`
- `add` - Arithmetic; `add(x, y, filter = false), x + y`
- `and` - Logical; `and(input1, input2)`
- `bucket` - Transformational; `bucket(rank(x), range=“0, 1, 0.1”, skipBoth=False, NaNGroup=False)
or
bucket(rank(x), buckets = “2,5,6,7,10”, skipBoth=False, NaNGroup=False)`
- `days_from_last_change` - Time Series; `days_from_last_change(x)`
- `densify` - Arithmetic; `densify(x)`
- `divide` - Arithmetic; `divide(x, y), x / y`
- `equal` - Logical; `input1 == input2`
- `greater` - Logical; `input1 > input2`
- `greater_equal` - Logical; `input1 >= input2`
- `group_backfill` - Group; `group_backfill(x, group, d, std = 4.0)`
- `group_mean` - Group; `group_mean(x, weight, group)`
- `group_neutralize` - Group; `group_neutralize(x, group)`
- `group_rank` - Group; `group_rank(x, group)`
- `group_scale` - Group; `group_scale(x, group)`
- `group_zscore` - Group; `group_zscore(x, group)`
- `hump` - Time Series; `hump(x, hump = 0.01)`
- `if_else` - Logical; `if_else(input1, input2, input 3)`
- `inverse` - Arithmetic; `inverse(x)`
- `is_nan` - Logical; `is_nan(input)`
- `kth_element` - Time Series; `kth_element(x, d, k, ignore=“NaN”)`
- `last_diff_value` - Time Series; `last_diff_value(x, d)`
- `less` - Logical; `input1 < input2`
- `less_equal` - Logical; `input1 <= input2`
- `log` - Arithmetic; `log(x)`
- `max` - Arithmetic; `max(x, y, ..)`
- `min` - Arithmetic; `min(x, y ..)`
- `multiply` - Arithmetic; `multiply(x ,y, ... , filter=false), x * y`
- `normalize` - Cross Sectional; `normalize(x, useStd = false, limit = 0.0)`
- `not` - Logical; `not(x)`
- `not_equal` - Logical; `input1!= input2`
- `or` - Logical; `or(input1, input2)`
- `power` - Arithmetic; `power(x, y)`
- `quantile` - Cross Sectional; `quantile(x, driver = gaussian, sigma = 1.0)`
- `rank` - Cross Sectional; `rank(x, rate=2)`
- `reverse` - Arithmetic; `reverse(x)`
- `scale` - Cross Sectional; `scale(x, scale=1, longscale=1, shortscale=1)`
- `sign` - Arithmetic; `sign(x)`
- `signed_power` - Arithmetic; `signed_power(x, y)`
- `sqrt` - Arithmetic; `sqrt(x)`
- `subtract` - Arithmetic; `subtract(x, y, filter=false), x - y`
- `trade_when` - Transformational; `trade_when(x, y, z)`
- `ts_arg_max` - Time Series; `ts_arg_max(x, d)`
- `ts_arg_min` - Time Series; `ts_arg_min(x, d)`
- `ts_av_diff` - Time Series; `ts_av_diff(x, d)`
- `ts_backfill` - Time Series; `ts_backfill(x,lookback = d, k=1)`
- `ts_corr` - Time Series; `ts_corr(x, y, d)`
- `ts_count_nans` - Time Series; `ts_count_nans(x ,d)`
- `ts_covariance` - Time Series; `ts_covariance(y, x, d)`
- `ts_decay_linear` - Time Series; `ts_decay_linear(x, d, dense = false)`
- `ts_delay` - Time Series; `ts_delay(x, d)`
- `ts_delta` - Time Series; `ts_delta(x, d)`
- `ts_mean` - Time Series; `ts_mean(x, d)`
- `ts_product` - Time Series; `ts_product(x, d)`
- `ts_quantile` - Time Series; `ts_quantile(x,d, driver="gaussian" )`
- `ts_rank` - Time Series; `ts_rank(x, d, constant = 0)`
- `ts_regression` - Time Series; `ts_regression(y, x, d, lag = 0, rettype = 0)`
- `ts_scale` - Time Series; `ts_scale(x, d, constant = 0)`
- `ts_std_dev` - Time Series; `ts_std_dev(x, d)`
- `ts_step` - Time Series; `ts_step(1)`
- `ts_sum` - Time Series; `ts_sum(x, d)`
- `ts_zscore` - Time Series; `ts_zscore(x, d)`
- `vec_avg` - Vector; `vec_avg(x)`
- `vec_sum` - Vector; `vec_sum(x)`
- `winsorize` - Cross Sectional; `winsorize(x, std=4)`
- `zscore` - Cross Sectional; `zscore(x)`
