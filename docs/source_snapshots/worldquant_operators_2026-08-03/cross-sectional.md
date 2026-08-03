# Cross Sectional Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-03

| Name | Level | Scope | Definition | Documentation |
|---|---|---|---|---|
| `normalize` | ALL | REGULAR | `normalize(x, useStd = false, limit = 0.0)` | [/operators/normalize](https://platform.worldquantbrain.com/learn/operators/operators/normalize) |
| `quantile` | ALL | REGULAR | `quantile(x, driver = gaussian, sigma = 1.0)` | [/operators/quantile](https://platform.worldquantbrain.com/learn/operators/operators/quantile) |
| `rank` | ALL | REGULAR | `rank(x, rate=2)` | [/operators/rank](https://platform.worldquantbrain.com/learn/operators/operators/rank) |
| `scale` | ALL | REGULAR | `scale(x, scale=1, longscale=1, shortscale=1)` | [/operators/scale](https://platform.worldquantbrain.com/learn/operators/operators/scale) |
| `winsorize` | ALL | REGULAR | `winsorize(x, std=4)` | [/operators/winsorize](https://platform.worldquantbrain.com/learn/operators/operators/winsorize) |
| `zscore` | ALL | REGULAR | `zscore(x)` | [/operators/zscore](https://platform.worldquantbrain.com/learn/operators/operators/zscore) |

## Details

### `normalize`

- Category: Cross Sectional
- Level: ALL
- Scope: REGULAR
- Definition: `normalize(x, useStd = false, limit = 0.0)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/normalize

Centers a daily cross section by subtracting the market mean; optionally divide by the cross sectional standard deviation and clamp the result to [?limit, +limit]. NaNs are ignored in mean/std.

### `quantile`

- Category: Cross Sectional
- Level: ALL
- Scope: REGULAR
- Definition: `quantile(x, driver = gaussian, sigma = 1.0)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/quantile

Ranks and shifts a vector of Alpha values, then applies a chosen statistical distribution (gaussian, cauchy, or uniform) to reduce outliers. The sigma parameter controls the scale of the output.

### `rank`

- Category: Cross Sectional
- Level: ALL
- Scope: REGULAR
- Definition: `rank(x, rate=2)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/rank

Ranks the values of the input x among all instruments, returning numbers evenly spaced between 0.0 and 1.0. Useful for normalizing data and reducing the impact of outliers.

### `scale`

- Category: Cross Sectional
- Level: ALL
- Scope: REGULAR
- Definition: `scale(x, scale=1, longscale=1, shortscale=1)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/scale

Scales the input so that the sum of absolute values across all instruments equals a specified book size. Allows separate scaling for long and short positions using optional parameters.

### `winsorize`

- Category: Cross Sectional
- Level: ALL
- Scope: REGULAR
- Definition: `winsorize(x, std=4)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/winsorize

Winsorize limits values in a data to within a specified number of standard deviations from the mean, reducing the impact of extreme outliers. Note: recommended std values range from 2 to 5: std = 2, 3, 4, 5 removes approximately 4.5%, 0.27%, 0.01%, and 0.0001% of extreme values, respectively (higher std removes fewer extremes).

### `zscore`

- Category: Cross Sectional
- Level: ALL
- Scope: REGULAR
- Definition: `zscore(x)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/zscore

Z-score is a numerical measurement that describes a value's relationship to the mean of a group of values. Z-score is measured in terms of standard deviations from the mean
