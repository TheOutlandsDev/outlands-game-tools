# Changes

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
