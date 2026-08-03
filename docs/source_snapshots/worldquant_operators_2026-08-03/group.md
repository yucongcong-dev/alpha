# Group Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-03

| Name | Level | Scope | Definition | Documentation |
|---|---|---|---|---|
| `group_backfill` | ALL | REGULAR | `group_backfill(x, group, d, std = 4.0)` | [/operators/group_backfill](https://platform.worldquantbrain.com/learn/operators/operators/group_backfill) |
| `group_mean` | ALL | REGULAR | `group_mean(x, weight, group)` | [/operators/group_mean](https://platform.worldquantbrain.com/learn/operators/operators/group_mean) |
| `group_neutralize` | ALL | REGULAR | `group_neutralize(x, group)` | [/operators/group_neutralize](https://platform.worldquantbrain.com/learn/operators/operators/group_neutralize) |
| `group_rank` | ALL | REGULAR | `group_rank(x, group)` | [/operators/group_rank](https://platform.worldquantbrain.com/learn/operators/operators/group_rank) |
| `group_scale` | ALL | REGULAR | `group_scale(x, group)` | [/operators/group_scale](https://platform.worldquantbrain.com/learn/operators/operators/group_scale) |
| `group_zscore` | ALL | REGULAR | `group_zscore(x, group)` | [/operators/group_zscore](https://platform.worldquantbrain.com/learn/operators/operators/group_zscore) |

## Details

### `group_backfill`

- Category: Group
- Level: ALL
- Scope: REGULAR
- Definition: `group_backfill(x, group, d, std = 4.0)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/group_backfill

Fills missing (NaN) values for instruments within the same group by calculating a winsorized mean of all non-NaN values over the past d days. The winsorized mean is computed by trimming extreme values based on a specified standard deviation multiplier (std, default 4.0).

### `group_mean`

- Category: Group
- Level: ALL
- Scope: REGULAR
- Definition: `group_mean(x, weight, group)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/group_mean

Calculates the harmonic mean of a data field within each specified group.

### `group_neutralize`

- Category: Group
- Level: ALL
- Scope: REGULAR
- Definition: `group_neutralize(x, group)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/group_neutralize

Neutralizes Alpha values within each specified group by subtracting the group mean from each value. Groups can be industry, sector, country, or any custom grouping.

### `group_rank`

- Category: Group
- Level: ALL
- Scope: REGULAR
- Definition: `group_rank(x, group)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/group_rank

Ranks each element within its group based on the input field, assigning a value between 0.0 and 1.0. This helps compare items within the same group, such as stocks in the same industry.

### `group_scale`

- Category: Group
- Level: ALL
- Scope: REGULAR
- Definition: `group_scale(x, group)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/group_scale

Normalizes values within each group to a range between 0 and 1, making data comparable across different groups.

### `group_zscore`

- Category: Group
- Level: ALL
- Scope: REGULAR
- Definition: `group_zscore(x, group)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/group_zscore

Calculates the Z-score of each value within its group, showing how far each value is from the group mean in terms of standard deviations. Useful for comparing values relative to their group.
