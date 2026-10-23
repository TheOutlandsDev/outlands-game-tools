# Changes

## Mod Package ZIP Layout Inspector 1.0.0 - 2026-10-23

- Added original bounded single-disk contiguous classic ZIP32 metadata inspection
  for stored/deflated entries, matching local headers and classic descriptors.
  Lists names and declared sizes without extracting or decompressing members.
- Reports unsafe paths, duplicate/case/normalization collisions, file/directory
  prefixes, link attributes, encrypted entries, uninterpreted extras, common
  wrapper folders and suspicious declared sizes. Unsupported or malformed
  layouts produce incomplete results with no partial inventory.
- Added original stdlib-generated examples, malformed-archive and resource tests,
  detailed commands/report documentation, suggestion links and Windows/Linux
  Python 3.12/3.13 CI. Current main source after v0.1.0; no game files,
  third-party parser or AGPL implementation bundled.

## Unreal PAK Index & Conflict Inspector 1.0.0 - 2026-10-23

- Added an original read-only inspector for explicit standard unencrypted
  version-3 PAK indexes. Verifies the declared index SHA-1, strict strings/mounts,
  entry/block ranges and bounded counts without reading local entry headers or payloads.
- Reports case-insensitive virtual path overlaps and file/directory conflicts
  across labeled archives. Declared entry hashes do not prove payload equality,
  and argument order does not predict game load order or winners.
- Added original generated archives, binary-format and conflict regression tests,
  detailed commands/report documentation, explicit unsupported-format/privacy
  guidance, public suggestion links and Windows/Ubuntu Python 3.12/3.13 checks.
- Current main source after v0.1.0; no game archives, keys, extraction/decryption
  support, third-party parser or AGPL companion implementation is included.

## INI/LTX Configuration Value Diff 1.0.0 - 2026-10-23

- Added an original read-only comparison of explicit INI/LTX file pairs for
  literal section/key additions, removals and changed values. LTX parent lists
  are compared as declaration context without computing inherited values.
- Defines case matching, duplicate-key handling, comments and per-input
  encoding policies. Values are fingerprinted by default; exporting their
  literal text requires `--include-values`. Includes, DLTX and unsupported
  syntax make comparison incomplete rather than producing an equality claim.
- Added bounded parsing/comparison/reports, guarded new output, original
  generated examples, detailed instructions/report documentation, public
  suggestion links and Windows/Ubuntu Python 3.12/3.13 tests.
- Current main source after v0.1.0; no game configuration, third-party parser,
  engine implementation or AGPL companion source is included.

## Mod Asset Reference Checker 1.0.0 - 2026-10-22

- Added an original read-only checker for literal references in explicitly
  selected LTX files and contained literal include graphs. Defaults inspect
  `visual` mesh paths and `ammo_class` section lists; file/section key mappings
  can be selected explicitly. Inherited values and DLTX are not merged.
- Distinguishes loose-file metadata presence, paths listed in a supplied index,
  unresolved coverage and absence within explicitly declared complete coverage.
  A path index is supplied data, not proof of archive contents or compatibility.
- Added bounded parsing/lookups/reports, strict reference/index paths, guarded
  new output, original generated examples, detailed instructions/report scope,
  public suggestion links and Windows/Ubuntu Python 3.12/3.13 tests.
- New source on main after v0.1.0; no game assets, archive extractor, engine,
  upstream mod implementation or AGPL companion code is included.

## XML Mod Configuration Diff 1.0.0 - 2026-10-22

- Added an original read-only comparison of selected XML file pairs, using
  expanded namespace names and conservative per-parent identity matching.
- Reports attribute/text changes, compact added/removed subtrees and reordered
  common children. Ambiguous matches and unsupported mixed content are incomplete.
- Hides values by default, bounds parsing/comparison/report resources, rejects
  DTD/entity declarations, requires Expat 2.7.2+, and creates only new optional
  JSON reports.
- Added original generated examples, detailed commands/report scope, regression
  tests, Windows Python 3.13 and Ubuntu Python 3.12/3.13 XML checks, and public
  feedback guidance. The Expat minimum is checked independently of Python version.
- Added after the v0.1.0 snapshot; use current main source for this module.

## Collection v0.1.0 source pre-release - 2026-10-22

- Added Mod Content Manifest & Diff 1.0.0: bounded relative-path SHA-256 manifests
  for selected folders/MO2 winners and strict comparisons of compatible inputs.
- Added Verified Source Release Builder 1.0.0: manifest-selected source archives,
  deterministic stored ZIP members, member/hash verification and SHA-256 assets.
- Added the download quick start and maintainer release process, expanded public
  feedback module choices and portability checks, and prepared the first tagged
  source kit. No compiled game plugins or dependency payloads are included.
- The collection remains an experimental source release. Existing module guides
  and validation limits apply; this tag does not establish gameplay compatibility.

## LTX Definition Inspector 1.0.0 - 2026-10-22

- Added read-only structural checks of explicit loose entry/include graphs:
  section declarations, ordered parents, missing parents, duplicates and cycles.
- Added incomplete status for missing/unsafe includes, unsupported DLTX/syntax
  and limits. No values are merged or game-loader compatibility claimed.
- Bounded source bytes, graph records/depth, directory lookup, cycle witnesses
  and JSON report expansion. Added guarded output and relative diagnostics.
- Added fictional examples, detailed interpretation/scope guidance, synthetic
  regression/stress tests and portability CI. Original source/docs/tests are MIT.

## X-Ray Log Summary 1.0.0 - 2026-10-22

- Added bounded strict-decoding scans of one inactive selected X-Ray log, with
  warning/fatal/script-error counts and selected session/transport text markers.
- Reports contain static category/error codes, counts and capped line numbers;
  source text, paths, filenames and extracted identifiers are omitted.
- Added explicit incomplete status, guarded new reports, original generated logs,
  detailed privacy/scope guidance and portable synthetic tests.
- Original code/docs/tests/examples are MIT; no raw game logs or engine bundled.

## MO2 Baseline Profile Builder 1.0.0 - 2026-10-22

- Added previews and explicit creation of a new limited saved-profile copy with
  exact selected mods disabled; saved modlist order, BOM and newlines preserved.
- Added a fixed five-file allowlist, source/copy verification, exclusive report
  reservation before apply and guarded rollback of only owned files.
- Added detailed examples, shared-save and excluded-profile-file guidance,
  synthetic regression tests and Windows/Ubuntu portability CI.
- Original source/docs/tests/examples are MIT. No MO2/game/mod payloads bundled.

## Save Snapshot Verifier 1.0.0 - 2026-10-22

- Added explicit labeled file/folder snapshots into new destinations, with
  streamed SHA-256 copy verification and input stability checks.
- Added separate read-only verification of changed, missing and unexpected files,
  guarded reports, input/output limits and partial-snapshot markers.
- Added original toy files, detailed commands and failure guidance, synthetic
  tests and portability CI. No restore, deletion or game-format validation.
- Original code, examples, tests and docs are MIT; no game/save payloads bundled.

## Audio Integrity Checker 1.0.0 - 2026-10-22

- Added streamed decode checks for loose WAV/OGG/FLAC/AIFF audio and the effective
  files of saved MO2 profiles, including optional loose base and overwrite roots.
- Added metadata, finite-sample and decoded-frame checks, optional streaming
  SHA-256, explicit byte/frame/channel limits and sanitized JSON reports.
- Added protected report creation, incomplete-scan status, original generated
  examples, synthetic regression checks and Windows/Ubuntu portability CI.
- Added detailed setup, report interpretation and public bug/suggestion links.
  A decode pass does not establish game compatibility or validate every byte.
- Original source, examples, tests and docs are MIT. SoundFile, NumPy and their
  native dependencies are separately installed and retain their own licenses.

## Lua Syntax Checker 1.0.0 - 2026-10-22

- Added compile-only syntax checks for loose `.lua`/`.script` sources and the
  effective loose files of a saved MO2 profile, with optional base/overwrite roots.
- Added explicit LuaJIT 2.1, Lua 5.1 and Lua 5.4 parser selection through Lupa 2.8.
  Inspected chunks are compiled and discarded; their top-level code is not run.
- Added source/parser-input hashes, UTF-8 BOM accounting, sanitized error line
  reports, incomplete-scan status and guarded exclusive report creation.
- Added detailed instructions, a reproducible original example, synthetic
  regression checks, public feedback links and portability CI.
- Original code, examples, tests and documentation are MIT. External parser
  dependencies retain their own terms and are not bundled.

## MO2 Conflict Inspector 1.0.0 - 2026-10-22

- Added a portable Python standard-library inspector for explicit MO2 profiles,
  with loose-file provider/winner reports and optional overwrite-folder input.
- Added heuristic reports for repeated qualified Lua declarations, repeated LTX
  keys, and unlocalizer symbols. Findings are review prompts, not proof of a
  broken installation or a proposed automatic repair.
- Added relative report references, omitted source/configuration values,
  protected source folders from output, and made partial scans visible.
- Added detailed setup, CLI/report explanations, an original game-free example,
  synthetic tests, and the inspector in the public bug-report form.
- Original inspector code, examples, tests and docs use the collection's MIT
  license. No game/mod payloads are included or changed.

## Initial public source package - 2026-10-22

- Selected eleven original SPT mod/helper modules and two standalone game tools.
- Added MIT licensing for original contributions with explicit external-dependency
  boundaries and source provenance notes.
- Converted installed-machine build paths to explicit parameters; default builds
  compile/package locally without installing into a game.
- Removed private endpoints, profile identifiers, runtime logs/state and binaries
  from the publication tree.
- Hardened the local Scav Life console's origin/host/request-token checks, normal
  backend TLS validation and mutation defaults. Gated framework debug operations.
- Reworked Fika wrappers around explicit inputs, previews, optional apply operations,
  path checks and backup/manifests.
- Made the folder inventory utility portable, with relative reports, explicit
  overwrite, filtering, link handling and spreadsheet-formula protection.
- Made the process-exit observer independent of one game or installation path.
- Added setup/FAQ/roadmap/contribution documentation, public bug/suggestion forms,
  synthetic checks, a source hash manifest and a GitHub Actions source-check workflow.

Nine C# projects compiled locally without warnings/errors. No game, raid, live
SPT backend, installer or multiplayer session was started for this release.
