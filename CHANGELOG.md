# Changes

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
