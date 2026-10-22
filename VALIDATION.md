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
