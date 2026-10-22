# Vagabond Scav Access

Small BepInEx/Harmony compatibility patch for the Vagabond mod. After Vagabond marks the Scav side selector with `Disabled (Vagabond Mod)`, it restores the Scav UI controls and selected-side visuals. It declares Vagabond as a soft dependency and checks the specific blocked-state text before acting.

Configuration: `Compatibility / Enabled` defaults to `true`. BepInEx generates `BepInEx/config/codex.vagabond.scavaccess.cfg` after loading.

## Privacy and operating limits

The patch does not collect telemetry or edit player profiles. Ordinary BepInEx messages still go to the host's normal logs. It patches private UI members and depends on Vagabond's exact English blocked-state text; updates or localization can break it. Restoring the UI does not establish that Scav raids or progression are supported by every Vagabond version. Verify the full selection/load/return flow with the intended versions before relying on it.

Vagabond source and assets are not included. This module supplies only the compatibility patch.

## Build and install

Use Windows, PowerShell, the .NET 9 SDK, and the already-installed matching SPT game/mod references. The client plugins target .NET Standard 2.1, matching the current Unity/BepInEx reference baseline; the server preload targets .NET 9. Dependencies are referenced from your own installation; none are redistributed here. `nuget.config` clears package feeds, so the build does not download dependencies.

From this module directory:

```powershell
.\Build-VagabondScavAccess.ps1 -GameRoot 'D:\Games\SPT'
```

This builds locally and does not install anything. To install the compiled plugin, explicitly add:

```powershell
.\Build-VagabondScavAccess.ps1 -GameRoot 'D:\Games\SPT' -InstallDirectory 'D:\Games\SPT\BepInEx\plugins\Codex.VagabondScavAccess'
```

The install step replaces only this module's named DLL at that destination. Close the game/server before installing or removing a plugin. Remove that DLL to uninstall; existing logs/config files remain.

## Compatibility and maturity

This is an experimental source release. Preparation used references from SPT 4.0.13, Escape from Tarkov 0.16.9.40087, and BepInEx 5.4.23.2 where applicable. Those reference versions identify the local compile baseline, not a promise of compatibility with every 4.x build. Private EFT fields, Harmony targets, and mod behavior can change between releases. No game, raid, or co-op session was launched as part of this release preparation.

## Source and licensing

The original project source was selected from the owner's local custom tools. No upstream source license/header was present in the selected files. The repository MIT license applies to the original code in this directory under the owner's publication instruction. Game APIs, BepInEx, Harmony, Newtonsoft.Json, SPT, and other external dependencies retain their own terms. Their source, binaries, game data, and assets are excluded. Names identify compatibility and do not imply affiliation or endorsement.
