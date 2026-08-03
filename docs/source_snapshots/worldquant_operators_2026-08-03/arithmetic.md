# Arithmetic Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-03

| Name | Level | Scope | Definition | Documentation |
|---|---|---|---|---|
| `abs` | ALL | REGULAR | `abs(x)` | [/operators/abs](https://platform.worldquantbrain.com/learn/operators/operators/abs) |
| `add` | ALL | REGULAR | `add(x, y, filter = false), x + y` | [/operators/add](https://platform.worldquantbrain.com/learn/operators/operators/add) |
| `densify` | ALL | REGULAR | `densify(x)` | [/operators/densify](https://platform.worldquantbrain.com/learn/operators/operators/densify) |
| `divide` | ALL | REGULAR | `divide(x, y), x / y` |  |
| `inverse` | ALL | REGULAR | `inverse(x)` |  |
| `log` | ALL | REGULAR | `log(x)` | [/operators/log](https://platform.worldquantbrain.com/learn/operators/operators/log) |
| `max` | ALL | REGULAR | `max(x, y, ..)` | [/operators/max](https://platform.worldquantbrain.com/learn/operators/operators/max) |
| `min` | ALL | REGULAR | `min(x, y ..)` | [/operators/min](https://platform.worldquantbrain.com/learn/operators/operators/min) |
| `multiply` | ALL | REGULAR | `multiply(x ,y, ... , filter=false), x * y` | [/operators/multiply](https://platform.worldquantbrain.com/learn/operators/operators/multiply) |
| `power` | ALL | REGULAR | `power(x, y)` | [/operators/power](https://platform.worldquantbrain.com/learn/operators/operators/power) |
| `reverse` | ALL | REGULAR | `reverse(x)` |  |
| `sign` | ALL | REGULAR | `sign(x)` | [/operators/sign](https://platform.worldquantbrain.com/learn/operators/operators/sign) |
| `signed_power` | ALL | REGULAR | `signed_power(x, y)` | [/operators/signed_power](https://platform.worldquantbrain.com/learn/operators/operators/signed_power) |
| `sqrt` | ALL | REGULAR | `sqrt(x)` | [/operators/sqrt](https://platform.worldquantbrain.com/learn/operators/operators/sqrt) |
| `subtract` | ALL | REGULAR | `subtract(x, y, filter=false), x - y` | [/operators/subtract](https://platform.worldquantbrain.com/learn/operators/operators/subtract) |

## Details

### `abs`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `abs(x)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/abs

Returns the absolute value of a number, removing any negative sign.

### `add`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `add(x, y, filter = false), x + y`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/add

Adds two or more inputs element wise. Set filter=true to treat NaNs as 0 before summing.

### `densify`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `densify(x)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/densify

Converts a grouping field of many buckets into lesser number of only available buckets so as to make working with grouping fields computationally efficient

### `divide`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `divide(x, y), x / y`

Returns x divided by y (x / y). Note: dividing by zero raises an error; to avoid it, use divide(x, add(y, 0.0001)); adding a small epsilon to the denominator prevents divide-by-zero errors.

### `inverse`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `inverse(x)`

Returns the reciprocal of x (1 / x). Note: errors when x = 0; to avoid it, use inverse(add(x, 0.0001)); adding a small epsilon prevents divide-by-zero errors.

### `log`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `log(x)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/log

Calculates the natural logarithm of the input value. Commonly used to transform data that has positive values.

### `max`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `max(x, y, ..)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/max

Maximum value of all inputs. At least 2 inputs are required

### `min`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `min(x, y ..)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/min

Minimum value of all inputs. At least 2 inputs are required

### `multiply`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `multiply(x ,y, ... , filter=false), x * y`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/multiply

Multiplies two or more inputs element wise. Set filter=true to treat NaNs as 0 before multiplication

### `power`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `power(x, y)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/power

Returns x raised to the power of y (x ^ y). Note: power(x, y) can drop the sign of x when y is non-integer; use signed_power(x, y) to preserve the sign of x.

### `reverse`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `reverse(x)`

- x

### `sign`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `sign(x)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/sign

Returns the sign of a number: +1 for positive, -1 for negative, and 0 for zero. If the input is NaN, returns NaN.

Input: Value of 7 instruments at day t: (2, -3, 5, 6, 3, NaN, -10)
Output: (1, -1, 1, 1, 1, NaN, -1)

### `signed_power`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `signed_power(x, y)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/signed_power

x raised to the power of y such that final result preserves sign of x

### `sqrt`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `sqrt(x)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/sqrt

Returns the non-negative square root of x. Equivalent to power(x, 0.5). Note: for x < 0 the result is undefined; to retain the sign of x, use signed_power(x, 0.5) instead.

### `subtract`

- Category: Arithmetic
- Level: ALL
- Scope: REGULAR
- Definition: `subtract(x, y, filter=false), x - y`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/subtract

Subtracts inputs left to right: x ? y ? … Supports two or more inputs. Set filter=true to treat NaNs as 0 before subtraction.
