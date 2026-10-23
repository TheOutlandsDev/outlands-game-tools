# DayZ Market Numeric Diff — Python library

Compare the numeric fields of two already-selected market categories, then
preview a chosen change list against exact baseline bytes. This original
standard-library module is available under the collection's [MIT license](../../LICENSE).

It is a Python library, with no command-line installer. It reads no files,
uploads nothing and writes no configuration. Examples and tests are fictional;
no game, server, mod, item database or private recovery recipe is included.

## Quick example

Use Python 3.12 or newer. From the repository root:

```text
python -B tools/dayz-market-numeric-diff/examples/demo.py
python -B -m unittest discover -s tools/dayz-market-numeric-diff -p test_numeric_delta.py -v
```

The example changes one synthetic item's maximum stock from 1 to 50. A second
item also starts at 1 and remains unchanged. The result contains one indexed
operation, rather than a global replacement that would change both items.
The preview remains in memory; no output file is created.

From this tool directory, the same API can be used directly:

```python
import copy
import hashlib
from numeric_delta import load_market, derive_numeric_changes, preview_exact_baseline

raw = b'{"Items":[{"ClassName":"Synthetic_A","MaxStockThreshold":1}]}'
before = load_market(raw)
after = copy.deepcopy(before)
after['Items'][0]['MaxStockThreshold'] = 50

result = derive_numeric_changes(before, after)
preview = preview_exact_baseline(raw, hashlib.sha256(raw).hexdigest(), result['operations'])
assert preview['Items'][0]['MaxStockThreshold'] == 50
print(result)
```

An emitted operation has this form:

```json
{"op":"set_existing_numeric_field","pointer":"/Items/0/MaxStockThreshold","before":1,"after":50}
```

## APIs and supported fields

`load_market(raw_bytes)` parses bounded UTF-8 JSON, optionally with a UTF-8 BOM.
It rejects duplicate keys, nonfinite numbers, unsupported structure and resource
limits. The category must be an object containing an `Items` array.

`derive_numeric_changes(before, after)` accepts two JSON-compatible objects. It
returns only changed finite numeric fields in this fixed subset:

| Location | Fields |
| --- | --- |
| Category | `InitStockPercent`, `IsExchange` |
| Item | `MaxPriceThreshold`, `MinPriceThreshold`, `SellPricePercent`, `MaxStockThreshold`, `MinStockThreshold`, `QuantityPercent` |

Item operations require the same textual `ClassName` at the same array position
in both observations. Added, removed or differently identified positions are
counted as held; their objects are not emitted. ClassName, variants, attachments,
inherited display text and whole item objects are omitted from the result.
This fixed field set is not a general JSON diff or a complete mod compatibility
check. Missing/new numeric fields and changes outside the subset stay unselected.

`unselected_differences_present` reports whether the reconstructed parsed object
still differs from the after-observation. `numeric_replay_matches_complete_observation`
reports the inverse. JSON booleans are distinct from numbers, including in nested
unselected data. These flags assess parsed values, not source formatting.

`preview_exact_baseline(raw, expected_sha256, operations)` requires a lowercase
SHA-256 of the exact before-bytes and every recorded old scalar. It rejects
different bytes, duplicate assignments, unsupported operations/pointers, missing
fields and invalid numeric values, returning only an in-memory object.
An item index cannot safely be transplanted to another template or ordering.
Do not treat a complete numeric replay as a complete configuration backup:
the matching external baseline is still required.

## Limits and validation

- Raw input: 1,000,000 bytes; JSON trees: depth 64, 100,000 nodes and 1,000,000
  text characters per object API input. Cycles and unsupported Python objects
  are rejected. Operation lists are capped at 20,000 entries.
- Integers use Python integer semantics. Decimal/exponent tokens use Python
  floats: rounding and underflow can hide decimal-token differences. Integer
  and float representations of the same numeric value compare equally. This
  is parsed-value comparison, not exact decimal-token preservation.
- This module provides no path/link/race checks for a caller's file acquisition,
  secret scanning, automatic redaction, template licensing, schema-version
  migration, game loading, installation or filesystem output.
- Twenty-three synthetic tests passed locally on Windows. The source-check
  workflow also schedules these tests on Windows/Ubuntu with Python 3.12/3.13.
  Current run results are in the repository Actions tab; gameplay is untested.

The publication revision fixes two early helper edge cases: numeric/boolean
equality and exponent overflow. It also bounds object trees and rejects cycles.
See [source provenance](PROVENANCE.md). Preview only data and dependencies you
are entitled to use, and review derived records before sharing them; omitting
item objects does not guarantee that numeric settings are non-sensitive.

## Suggestions and bugs

[Suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
or [report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml).
Include a small fictional before/after example, Python version, expected result
and actual result. Keep real server files, player/account information, credentials
and private recovery records out of public issues. No coding contribution is
required to leave a useful suggestion.
