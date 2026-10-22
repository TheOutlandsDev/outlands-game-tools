# Codex Diagnostics

Passive BepInEx client diagnostics for an SPT installation. Records session markers, plugin/mod inventory, Unity warnings/errors, scene changes, frame-time/FPS/hitch statistics, process memory/CPU samples, and lightweight raid context. Writes bounded JSONL through a background worker under `<GameRoot>/Logs/CodexDiagnostics`.

## Read a capture

```powershell
.\Summarize-CodexDiagnostics.ps1 -Path '.\client-example.jsonl'
.\Summarize-CodexDiagnostics.ps1 -DiagnosticsDirectory 'D:\Games\SPT\Logs\CodexDiagnostics' -ComparePrevious
```

The summarizer reads files and prints a report; it does not change them. BepInEx generates configuration in `BepInEx/config/codex.diagnostics.client.cfg` after loading. Capture is enabled by default; normal info logs are disabled by default.

## Privacy and operating limits

Capture files can contain absolute paths, the main player's profile ID, plugin/mod names, hardware/OS details, and free-form Unity error messages/stack traces. There is no anonymization or upload feature. Review and redact captures before sharing them. Raw logs and existing configuration files are excluded from this source release. Bounded queues can drop events under load; this is diagnostic sampling rather than complete recording. Performance overhead and writer shutdown behavior need runtime testing with the target mod set.

## Build and install

Use Windows, PowerShell, the .NET 9 SDK, and the already-installed matching SPT game/mod references. The client plugins target .NET Standard 2.1, matching the current Unity/BepInEx reference baseline; the server preload targets .NET 9. Dependencies are referenced from your own installation; none are redistributed here. `nuget.config` clears package feeds, so the build does not download dependencies.

From this module directory:

```powershell
.\Build-CodexDiagnostics.ps1 -GameRoot 'D:\Games\SPT'
```

This builds locally and does not install anything. To install the compiled plugin, explicitly add:

```powershell
.\Build-CodexDiagnostics.ps1 -GameRoot 'D:\Games\SPT' -InstallDirectory 'D:\Games\SPT\BepInEx\plugins\CodexDiagnostics'
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
