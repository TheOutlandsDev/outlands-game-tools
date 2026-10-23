# Outlands Game Tools

Original SPT mods and local game utilities from
TheOutlandsDev / Connor O'Shea. Original contributions are available under the
[MIT license](LICENSE). See [dependency and provenance boundaries](THIRD-PARTY.md).

Suggestions, questions, bug reports and contributions are welcome. Explain the
problem you want solved, the setup you tried, and what a useful result would
look like. You do not need to submit code to help improve the tools.

**Experimental source release.** Compile and synthetic checks are separate from
gameplay validation. Use a backed-up test installation and read each module's
README before building or installing. There is no automatic installer for the
collection. Default builds do not change an installed game.

Start with [getting started](docs/GETTING-STARTED.md), [questions and troubleshooting](docs/FAQ.md),
and the [roadmap and help wanted](docs/ROADMAP.md). Changes in this first source
release are listed in [CHANGELOG.md](CHANGELOG.md).

For a versioned download, use the [v0.1.0 source pre-release](https://github.com/TheOutlandsDev/outlands-game-tools/releases/tag/v0.1.0)
and [download quick start](docs/QUICK-START.md). The custom ZIP and SHA-256 asset
contain reviewed source; games, compiled plugins and dependency binaries are
obtained separately. Maintainers can read [the source release process](docs/RELEASING.md).

## SPT modules

| Module | Purpose |
|---|---|
| [Codex Diagnostics](spt/CodexDiagnostics/README.md) | Frame-time, hitch, process and plugin diagnostics with JSONL summaries. |
| [QuakeBrain Telemetry](spt/QuakeBrain/README.md) | Passive raid telemetry and offline summaries; planned AI layers are not implemented. |
| [Scav Life Framework](spt/ScavLifeFramework/README.md) | Experimental persistent scav state, plans and stash integration. |
| [Scav Life Client](spt/ScavLifeClient/README.md) | In-game companion UI for the framework. |
| [Scav Life Console](spt/ScavLifeConsole/README.md) | Local browser dashboard; loopback, same-origin/token checks and opt-in mutations. |
| [AI Population Tuning](spt/AiPopulationTuning/README.md) | Server-side AI population adjustments. |
| [Open Scav Transits](spt/OpenScavTransits/README.md) | Transit/trader availability adjustments; read persistent-state limitations. |
| [FPV Parent Cache Preload](spt/FpvDroneParentCachePreload/README.md) | Small compatibility preload for a separately obtained FPV mod. |
| [Vagabond Scav Access](spt/VagabondScavAccess/README.md) | Focused client compatibility adjustment for a separately obtained Vagabond setup. |
| [Text Branding](spt/EscapeFromConnorBranding/README.md) | Configurable server title text; no artwork. |
| [Fika Headless Helpers](spt/FikaHeadless/README.md) | Explicit-input, preview-first setup/configuration/plugin helpers. |

The compile baseline is SPT 4.0.13, EFT 0.16.9.40087 and BepInEx 5.4.23.2, where
applicable. These identify the references used locally; they are not a blanket
compatibility claim. Obtain game and dependency assemblies separately. Modules
use their documented `GameRoot` or `SptServerDirectory` build parameters.

```powershell
# Example: compile only, using your already installed matching references.
.\spt\CodexDiagnostics\Build-CodexDiagnostics.ps1 -GameRoot 'D:\Games\SPT'
```

The source retains existing plugin IDs/names for compatibility. Codex names in
older namespaces and metadata identify the original assistant-assisted local
projects; the collection is maintained by TheOutlandsDev, not an official OpenAI
or SPT product.

## Standalone game utilities

### Try a tool without a game installation

Start with the [LTX Definition Inspector](tools/ltx-definition-inspector/README.md)
if you want a small, dependency-free example to inspect and test. Its Python
implementation, synthetic tests, report format and fictional example generator
are all in this repository. Use Python 3.12 or newer; no game, model, account or
extra Python package is needed.

From the repository root on Linux or macOS:

```sh
# Create a new fictional input folder beside your checkout.
python3 -B tools/ltx-definition-inspector/examples/create_example.py --destination ../outlands-ltx-demo

# Inspect the clean example; JSON goes to your terminal. Expected exit: 0.
python3 -B tools/ltx-definition-inspector/ltx_inspector.py --root ../outlands-ltx-demo/configs --entry clean.ltx

# Run the inspector's isolated synthetic test suite.
python3 -B -m unittest discover -s tools/ltx-definition-inspector/tests -v
```

On Windows, use `py -3.12` instead of `python3`. The example generator refuses
an existing destination. The inspector reads the selected configuration files;
it does not start a game or evaluate configuration values. See the
[worked examples](tools/ltx-definition-inspector/examples/README.md) for review
findings (exit 2) and incomplete inspection (exit 1). Those outcomes are
different from a clean structural report (exit 0).

### Choose another utility

- [XML Mod Configuration Diff](tools/xml-config-diff/README.md): compare selected
  XML files for changed attributes/text and added/removed entries, with namespace
  awareness and conservative sibling matching. Values are hidden by default.
  Added after v0.1.0; use the current main source for this tool.
- [Mod Content Manifest & Diff](tools/mod-content-manifest/README.md): hash
  selected loose folders or MO2 winners, then compare compatible manifests for
  added, removed, changed or differently provided files. No file payload upload.
- [Verified Source Release Builder](tools/source-release-builder/README.md):
  create and verify a deterministic source ZIP and companion SHA-256 file from
  an explicit reviewed source manifest. Maintainer utility; new outputs only.
- [LTX Definition Inspector](tools/ltx-definition-inspector/README.md): inspect
  explicit entry/include graphs for missing parents, duplicate sections and
  cycles. Structural checks only; unsupported DLTX makes the report incomplete.
- [X-Ray Log Summary](tools/xray-log-summary/README.md): count selected warning,
  fatal/script-error and session markers without emitting original log text.
  Local observations only; no game diagnosis or raw-log redaction guarantee.
- [MO2 Baseline Profile Builder](tools/mo2-profile-builder/README.md): preview and
  create a separate limited comparison profile with selected mods disabled.
  New destinations only; originals remain unchanged. Read shared-save caveats.
- [Save Snapshot Verifier](tools/save-snapshot-verifier/README.md): create new
  SHA-256-verified backups of selected saves/configuration, then check snapshots
  for changed, missing or unexpected files. No restore or overwrite feature.
- [Audio Integrity Checker](tools/audio-integrity-checker/README.md): stream-decode
  loose audio or a saved MO2 profile's winning files, report decode errors and
  sample anomalies, and optionally hash inputs. Includes generated examples.
- [Lua Syntax Checker](tools/lua-syntax-checker/README.md): compile-only checks
  for loose Lua sources or the winning files of a saved MO2 profile. Select
  LuaJIT 2.1, Lua 5.1, or Lua 5.4 through a separately installed Lupa dependency.
- [MO2 Conflict Inspector](tools/mo2-conflict-inspector/README.md): read-only
  loose-file priority and possible Lua/LTX conflict reports for an explicit MO2
  profile. Includes a game-free worked example and offline tests.
- [Game Folder Inventory](tools/game-tree-exporter/README.md): filtered TXT/CSV/JSON
  inventories, without reading game-file contents or following links.
- [Process Exit Observer](tools/process-exit-observer/README.md): capture a
  user-started game's native exit code without starting or stopping the game.

## Verification and contributing

Run `python -B tools/verify_source_release.py` with Python 3.12+ to check the
recorded source inventory and publication exclusions. The SHA-256 manifest
detects changes relative to this reviewed package; it does not authenticate a
download by itself or prove legal ownership. See [VALIDATION.md](VALIDATION.md)
for actual checks and remaining limits.

Contributions follow [CONTRIBUTING.md](CONTRIBUTING.md). Do not attach unredacted
logs, profiles, credentials or network/device identifiers to public issues.
There is no telemetry-upload feature in this collection.
