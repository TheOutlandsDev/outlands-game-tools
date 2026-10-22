# QuakeBrain Telemetry

Passive BepInEx/Harmony telemetry for SPT. Records raid snapshots, tracked bot lives, rate-limited shot/damage/death events, position/look/velocity samples, line-of-sight probes, and optional advisory utility scores. It does not control bots. Future AI behavior layers and ML helpers are not implemented in this release.

Capture defaults: enabled; five tracked AI lives after a 30-second delay; five-second snapshots; combat events enabled; utility scores disabled; bounded writer queue. Files are written under `<GameRoot>/Logs/QuakeBrainTelemetry`. BepInEx generates configuration in `BepInEx/config/codex.quakebrain.telemetry.cfg`.

## Read a capture

```powershell
.\Summarize-QuakeBrainTelemetry.ps1 -Path '.\raid-example.jsonl'
.\Summarize-QuakeBrainTelemetry.ps1 -TelemetryDirectory 'D:\Games\SPT\Logs\QuakeBrainTelemetry' -Latest 3
```

The summarizer reads files and prints counts/averages; it does not modify them.

## Privacy and operating limits

Captures and filenames include player profile IDs. Payloads can contain account IDs, nicknames, group/team IDs, positions, equipment names, and absolute log paths. Capture is local, contains no anonymization, and has no upload feature. Obtain consent from co-op participants and redact identifiers before sharing. Raw captures, player profiles, and installed configurations are excluded from this source release.

Line-of-sight probes use generic physics raycasts and are not authoritative AI visibility. Capture caps drop events under load. Reflection fallbacks can omit fields on incompatible builds. Game hooks, capture overhead, and writer lifecycle across consecutive raids still require runtime validation. SAIN, BigBrain, Waypoints, and Fika compatibility has not been independently established by this preparation pass.

## Build and install

Use Windows, PowerShell, the .NET 9 SDK, and the already-installed matching SPT game/mod references. The client plugins target .NET Standard 2.1, matching the current Unity/BepInEx reference baseline; the server preload targets .NET 9. Dependencies are referenced from your own installation; none are redistributed here. `nuget.config` clears package feeds, so the build does not download dependencies.

From this module directory:

```powershell
.\Build-QuakeBrainTelemetry.ps1 -GameRoot 'D:\Games\SPT'
```

This builds locally and does not install anything. To install the compiled plugin, explicitly add:

```powershell
.\Build-QuakeBrainTelemetry.ps1 -GameRoot 'D:\Games\SPT' -InstallDirectory 'D:\Games\SPT\BepInEx\plugins\QuakeBrain'
```

The install step replaces only this module's named DLL at that destination. Close the game/server before installing or removing a plugin. Remove that DLL to uninstall; existing logs/config files remain.

## Compatibility and maturity

This is an experimental source release. Preparation used references from SPT 4.0.13, Escape from Tarkov 0.16.9.40087, and BepInEx 5.4.23.2 where applicable. Those reference versions identify the local compile baseline, not a promise of compatibility with every 4.x build. Private EFT fields, Harmony targets, and mod behavior can change between releases. No game, raid, or co-op session was launched as part of this release preparation.

## Source and licensing

The original project source was selected from the owner's local custom tools. No upstream source license/header was present in the selected files. The repository MIT license applies to the original code in this directory under the owner's publication instruction. Game APIs, BepInEx, Harmony, Newtonsoft.Json, SPT, and other external dependencies retain their own terms. Their source, binaries, game data, and assets are excluded. Names identify compatibility and do not imply affiliation or endorsement.

## Validation

See [VALIDATION.md](VALIDATION.md). Run the synthetic report checks with:

```powershell
powershell -File .\tests\Test-Summary.ps1
```
