# Transformational Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-03

| Name | Level | Scope | Definition | Documentation |
|---|---|---|---|---|
| `bucket` | ALL | REGULAR | `bucket(rank(x), range=“0, 1, 0.1”, skipBoth=False, NaNGroup=False)
or
bucket(rank(x), buckets = “2,5,6,7,10”, skipBoth=False, NaNGroup=False)` | [/operators/bucket](https://platform.worldquantbrain.com/learn/operators/operators/bucket) |
| `trade_when` | ALL | REGULAR | `trade_when(x, y, z)` | [/operators/trade_when](https://platform.worldquantbrain.com/learn/operators/operators/trade_when) |

## Details

### `bucket`

- Category: Transformational
- Level: ALL
- Scope: REGULAR
- Definition: `bucket(rank(x), range=“0, 1, 0.1”, skipBoth=False, NaNGroup=False)
or
bucket(rank(x), buckets = “2,5,6,7,10”, skipBoth=False, NaNGroup=False)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/bucket

The bucket operator creates custom groups by dividing data into buckets (ranges) based on ranked values of any data field. These buckets can then be used with group operators like group_neutralize, group_rank, group_zscore etc.

### `trade_when`

- Category: Transformational
- Level: ALL
- Scope: REGULAR
- Definition: `trade_when(x, y, z)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/trade_when

The trade_when operator changes Alpha values only when a specific condition is met, keeps previous values otherwise, and can close positions by assigning NaN under an exit condition. It is useful for reducing turnover and controlling when trades are executed.
