# Release preparation checks

## Unreleased v0.1.1-rc.1 review candidate

This is an unreleased review candidate based on the original v0.1.0 tag, not current
main. The scope is the source-inventory portability correction and its tests,
manifest and documentation. The 11 standalone utility implementations and SPT
sources are retained; the seven later main-branch utilities are not included.
No candidate GitHub tag, release or release-asset download has been published.

### First review-branch CI checkpoint

Review revision `c6af1509f60b0bdff25a208ece72bb61115bd998` completed all
**17 jobs** successfully in [run 40008430058](https://github.com/TheOutlandsDev/outlands-game-tools/actions/runs/40008430058):
nine Windows jobs and eight Ubuntu jobs, including Python 3.12/3.13 matrices.
The Windows Server 2025 source job passed all 19 publication-gate tests and the
176-record inventory check. Its full source build read back all 177 members.

That CI build uses the generic `outlands-game-tools-source` archive prefix; its
1,328,018-byte ZIP had SHA-256
`3d1784b58cefbe886c1515f5a3d81aac33d34c67e5c50d9b66d025b81942e137`,
matching the independently derived generic-prefix package for that revision.
It is not the checksum of the differently prefixed candidate release ZIP.
Case-collision fixtures have explicit Windows filesystem skips; passing jobs do
not imply every fixture ran. CI installs the separately pinned Lua/audio wheels
on hosted runners and is distinct from the local offline checks below.

This checkpoint applies only to the exact revision named above. Later source or
documentation changes require their own checks; consult the final review receipt
for the current CI head and candidate ZIP identity. No game or production
acceptance is established by these synthetic CI checks.

The unchanged v0.1.0 package exposed an ordering defect on Linux: its checker
compared a POSIX-sorted Path list with the manifest's Windows-sorted record
list. All 176 path/byte-count/SHA-256 records agreed exactly, but list order
caused a false mismatch. The original custom ZIP was independently reproduced
byte for byte: 177 members, 1,315,397 bytes, SHA-256
`90653639397e82375f0f4548da4a76c161df46b992fc8ca980c189e1df78e4b4`.
The original asset and extracted source were preserved.

The candidate writes inventories in explicit relative POSIX-path string order
and accepts legacy ordering without rewriting it. It compares full records by
exact unique path. Duplicate paths or JSON fields, invalid schemas/record shapes
and non-integer lengths are refused; hashes and byte counts remain exact.

- Candidate publication gate: **19 collected, 19 passed, zero skipped** on
  Linux with Python 3.12.14. Twelve new regressions cover canonical writing,
  reversed/shuffled/Windows-ordered legacy inventories, duplicate records and
  JSON fields, changed hashes/lengths, strict schemas and exact integer lengths.
  The seven prior gate tests remain included. Fixtures are original temporary
  source trees; no game, real profile, service or installed dependency was used.
- Separately, the unmodified released Mod Content Manifest & Diff and Source
  Release Builder suites collected **44 and 56** cases respectively: **43 and
  55 passed**, with one Windows-only junction skip in each suite on Linux.
- A separate fresh run of six existing released utility suites collected
  **188 cases: 185 passed and three Windows-only cases skipped**. These are
  results for the unchanged v0.1.0 utilities, not a complete candidate CI run.
- The original release revision's [17-job CI run](https://github.com/TheOutlandsDev/outlands-game-tools/actions/runs/39875896673)
  passed at commit `edabafcc4e71bf998841cc151b279eef9038e060`. That is historical
  v0.1.0 evidence; it does not establish CI results for this unpublished candidate.

The candidate inventory, newly built local ZIP/checksum and unpacked inventory
must be checked after the source and manifest review. Detailed local receipts
remain outside the candidate source tree. This correction does not establish
macOS support, game compatibility, runtime performance, restoration, licensing
ownership or complete secret absence.

## Historical v0.1.0 preparation record

The retained Windows notes below describe the original preparation environment
and its own test/skip populations; they are not new candidate execution claims.

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

- Mod Content Manifest & Diff 1.0.0: 44 generated-fixture black-box tests on
  Windows Python 3.12.7; 40 passed and 4 case/symlink/junction fixtures were
  explicitly skipped because the review filesystem/account could not create
  them. Coverage includes streamed byte hashing, privacy exclusions, native MO2
  priority, separator/hidden-directory handling, base/overwrite-only profiles,
  virtual file/directory collisions, strict imported JSON/schema/hash/path checks,
  compatible selection policies, equal-byte provider changes, incomplete status,
  exclusive output, input immutability and metadata/depth/report limits. Original
  examples produced the expected one added, one removed, one changed and one
  identical path; the MO2 example found three effective files and one overlap.
  No game files, live MO2 VFS, archive extraction or multiplayer was exercised.
- Source Release Builder 1.0.0: 56 generated-fixture tests on Windows Python
  3.12.7; 51 passed and 5 native link/junction fixtures were explicitly skipped
  because the sandbox denied creation. Coverage includes canonical manifest
  validation, duplicate JSON/path/case/prefix/depth rejection, source type/license
  checks, byte/hash mismatch, unchanged inputs, exclusive ZIP/checksum outputs,
  interrupted/changed-source failure cleanup, exact stored ZIP members and
  deterministic bytes. The original example created four archive members from
  three listed toy source files plus its exact manifest; unlisted source was
  excluded and repeat builds matched. No game folder or compiled payload used.
  The source CI job also builds/verifies the complete collection archive after
  its source gate, using only manifest-selected records. These checks do not
  establish authorship, legal rights, secret absence or game/runtime compatibility.
- LTX Definition Inspector 1.0.0: 40 generated-fixture tests on Windows
  Python 3.12.7; 37 passed and 3 case/junction fixtures were skipped because
  the local filesystem/sandbox could not create them. Tests cover supported
  includes/declarations, ordered parent records, missing/duplicate/cyclic
  references, unsafe paths, encodings, unsupported DLTX/syntax, source
  immutability, byte/file/depth/record/directory/report limits and exclusive
  reports. Fictional examples return clean/review/incomplete exits 0/2/1.
  Independent stress review exposed cycle-report expansion; fixed element,
  encoded-character and streaming JSON bounds now stop dense/long-name graphs
  with an incomplete report. Windows/Ubuntu Python 3.12/3.13 CI uses generated
  configurations only. No full LTX/DLTX loader, value resolution, game configuration
  dump, real profile or game runtime was tested.
- X-Ray Log Summary 1.0.0: 35 black-box tests on Windows Python 3.12.7;
  33 passed and 2 native link checks were skipped because the local review
  sandbox could not create them. Tests cover known category counts/markers,
  no source-text or identifier disclosure, malformed encoding, byte/line caps,
  late findings, repeated-input refusal, source stability, exclusive output,
  original example logs and platform link guards. Windows CI requires its native
  junction fixture to run. The Windows/Ubuntu Python 3.12/3.13 matrix uses only
  generated logs; no real player logs, game behavior or multiplayer was tested.
- MO2 Baseline Profile Builder 1.0.0: 42 generated-fixture tests on Windows
  Python 3.12.7; 38 passed and 4 native symlink/junction checks were skipped
  because the local review account could not create them. Coverage includes
  zero-write previews, exact marker changes, BOM/newline preservation, source
  immutability, fixed file selection, exclusive output, unsafe paths, late source
  changes, injected copy/write failures and owned-file rollback preserving foreign
  files. The original example generator and malformed-argument privacy were also
  tested. Portability CI runs Windows/Ubuntu with Python 3.12/3.13. No installed
  MO2 instance/game was used; no runtime save compatibility is established.
- Save Snapshot Verifier 1.0.0: Windows Python 3.12.7 validation collected
  29 tests; 26 passed and 3 case/link fixture checks were skipped because this
  filesystem/account could not create them. Checks cover multi-source and
  multi-chunk copy/hash preservation, malformed/traversal manifests, changed/
  missing/extra files, exclusive reports, path/size guards, injected disk failure
  and mid-copy source membership changes. Only generated toy files were used.
  Portability CI exercises Windows/Ubuntu and Python 3.12/3.13. No real saves,
  game-format validity, automatic restoration or crash-safe durability was tested.
- Audio Integrity Checker 1.0.0: 35 black-box CLI tests collected on Windows
  with Python 3.12.7, SoundFile 0.13.1, NumPy 2.2.6 and libsndfile 1.2.2;
  33 passed and 2 link fixture checks were skipped because this review
  environment could not create directory/file links. Actual generated WAV,
  OGG/Vorbis, FLAC and AIFF decoding was required rather than silently skipped.
  Coverage includes empty/non-finite audio, limits, sanitized metadata/errors,
  hashes and unchanged input bytes, MO2 winners, hidden files, incomplete/error
  exits, output guards and missing dependencies. The original source example
  produced one pass, one decode error and one empty-audio anomaly; its MO2
  example selected two valid winners from four copies. All nine example input
  files remained unchanged. A separate generated scan checked 259 files,
  including a stereo WAV spanning multiple decode blocks and SHA-256 chunks;
  all passed, hashes matched and input bytes remained unchanged. Its observed
  0.828-second run is a single local measurement, not a performance promise.
  Seven publication-gate tests passed, Python syntax and workflow YAML parsed,
  and CI exercises Windows/Ubuntu with Python 3.12/3.13 and separate dependency
  wheels. No game audio, playback, actual game/MO2 instance, native decoder
  sandbox or game-engine compatibility was tested. See the
  [module guide](tools/audio-integrity-checker/README.md) for scope and limits.
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
