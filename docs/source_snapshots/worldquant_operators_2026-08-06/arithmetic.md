# Arithmetic Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-06

## `abs`

- **Definition**: `abs(x)`
- **Description**: Returns the absolute value of a number, removing any negative sign.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/abs

## `add`

- **Definition**: `add(x, y, filter = false), x + y`
- **Description**: Adds two or more inputs element wise. Set filter=true to treat NaNs as 0 before summing.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/add

## `densify`

- **Definition**: `densify(x)`
- **Description**: Converts a grouping field of many buckets into lesser number of only available buckets so as to make working with grouping fields computationally efficient
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/densify

## `divide`

- **Definition**: `divide(x, y), x / y`
- **Description**: Returns x divided by y (x / y). Note: dividing by zero raises an error; to avoid it, use divide(x, add(y, 0.0001)); adding a small epsilon to the denominator prevents divide-by-zero errors.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com

## `inverse`

- **Definition**: `inverse(x)`
- **Description**: Returns the reciprocal of x (1 / x). Note: errors when x = 0; to avoid it, use inverse(add(x, 0.0001)); adding a small epsilon prevents divide-by-zero errors.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com

## `log`

- **Definition**: `log(x)`
- **Description**: Calculates the natural logarithm of the input value. Commonly used to transform data that has positive values.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/log

## `max`

- **Definition**: `max(x, y, ..)`
- **Description**: Maximum value of all inputs. At least 2 inputs are required
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/max

## `min`

- **Definition**: `min(x, y ..)`
- **Description**: Minimum value of all inputs. At least 2 inputs are required
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/min

## `multiply`

- **Definition**: `multiply(x ,y, ... , filter=false), x * y`
- **Description**: Multiplies two or more inputs element wise. Set filter=true to treat NaNs as 0 before multiplication
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/multiply

## `power`

- **Definition**: `power(x, y)`
- **Description**: Returns x raised to the power of y (x ^ y). Note: power(x, y) can drop the sign of x when y is non-integer; use signed_power(x, y) to preserve the sign of x.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/power

## `reverse`

- **Definition**: `reverse(x)`
- **Description**:  - x
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com

## `sign`

- **Definition**: `sign(x)`
- **Description**: Returns the sign of a number: +1 for positive, -1 for negative, and 0 for zero. If the input is NaN, returns NaN.

Input: Value of 7 instruments at day t: (2, -3, 5, 6, 3, NaN, -10)
Output: (1, -1, 1, 1, 1, NaN, -1)
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/sign

## `signed_power`

- **Definition**: `signed_power(x, y)`
- **Description**: x raised to the power of y such that final result preserves sign of x
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/signed_power

## `sqrt`

- **Definition**: `sqrt(x)`
- **Description**: Returns the non-negative square root of x. Equivalent to power(x, 0.5). Note: for x < 0 the result is undefined; to retain the sign of x, use signed_power(x, 0.5) instead.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/sqrt

## `subtract`

- **Definition**: `subtract(x, y, filter=false), x - y`
- **Description**: Subtracts inputs left to right: x ? y ? … Supports two or more inputs. Set filter=true to treat NaNs as 0 before subtraction.
- **Level**: ALL
- **Scope**: REGULAR
- **Documentation**: https://platform.worldquantbrain.com/operators/subtract
