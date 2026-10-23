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

- Bounded Evidence Manifest Verifier (2026-10-23): Linux WSL Python 3.10.12
  passed 18 of 19 synthetic cases, with one Windows-only rejection check skipped.
  All 16 original verifier cases passed and their test bodies remain unchanged.
  Windows Python 3.12 passed three platform-rejection cases and explicitly
  skipped the 16 POSIX file-verification cases; those skips do not validate
  native Windows hashing. The included fictional example passed on Linux, and
  both example files remain byte-identical to the reviewed original archive.
  The standalone CI matrix includes the suite on Windows/Ubuntu Python 3.12/3.13.
  Linux verification is the supported use; other POSIX systems remain unverified.
  No actual evidence, game files or private data was used. Matching supplied
  hashes does not authenticate the manifest, prove custody or detect extra files.

- .NET Assembly Inspector 1.0.0 (2026-10-23): local Windows synthetic integration
  tests build only this standalone helper and original authored fixture source
  with the .NET 9.0.310 SDK and Python 3.12. All 19 cases passed, including
  malformed user-string framing, a well-formed oversized decoded value and
  JSON expansion beyond the output limit without partial stdout. Inspected
  test fixtures are read as PE data without assembly loading or entry-point execution. No
  actual game/vendor assembly, dependency package, private metadata dump or
  game runtime was used. Windows/Ubuntu CI builds and runs the same original
  fixtures; Linux execution remains unverified at this local stage.

- Game Session Evidence Auditor 1.0.0 (2026-10-23): 43 original synthetic
  cases on Windows Python 3.12.14; 41 passed and 2 native symlink/junction
  fixtures explicitly skipped because local creation is denied. Covers binary
  streaming hashes, size/hash changes, missing files/receipts, schema trust
  gating, session/process/executable/time/exit consistency, privacy omissions,
  strict paths/JSON, resource limits, concurrent changes and exclusive external
  reports. The rejected in-evidence report path is tested to create no file.
  A private deterministic review passed 2,201 additional cases: schema byte
  mutations, 100 independent binary-hash oracles, 100 receipt-pair truth checks
  and a maximum 1,002-file selection producing a bounded report below 0.4 MiB.
  Original clean/changed/missing/inconsistent examples return exits 0/2/2/2.
  Windows/Linux Python 3.12/3.13 CI runs the same suite with declared native
  fixture skips where unavailable. No game/process was launched, observed or
  validated; no installed profile, save, log or AGPL implementation was modified
  or incorporated. Hash/receipt agreement is not gameplay/authenticity evidence.

- Offline Mod Dependency Rule Checker 1.0.0 (2026-10-23): 42 original
  synthetic cases on Windows Python 3.12.14; 40 passed and 2 native symlink/
  junction fixtures explicitly skipped because local creation is denied.
  Covers direct requires/conflicts/order semantics, separate inactive/active
  catalog context, cycle groups/witnesses, self rules, duplicate/unknown fields,
  strict JSON/depth/encoding, resource ceilings, input preservation and guarded
  exclusive reports. Independent reachability checks all 512 three-name directed
  graphs, including self edges, and verifies each witness against authored edges;
  100 seeded direct-evaluation cases and a 1,500-name chain/cycle also pass.
  A private review passed 2,102 additional mutation/resource/mixed-graph cases,
  including 100 independent mixed-graph oracles and a 10,000-rule/10,000-name
  cycle. The maximum-cycle report stayed below 4.1 MiB; an actual CLI Unicode
  expansion case hit the fixed report ceiling and returned sanitized incomplete
  JSON with no inventories. Generated clean/review examples return exits 0/2.
  Windows/Linux Python 3.12/3.13 CI runs the same suite, declaring unavailable
  native fixtures. No game installation, manager, profile or compatibility
  database was accessed, changed or validated. No runtime compatibility claim.

- MO2 Profile Change Report 1.0.0 (2026-10-23): 43 original synthetic cases
  on Windows Python 3.12.14; 41 passed and 2 native symlink/junction fixtures
  explicitly skipped because local creation is denied. Covers added/removed
  mods, enablement, casefold spelling, shared relative ordering, separator
  relocation/markers, foreign entries, duplicates, strict names/encoding, BOM
  and line endings, input preservation, exclusive reports and resource limits.
  An independent pairwise oracle checks all 120 permutations of five names and
  100 seeded mixed selections. Generated changed/identical comparisons return
  exits 2/0; actual output-limit failure returns a small incomplete report.
  Windows/Linux Python 3.12/3.13 CI runs the same suite, declaring unavailable
  native fixtures. No live MO2 instance, installed profile, plugin load order,
  game content or runtime compatibility was inspected or altered.
  A private deterministic review also passed 2,002 mutation/resource cases
  against the same parser source hash: two identical 10,000-entry inventories
  produced a bounded approximately 3.1 MiB report, and a long-name toggle report
  hit the actual fixed output ceiling with a controlled incomplete result.

- Mod Package ZIP Layout Inspector 1.0.0 (2026-10-23): 47 original
  generated-fixture cases on Windows Python 3.12.14; 45 passed and 2 native
  symlink/junction fixtures explicitly skipped because local creation is denied.
  Covers stored/deflated ZIP32, signed/unsigned descriptors, empty/commented
  archives, portable path/case/NFC/prefix collisions, local/central mismatches,
  unsafe names, declared size/ratio observations, unsupported ZIP64/flags,
  malformed ranges/extras, read/report/accounting limits and exclusive output.
  A read-region spy confirms payload ranges are skipped except the bounded
  end-record search; deliberate payload corruption leaves the metadata verdict
  unchanged. Generated clean/wrapper/review examples return 0/2/2. Windows/Linux
  Python 3.12/3.13 CI exercises the same suite, with native link skips declared
  where unavailable. No extraction, installation, malware scan or gameplay test.
  An additional private deterministic review passed 2,225 truncation, mutation,
  reordered-directory and maximum-entry stress cases against the same parser
  source hash. A 10,000-member original archive produced a bounded approximately
  3 MiB report. This exercises metadata handling, not payload authenticity.

- Unreal PAK Index & Conflict Inspector 1.0.0 (2026-10-23): 45 original
  generated-fixture cases on Windows Python 3.12.14; 42 passed and 3 native
  hardlink/symlink/junction fixtures were explicitly skipped because the local
  sandbox denied creation. Tests cover standard-v3 index metadata/checksums,
  mount joining and ASCII case matching, path and file/directory overlaps,
  malformed strings/counts/ranges/flags, compressed block assertions, read
  regions, source preservation, exclusive reports and resource ceilings.
  An additional 376 generated truncation/mutation/property cases passed against
  the same source hash, including a 10-archive/200-entry overlap oracle.
  Only index/footer regions are requested by the inspector; deliberate local
  header/payload changes leave metadata-only reports unchanged. The original
  worked pairs return complete overlap/disjoint exits 2/0. Windows/Ubuntu
  Python 3.12/3.13 CI uses original generated archives only. No real PAK,
  payload decoding/hash validation, extraction, decryption, load order, game
  compatibility or runtime behavior was tested; macOS remains unverified.
  Standard unencrypted version 3 is the only supported layout. See the
  [module guide](tools/unreal-pak-inspector/README.md) for exact limits.
- INI/LTX Configuration Value Diff 1.0.0 (2026-10-23): 47 original
  generated-fixture cases on Windows Python 3.12.14; 45 passed and 2 native
  symlink/junction fixtures were explicitly skipped because the local sandbox
  denied creation. Tests cover literal section/key changes, empty values,
  ordered LTX parent context, globals and ordinary DEFAULT sections, case and
  duplicate-key policies, comments/quotes, independent strict encodings,
  fingerprints and opt-in values, source preservation, error locations,
  exclusive output and resource bounds. Independent generated review passed
  82 additional CLI cases against the same source hash. Per-parent accounting
  and a fixed parent-count ceiling bound large declarations before retention;
  unsupported syntax and limits clear partial differences. Original INI and
  LTX examples return complete difference exit 2; no settings are evaluated,
  includes loaded or inherited/default values materialized. Windows/Ubuntu
  Python 3.12/3.13 CI exercises generated inputs only. No actual game config,
  mod pack, MO2 VFS or runtime settings behavior was tested; macOS remains
  unverified. See the [module guide](tools/ini-ltx-value-diff/README.md).
- Mod Asset Reference Checker 1.0.0: 52 original generated-fixture cases on
  Windows Python 3.12.14; 48 passed and 4 native link/case fixtures were
  explicitly skipped because this filesystem/account could not create them.
  Tests cover literal file mappings, selected section declarations, contained
  include graphs, encoding, strict asset-path indexes, uncertain versus
  caller-attested coverage, case ambiguity, input preservation, privacy,
  exclusive reports and file/directory/metadata limits. Independent review
  passed 56 additional generated CLI cases and 6 focused path/resource checks,
  including simulated casefold aliases and deeply branching index bookkeeping.
  The original worked example returns complete review exit 2 with one loose
  file, one unresolved reference and one selected section; the supplied toy
  index resolves its asserted name for exit 0. Declaring complete asset coverage
  instead reports one absence within that declared coverage for exit 2. All
  three generated input files stayed unchanged. Windows/Ubuntu Python 3.12/3.13
  CI exercises generated inputs only. No asset payload is read by the checker;
  no game assets, archives, live MO2 VFS, inherited/effective values or game
  runtime were tested. macOS remains unverified. See the
  [module guide](tools/mod-asset-reference-checker/README.md) for exact scope.
- XML Mod Configuration Diff 1.0.0: 57 original generated-fixture cases on
  Windows Python 3.12.14 with Expat 2.8.3; 55 passed and 2 native symlink/junction
  fixtures were explicitly skipped because the local sandbox denied creation.
  Tests cover exact change records/fingerprints, conservative sibling identities,
  namespaced attributes, insertions/reordering, unmatched subtree validation,
  exact parsed leaf text, default value omission and opt-in disclosure, UTF-8
  enforcement, malformed XML and DTD/entity/XInclude/xml:space refusals, limits,
  source stability, output non-overwrite and original examples. Independent
  review passed 47 additional generated adversarial cases, including namespace
  metadata and locator/report expansion limits. It found and verified the fix
  for BOM-less UTF-16 input bypassing the UTF-8 policy. The older local Python
  3.12.7/Expat 2.6.3 correctly returns unsupported_expat_version without parsing.
  The worked example returns exit 2 with one added, one removed, one attribute
  and one text change; inputs stay unchanged and values are omitted by default.
  XML portability CI requires Expat 2.7.2+ on Windows Python 3.13 and Ubuntu
  Python 3.12/3.13. The initial Windows Python 3.12 CI runtime exposed Expat
  2.7.1 and correctly failed the guard; the XML matrix uses supported runtimes
  without lowering the parser requirement. The other standalone utility jobs
  retain their Windows/Ubuntu Python 3.12/3.13 matrix. These are synthetic source
  checks; no actual game XML, mod pack, schema, game launch or runtime settings
  behavior was tested. macOS remains unverified.
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
