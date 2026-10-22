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
