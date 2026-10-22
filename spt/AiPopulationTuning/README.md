# AI Population Tuning

SPT 4.0.x server mod that adjusts per-map bot caps, spawn timing, normal scav waves, and PMC boss-wave chances after database loading. Version 0.1.0; experimental. It edits the server's in-memory location data and loads `config/config.json` beside its DLL. Invalid config falls back to the source defaults.

## Build and install

Requires the .NET 9 SDK and an existing, separately obtained compatible SPT installation. In PowerShell:

```powershell
.\Build-AiPopulationTuning.ps1 -SptServerDirectory 'D:\Games\SPT\SPT'
```

The directory must contain `SPTarkov.DI.dll`, `SPTarkov.Server.Core.dll`, `SPTarkov.Reflection.dll`, and `SemanticVersioning.dll`. No dependencies are redistributed or downloaded by this build. Output is `src/Codex.AiPopulationTuning/bin/Release/net9.0/Codex.AiPopulationTuning.dll`.

With the server stopped, copy only the built DLL and the `config` folder to `SPT/user/mods/zzz-CodexAiPopulationTuning`. Keep existing config separately before replacing it. The build script does not install or update the game. Remove this mod folder to uninstall.

## Behavior and compatibility

Review every map entry before use: the included preset increases activity and may increase CPU load. Existing values above configured caps are not reduced by the cap addition path. Boss-specific waves other than the targeted PMC wave types are outside this tool's scope. Source metadata declares `~4.0.0`; other SPT generations are unsupported without porting.

Other spawn/population overhaul mods can overwrite these settings or be overwritten by them; load order affects results. No exhaustive compatibility list exists. Server build success does not establish raid balance, performance, or Fika behavior. Back up profiles before any runtime test.

## License and validation

Original module source declares MIT. This release uses the repository MIT license. SPT, EFT, and other referenced software retain their own terms; their binaries and assets are absent.

Release preparation validates compilation against locally installed assemblies only. No server, raid, or multiplayer session was launched for this release.
