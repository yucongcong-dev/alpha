# Group Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-06

## `group_backfill`

- **Definition**: `group_backfill(x, group, d, std = 4.0)`
- **Description**: Fills missing (NaN) values for instruments within the same group by calculating a winsorized mean of all non-NaN values over the past d days. The winsorized mean is computed by trimming extreme values based on a specified standard deviation multiplier (std, default 4.0).
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/group_backfill

## `group_mean`

- **Definition**: `group_mean(x, weight, group)`
- **Description**: Calculates the harmonic mean of a data field within each specified group.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/group_mean

## `group_neutralize`

- **Definition**: `group_neutralize(x, group)`
- **Description**: Neutralizes Alpha values within each specified group by subtracting the group mean from each value. Groups can be industry, sector, country, or any custom grouping.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/group_neutralize

## `group_rank`

- **Definition**: `group_rank(x, group)`
- **Description**: Ranks each element within its group based on the input field, assigning a value between 0.0 and 1.0. This helps compare items within the same group, such as stocks in the same industry.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/group_rank

## `group_scale`

- **Definition**: `group_scale(x, group)`
- **Description**: Normalizes values within each group to a range between 0 and 1, making data comparable across different groups.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/group_scale

## `group_zscore`

- **Definition**: `group_zscore(x, group)`
- **Description**: Calculates the Z-score of each value within its group, showing how far each value is from the group mean in terms of standard deviations. Useful for comparing values relative to their group.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/group_zscore
