# FPV Drone Parent Cache Preload

Small SPT server compatibility preload for `FPVDroneModServer`. FPV Drone uses two custom parent template identifiers. This preload returns `false` for base-class queries on those two identifiers before SPT's item base-class service processes them, suppressing warnings for these synthetic parents. Other item queries continue through the original method.

It does not rewrite FPV items or include FPV Drone source/assets. The two 24-character identifiers in the source are functional FPV item-template constants, not player/profile identifiers.

## Privacy and operating limits

No player telemetry, network calls, or profile writes are implemented. A normal server startup message confirms patch installation. The server metadata declares SPT `~4.0.0`; the local reference baseline is 4.0.13. Method overloads and FPV parent identifiers must match the target versions. A successful compile does not establish that warning suppression or drone/payload behavior is correct in a live server. No server was started in this preparation pass.

## Build and install

Use Windows, PowerShell, the .NET 9 SDK, and the already-installed matching SPT game/mod references. The client plugins target .NET Standard 2.1, matching the current Unity/BepInEx reference baseline; the server preload targets .NET 9. Dependencies are referenced from your own installation; none are redistributed here. `nuget.config` clears package feeds, so the build does not download dependencies.

From this module directory:

```powershell
.\Build-FpvDroneParentCachePreload.ps1 -GameRoot 'D:\Games\SPT'
```

This builds locally and does not install anything. To install the compiled plugin, explicitly add:

```powershell
.\Build-FpvDroneParentCachePreload.ps1 -GameRoot 'D:\Games\SPT' -InstallDirectory 'D:\Games\SPT\SPT\user\mods\000-FPVDroneParentCachePreload'
```

The install step replaces only this module's named DLL at that destination. Close the server before installing or removing a plugin. Remove that DLL to uninstall; existing logs/config files remain.

## Compatibility and maturity

This is an experimental source release. Preparation used references from SPT 4.0.13, Escape from Tarkov 0.16.9.40087, and BepInEx 5.4.23.2 where applicable. Those reference versions identify the local compile baseline, not a promise of compatibility with every 4.x build. Private EFT fields, Harmony targets, and mod behavior can change between releases. No game, raid, or co-op session was launched as part of this release preparation.

## Source and licensing

The original project source was selected from the owner's local custom tools. No upstream source license/header was present in the selected files. The repository MIT license applies to the original code in this directory under the owner's publication instruction. SPT, Harmony, SemanticVersioning, and other external dependencies retain their own terms. Their source, binaries, game data, and assets are excluded. Names identify compatibility and do not imply affiliation or endorsement.
