# Logical Operators

Source: https://api.worldquantbrain.com/operators
Captured: 2026-08-03

| Name | Level | Scope | Definition | Documentation |
|---|---|---|---|---|
| `and` | ALL | REGULAR | `and(input1, input2)` |  |
| `equal` | ALL | REGULAR | `input1 == input2` |  |
| `greater` | ALL | REGULAR | `input1 > input2` |  |
| `greater_equal` | ALL | REGULAR | `input1 >= input2` |  |
| `if_else` | ALL | REGULAR | `if_else(input1, input2, input 3)` | [/operators/if_else](https://platform.worldquantbrain.com/learn/operators/operators/if_else) |
| `is_nan` | ALL | REGULAR | `is_nan(input)` | [/operators/is_nan](https://platform.worldquantbrain.com/learn/operators/operators/is_nan) |
| `less` | ALL | REGULAR | `input1 < input2` |  |
| `less_equal` | ALL | REGULAR | `input1 <= input2` |  |
| `not` | ALL | REGULAR | `not(x)` |  |
| `not_equal` | ALL | REGULAR | `input1!= input2` |  |
| `or` | ALL | REGULAR | `or(input1, input2)` |  |

## Details

### `and`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `and(input1, input2)`

Returns 1 ('true') if both inputs are 1 ('true'). Otherwise, returns 0 ('false').

### `equal`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `input1 == input2`

Returns 1 ('true') if input1 and input2 are the same. Otherwise, returns 0 ('false').

### `greater`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `input1 > input2`

Returns 1 ('true') if input1 is a larger than input2. Otherwise, returns 0 ('false').

### `greater_equal`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `input1 >= input2`

Returns 1 ('true') if input1 is a larger or the same as input2. Otherwise, returns 0 ('false').

### `if_else`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `if_else(input1, input2, input 3)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/if_else

The if_else operator returns one of two values based on a condition. If the condition is true, it returns the first value; if false, it returns the second value.

### `is_nan`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `is_nan(input)`
- Documentation: https://platform.worldquantbrain.com/learn/operators/operators/is_nan

If (input == NaN) return 1 else return 0

### `less`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `input1 < input2`

Returns 1 ('true') if input1 is a smaller than input2. Otherwise, returns 0 ('false').

### `less_equal`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `input1 <= input2`

Returns 1 ('true') if input1 is a smaller or the same as input2. Otherwise, returns 0 ('false').

### `not`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `not(x)`

Returns the logical negation of x. Returns 0 when x is 1 (‘true’) and 1 when x is 0 (‘false’).

### `not_equal`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `input1!= input2`

Returns 1 ('true') if input1 and input2 are different numbers. Otherwise, returns 0 ('false').

### `or`

- Category: Logical
- Level: ALL
- Scope: REGULAR
- Definition: `or(input1, input2)`

Returns 1 if either input is true (either input1 or input2 has a value of 1), otherwise it returns 0.
