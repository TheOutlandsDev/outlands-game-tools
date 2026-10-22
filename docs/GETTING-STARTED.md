# Getting started

These are tools from a personal SPT setup, opened up so other people can inspect them, use the parts that help, and suggest improvements. Each module has a separate job. Start with one module and read its README before changing a game installation.

This is an experimental source collection. Compiling a plugin, passing a synthetic test, and completing a real raid are different checks. The recorded preparation covered the first two; it did not establish gameplay or multiplayer compatibility. See [the actual validation record](../VALIDATION.md).

## Pick the tool that fits the problem

| What you want to do | Start here | Know before using it |
|---|---|---|
| Check loose audio for decoder errors and sample anomalies | [Audio Integrity Checker](../tools/audio-integrity-checker/README.md) | Needs separately installed SoundFile/NumPy. Reads effective loose files without playback or repairs; a decode pass does not prove game compatibility. |
| Check loose Lua source syntax using a selected Lua parser | [Lua Syntax Checker](../tools/lua-syntax-checker/README.md) | Needs Lupa installed in your own Python environment. Compiles inspected chunks without invoking them; game APIs and runtime compatibility are outside its scope. |
| Inspect MO2 loose-file winners and possible Lua/LTX conflicts | [MO2 Conflict Inspector](../tools/mo2-conflict-inspector/README.md) | Reads selected mod folders and profile; no game launch or automatic fixes. It does not unpack archives or reproduce the live virtual filesystem. |
| Investigate frame-time spikes, hitches, Unity errors, or the installed plugin stack | [Codex Diagnostics](../spt/CodexDiagnostics/README.md) | Passive collection still has runtime overhead. Captures can contain profile IDs, paths, and error text. |
| Inspect bot/raid observations and combat-event counts | [QuakeBrain Telemetry](../spt/QuakeBrain/README.md) | It records data; it does not control bots or implement the proposed AI layers. |
| Experiment with persistent scav state, customization, and a separate stash | [Scav Life Framework](../spt/ScavLifeFramework/README.md) | This can change inventory and persistent state. Use a disposable or backed-up test profile. |
| Show the Scav Life stash panel in game | [Scav Life Client](../spt/ScavLifeClient/README.md) | Requires the matching framework and compatible client dependencies. |
| Inspect Scav Life and local installation summaries in a browser | [Scav Life Console](../spt/ScavLifeConsole/README.md) | Local PowerShell dashboard; backend writes are possible even on display routes. |
| Adjust map population caps, spawn timing, or selected scav/PMC waves | [AI Population Tuning](../spt/AiPopulationTuning/README.md) | The preset increases activity. Balance, CPU cost, and interactions need testing. |
| Enable configured scav transits and location-based trader availability | [Open Scav Transits](../spt/OpenScavTransits/README.md) | Trader flags can persist in profiles. Shared route state can affect concurrent players. |
| Address the two known FPV custom-parent warning cases | [FPV Parent Cache Preload](../spt/FpvDroneParentCachePreload/README.md) | Requires the separately obtained compatible FPV setup. It is a narrow compatibility patch. |
| Restore a Scav selector blocked by the targeted Vagabond UI behavior | [Vagabond Scav Access](../spt/VagabondScavAccess/README.md) | Restoring the selector does not prove raid/progression compatibility. |
| Change the two supported server watermark labels | [Text Branding](../spt/EscapeFromConnorBranding/README.md) | Text constants only; no artwork or change to the actual compatible game-build check. |
| Preview and apply explicit Fika headless setup/configuration changes | [Fika Headless Helpers](../spt/FikaHeadless/README.md) | Installer is obtained separately. Every helper previews by default; `-Apply` changes files. |
| Produce a filtered directory inventory | [Game Folder Inventory](../tools/game-tree-exporter/README.md) | Reports filenames and metadata, not file contents. Review names before sharing. |
| Observe the exit code of a game you launch yourself | [Process Exit Observer](../tools/process-exit-observer/README.md) | Observation only. It does not start, stop, repair, or diagnose the root cause by itself. |

You do not need the whole collection. The diagnostics plugins, small compatibility mods, and standalone utilities can be evaluated separately. Scav Life is a companion stack; its framework, client, and console need matching route behavior.

## Requirements and path names

The preparation compile baseline was SPT 4.0.13, EFT 0.16.9.40087, and BepInEx 5.4.23.2 where relevant. Server metadata commonly targets SPT `~4.0.0`. These are reference versions, not a promise that every tool works on every 4.x installation.

For C# builds, use the .NET 9 SDK and your own compatible installation. The client projects target either .NET Standard 2.1 or, for Scav Life Client, .NET Framework 4.7.2. The latter also needs the corresponding reference assemblies. Game, Unity, SPT, Fika, BepInEx, Harmony, and other dependency binaries are not included.

Two build parameters refer to different directories:

| Parameter | Example | Meaning |
|---|---|---|
| `GameRoot` | `D:\Games\SPT` | The installation containing `BepInEx`, `EscapeFromTarkov_Data`, and the `SPT` server subdirectory. |
| `SptServerDirectory` | `D:\Games\SPT\SPT` | The directory containing `SPTarkov.Server.Core.dll` and the other server assemblies. |

Use PowerShell on Windows. Scav Life's console and HTTP helpers require PowerShell 7 because they use zlib support. Fika helpers, report summarizers, and the process observer were also checked with Windows PowerShell 5.1. The folder inventory utility and release checker use Python 3.12+; JavaScript syntax checking uses Node.js.

## Compile one module

Run the following examples from the repository root, replacing the example paths with your own. They build source; they do not launch a game or backend.

```powershell
# Client diagnostics: references the full installation.
.\spt\CodexDiagnostics\Build-CodexDiagnostics.ps1 -GameRoot 'D:\Games\SPT'

# Server population mod: references the server assembly directory.
.\spt\AiPopulationTuning\Build-AiPopulationTuning.ps1 -SptServerDirectory 'D:\Games\SPT\SPT'

# Scav Life: build each companion module separately.
.\spt\ScavLifeFramework\Build-ScavLifeFramework.ps1 -GameRoot 'D:\Games\SPT'
.\spt\ScavLifeClient\Build-ScavLifeClient.ps1 -GameRoot 'D:\Games\SPT'
```

| Build scripts | Required path | Optional parameters and output |
|---|---|---|
| `Build-CodexDiagnostics.ps1`, `Build-QuakeBrainTelemetry.ps1`, `Build-VagabondScavAccess.ps1`, `Build-FpvDroneParentCachePreload.ps1` | `-GameRoot` | Release output under each project's `src/.../bin/Release`. **Only** an explicit `-InstallDirectory` copies that module's DLL to an installation destination. The FPV server output has a `net9.0` subdirectory. |
| `Build-AiPopulationTuning.ps1`, `Build-OpenScavTransits.ps1`, `Build-EscapeFromConnorBranding.ps1` | `-SptServerDirectory` | `-Configuration Debug` or `Release`; default Release output under `src/.../bin/Release/net9.0`. Build only. |
| `Build-ScavLifeFramework.ps1`, `Build-ScavLifeClient.ps1` | `-GameRoot` | `-OutputDirectory` selects a package directory; defaults to `artifacts/ScavLifeFramework` or `artifacts/ScavLifeClient` within the module. `-NoRestore` uses a previous restore. Neither automatically installs. |

Several modules include a NuGet configuration that clears package feeds and builds against installed references. Scav Life's normal build can restore SDK dependencies; use `-NoRestore` only after a successful restore. Missing SDK/reference packs must be resolved locally. Do not copy game dependencies into this repository to make a build pass.

## Install into a test instance

Stop the game and backend before replacing plugins. Back up profiles and the specific configuration files you will change; keep those backups outside the public repository. Install one module, check its behavior, and record the versions before adding another.

Use the module README for exact assembly names and destination folders:

- Client plugins go into their documented `BepInEx/plugins` subdirectory.
- Server plugins go into their documented `SPT/user/mods` subdirectory.
- AI Population Tuning, Open Scav Transits, and Scav Life Framework also require their reviewed default `config` folder. Preserve an existing custom config instead of overwriting it blindly.
- Dependencies are referenced in place and marked not to copy with the plugin. Distribute only your own build output, subject to a separate dependency/license review if making binary releases.

The optional `-InstallDirectory` on four build scripts overwrites that tool's named DLL at the destination you supply. There is no collection-wide installer, dependency manager, mod conflict resolver, or automatic save restoration.

For uninstalling, stop the game/backend and remove the module DLL or folder described in its README. Removing a plugin does not undo already persisted profile or trader changes. Open Scav Transits specifically may require restoring a profile backup or reviewing trader flags. Scav Life data/config and diagnostic logs also remain separate from the plugin DLL.

Fika's wrappers have their own workflow: preview first, inspect the plan, then use `-Apply` only when you want those changes. Repair creates backups with a manifest; pruning moves selected entries into a fresh disabled directory. Read [the Fika restoration instructions](../spt/FikaHeadless/README.md) before applying either operation.

## Use reports or the local dashboard

To summarize your own captures without modifying them:

```powershell
.\spt\CodexDiagnostics\Summarize-CodexDiagnostics.ps1 -Path 'D:\Reports\client-example.jsonl'
.\spt\QuakeBrain\Summarize-QuakeBrainTelemetry.ps1 -Path 'D:\Reports\raid-example.jsonl'
```

The plugins generate captures during runtime; no real captures are shipped. Read their privacy notes before sharing any results.

For the Scav Life dashboard, start your own compatible backend separately, then use PowerShell 7:

```powershell
.\spt\ScavLifeConsole\Start-ScavLifeConsole.ps1 -GameRoot 'D:\Games\SPT' -ProfileId local-test -NoBrowser
```

Open `http://127.0.0.1:7777/`. The console requires literal loopback IPs, normal backend TLS certificate validation, and same-origin browser requests. Mutation routes are disabled unless `-EnableMutations` is supplied; backend debug methods separately require `developmentMode=true`. Those flags are deliberate opt-ins, not troubleshooting defaults. Display requests can still initialize framework state. See [console details](../spt/ScavLifeConsole/README.md) before enabling writes or selecting a real profile.

## Check the source package

From the repository root:

```powershell
python -B tools/verify_source_release.py
```

This checks the recorded source inventory, allowed file types, some sensitive-data patterns, and local documentation links. A manifest mismatch means the files differ from the reviewed package; it does not by itself identify malicious changes. Do not regenerate the manifest just to hide an unexpected difference.

For the available offline checks and their limits, read [VALIDATION.md](../VALIDATION.md). For build failures, TLS errors, missing captures, and compatibility questions, use [the FAQ](FAQ.md). Suggestions and first-time contributions are welcome; [CONTRIBUTING.md](../CONTRIBUTING.md) explains how to share useful evidence without publishing private data.
