# Cross Sectional Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-06

## `normalize`

- **Definition**: `normalize(x, useStd = false, limit = 0.0)`
- **Description**: Centers a daily cross section by subtracting the market mean; optionally divide by the cross sectional standard deviation and clamp the result to [?limit, +limit]. NaNs are ignored in mean/std.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/normalize

## `quantile`

- **Definition**: `quantile(x, driver = gaussian, sigma = 1.0)`
- **Description**: Ranks and shifts a vector of Alpha values, then applies a chosen statistical distribution (gaussian, cauchy, or uniform) to reduce outliers. The sigma parameter controls the scale of the output.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/quantile

## `rank`

- **Definition**: `rank(x, rate=2)`
- **Description**: Ranks the values of the input x among all instruments, returning numbers evenly spaced between 0.0 and 1.0. Useful for normalizing data and reducing the impact of outliers.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/rank

## `scale`

- **Definition**: `scale(x, scale=1, longscale=1, shortscale=1)`
- **Description**: Scales the input so that the sum of absolute values across all instruments equals a specified book size. Allows separate scaling for long and short positions using optional parameters.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/scale

## `winsorize`

- **Definition**: `winsorize(x, std=4)`
- **Description**: Winsorize limits values in a data to within a specified number of standard deviations from the mean, reducing the impact of extreme outliers. Note: recommended std values range from 2 to 5: std = 2, 3, 4, 5 removes approximately 4.5%, 0.27%, 0.01%, and 0.0001% of extreme values, respectively (higher std removes fewer extremes).
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/winsorize

## `zscore`

- **Definition**: `zscore(x)`
- **Description**: Z-score is a numerical measurement that describes a value's relationship to the mean of a group of values. Z-score is measured in terms of standard deviations from the mean
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/zscore
