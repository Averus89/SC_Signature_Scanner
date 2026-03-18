# Ship Signature Test Data

## Ship Under Test

| Field | Value |
|---|---|
| Ship model | |
| Ship size (CIG) | |
| Ship role/class | |
| SC version | 4.7 |
| Test date | |
| Tester | |

---

## Scan Results

| # | Scan Angle | IR | EM | CS | Notes |
|---|---|---|---|---|---|
| 1 | Front (nose-on) | | | | |
| 2 | Side (90° beam) | | | | |
| 3 | Above (dorsal) | | | | |
| 4 | Rear (tail-on) | | | | |
| 5 | 45° front-side | | | | |
| 6 | 45° top-side | | | | |
| 7 | Cold ship (engines off) | | | | same angle as #2 |
| 8 | Hot ship (engines on) | | | | same angle as #2 |

---

## Derived Values

| Metric | Value | Formula |
|---|---|---|
| CS min | | lowest CS across all angles |
| CS max | | highest CS across all angles |
| CS range | | max − min |
| EM baseline | | EM cold (row 7) |
| EM active | | EM hot (row 8) |
| IR baseline | | IR cold (row 7) |
| IR active | | IR hot (row 8) |
| EM/CS ratio | | EM ÷ CS (hot) |
| IR/CS ratio | | IR ÷ CS (hot) |

---

## Repeat With a Second Ship (different size class)

| Field | Value |
|---|---|
| Ship model | |
| Ship size (CIG) | |

| # | Scan Angle | IR | EM | CS | Notes |
|---|---|---|---|---|---|
| 1 | Front (nose-on) | | | | |
| 2 | Side (90° beam) | | | | |
| 3 | Above (dorsal) | | | | |
| 4 | Rear (tail-on) | | | | |
| 5 | Cold ship | | | | same angle as #2 |
| 6 | Hot ship | | | | same angle as #2 |

---

## Observations

_Fill in after testing:_

- Do CS values cluster clearly by size class?
- Does EM/IR stay constant across scan angles?
- How much does engine state shift EM/IR?
- Do the two ships have clearly separated CS ranges, or do they overlap?
