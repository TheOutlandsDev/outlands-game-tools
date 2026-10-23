# Original toy PAKs

[create_example.py](create_example.py) creates three original binary fixtures in
a new ordinary local directory outside the downloaded source tree. Only its
Python source is distributed; no `.pak` or game asset is checked into this repo.
Follow the [PowerShell/POSIX walkthrough](../README.md#try-original-generated-archives).

| Pair | Expected complete result |
|---|---|
| `base.pak` + `mod.pak` | Exit 2: four entries, three unique paths, one overlap at `toy/content/shared.uasset`. |
| `base.pak` + `clean.pak` | Exit 0: three entries and three disjoint paths. |

Base and mod use different mount/entry splits for the same combined virtual
path. Their shared-name payloads are different original placeholder text; the
inspector never reads or compares that text. Clean demonstrates wide-encoded
ASCII strings and standard compressed-block metadata without decompression.

The builder is a small fixture generator, not a production UnrealPak replacement
or proof of game-loadable assets. It creates no valid meshes or cooked packages.
It refuses existing destinations, retains partial output on I/O failure for
inspection, and performs no automatic cleanup. Remove only your own generated
demo directory with your file manager when finished.

Code and original toy content use the root [MIT license](../../../LICENSE).
User-supplied archives and reports retain their own rights/privacy requirements.
