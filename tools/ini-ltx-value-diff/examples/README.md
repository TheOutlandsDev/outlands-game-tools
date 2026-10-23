# Original toy file pairs

Run [create_example.py](create_example.py) with `--destination NEW_DIRECTORY`
outside the downloaded repository and game folders. The parent must exist and be
an ordinary local directory. The generator refuses existing destinations and
creates only original UTF-8 text: `before.ini`, `after.ini`, `before.ltx`,
`after.ltx`. They are not actual game configurations.

Follow the [PowerShell and POSIX commands](../README.md#try-original-examples-first).
Both pairs return complete review exit **2**:

| Pair | Expected changes |
|---|---|
| INI | 1 added key, 2 removed keys, 2 changed keys, 3 unchanged keys; no section changes. |
| LTX | 1 changed parent list, 1 added key, 1 removed key, 1 changed key, 4 unchanged keys. |

The INI pair demonstrates globals, an ordinary `[DEFAULT]` section, an empty
value disappearing, and inert quoted `%`/`${...}` text. The LTX pair demonstrates
ordered parent context, a direct mesh-like string change, semicolon comments
outside double quotes and a quoted literal semicolon. No parent values are merged.

Use `--include-values` only when intentionally exporting values from a pair you
may share. Default reports contain fingerprints/lengths and visible metadata.
Reports need new output names on every run. Comparing either supported input to
itself returns exit **0**. Changing a toy file to include an unsupported include
directive produces incomplete exit **1**, not a game diagnosis or equality claim.

The generator does not delete partial output after an I/O failure; inspect its
new toy directory. Remove only your own generated demo with a file manager when
finished. Tests and examples modify no installed game, mod, save or profile.

The original generator and examples use the collection's [MIT license](../../../LICENSE).
