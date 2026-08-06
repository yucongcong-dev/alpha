# Transformational Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-06

## `bucket`

- **Definition**: `bucket(rank(x), range=“0, 1, 0.1”, skipBoth=False, NaNGroup=False)
or
bucket(rank(x), buckets = “2,5,6,7,10”, skipBoth=False, NaNGroup=False)`
- **Description**: The bucket operator creates custom groups by dividing data into buckets (ranges) based on ranked values of any data field. These buckets can then be used with group operators like group_neutralize, group_rank, group_zscore etc.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/bucket

## `trade_when`

- **Definition**: `trade_when(x, y, z)`
- **Description**: The trade_when operator changes Alpha values only when a specific condition is met, keeps previous values otherwise, and can close positions by assigning NaN under an exit condition. It is useful for reducing turnover and controlling when trades are executed.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/trade_when
