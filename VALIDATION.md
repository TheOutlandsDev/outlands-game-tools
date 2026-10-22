# Release preparation checks

Prepared on Windows, 2026-10-22. The installed games and original project sources
were not modified. Private source-hash receipts remain outside the release tree.

## SPT

- Nine C# projects compiled against locally installed references, with zero
  warnings and errors. No external package downloads or game/server launches.
- Codex Diagnostics and QuakeBrain summarizers passed synthetic regression
  checks in PowerShell 7 and Windows PowerShell 5.1.
- Fika helpers passed synthetic preview, WhatIf, configuration backup/update,
  plugin move, unsafe-path/input and overlapping-root checks in both PowerShell
  versions. The third-party installer was never run.
- Scav Life Console passed 24 offline URL/request-policy checks. JavaScript
  syntax and PowerShell parsing passed. No listener or backend was started.
- Independent cross-review covered build/install paths and console/framework
  request/mutation guards. A CSV formula-injection issue in the inventory utility
  was fixed and received a regression test.
- Five publication-gate regression tests passed: altered/new source, binaries,
  credential/private-path markers, private endpoints, and excluded build output.

Some SDK discovery calls cannot read the Windows SDK registry in the review
sandbox. Compilation used explicit installed targeting paths or SDK discovery
environment overrides. No game or system installation was changed to do this.

## Standalone utilities

- Lua Syntax Checker 1.0.0: 27 black-box CLI tests collected on Windows with
  Python 3.12.7 and an existing isolated Lupa 2.8 runtime; 24 passed and 3 link
  fixture tests were skipped because the review environment could not create
  symbolic links (two checks) or a junction. Tests exercised all three selected
  VMs, bytecode/NUL refusal, BOM/hash accounting, private parser-error handling,
  MO2 winners, immutable input bytes, incomplete/error exits, output guards and
  invalid size limits. Runtime-error, file-write, missing-module and infinite-loop
  source fixtures compiled without executing their chunks. The original source
  example produced two passes and one intentional syntax error on all three VMs;
  its MO2 example selected four valid winners from eight candidate copies.
  A separate synthetic scan compiled 1,001 scripts, including a long comment,
  with unchanged input bytes. Its observed 1.781-second run is one local
  measurement, not a performance guarantee. Seven publication-gate tests passed,
  including requirements-path and virtual-environment exclusion checks.
  CI exercises the checker on Windows/Ubuntu with Python 3.12/3.13 and separately
  installed Lupa wheels. No parser binaries are in the source package, and no
  real game/MO2 installation or engine transformations were tested. See the
  [module guide](tools/lua-syntax-checker/README.md) for the exact scope.
- MO2 Conflict Inspector 1.0.0: 33 black-box CLI tests collected on Windows with
  Python 3.12.7; 28 passed and 5 were skipped because this review environment
  could not create case-colliding names, symbolic links (two checks), a hardlink,
  or a junction. The remaining tests covered priority/overwrite winners,
  effective-file parsing, incomplete scans, privacy, exclusive output, Windows
  device/stream path refusal, overlapping roots and unchanged input bytes.
  Its original worked example produced the expected five findings; repeated
  reports matched and all ten fixture input hashes remained unchanged.
  A separate synthetic scan of 150 providers and 4,502 loose files found the
  expected 30 overlaps and preserved all input bytes. This included large
  unmatched-bracket and repeated-declaration parser inputs. Its observed
  0.906-second scan is a single local measurement, not a performance promise.
  Five source-publication gate tests also passed after integration. CI exercises
  the inspector fixtures on Windows/Ubuntu with Python 3.12/3.13; platform fixture
  skips remain visible in the job logs. No real MO2/game installation or virtual
  filesystem was exercised for this source release. See the
  [module instructions](tools/mo2-conflict-inspector/README.md) for coverage limits.
- Game Folder Inventory: eight synthetic tests passed, including a native Windows
  junction check with normal permissions. One native symlink test was skipped
  because this account could not create that fixture.
  Coverage includes filtered/private filenames, relative reports, CSV formula
  neutralization, overwrite refusal, output-subtree exclusion, invalid paths and
  size filtering. Native symlink handling still needs a suitable Windows account.
- Process Exit Observer: five synthetic lifecycle checks passed, including
  retained exit code, waiting timeout, run timeout leaving the fixture alive,
  independent snapshots and observation-only state. Only short-lived Python
  fixture processes were started.

## Remaining validation

Actual gameplay, raids, multiplayer/Fika interoperability, runtime performance,
real profile mutations, dashboard UI operation and the third-party headless
installer were not tested. Scav Life is a trusted-local prototype; it does not
provide independent backend authorization or an internet-facing service.

The content scan is a bounded publication check, not a complete security audit.
External dependencies and their compatibility/licenses require separate review
for any future binary distribution. No whole-game archive is part of this release.
