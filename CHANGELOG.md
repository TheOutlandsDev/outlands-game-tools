# Changes

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
