# Escape From Connor Branding

Small SPT 4.0.x server mod (version 1.0.0) replacing two watermark labels with `Escape From Connor` and `Version 0.1`. It leaves the actual compatible Tarkov build check untouched. No artwork, logos, fonts, or game assets are included.

## Build and install

Requires the .NET 9 SDK and separately installed SPT server assemblies:

```powershell
.\Build-EscapeFromConnorBranding.ps1 -SptServerDirectory 'D:\Games\SPT\SPT'
```

The supplied directory must contain `SPTarkov.DI.dll`, `SPTarkov.Server.Core.dll`, `SPTarkov.Reflection.dll`, and `SemanticVersioning.dll`. Output is `src/Codex.EscapeFromConnorBranding/bin/Release/net9.0/Codex.EscapeFromConnorBranding.dll`. The script builds only and uses no package sources.

With the server stopped, copy that DLL to `SPT/user/mods/000-EscapeFromConnorBranding`. Remove the mod folder to uninstall. Change the three label constants in `EscapeFromConnorBranding.cs` to customize the text, then rebuild.

## Compatibility and maturity

Source metadata declares `~4.0.0`. This mod patches two public `Watermark` methods by reflection; SPT updates that change those methods require a port. Other watermark/version-label patches can conflict. Compilation was checked during release preparation, but server startup and visible in-game labels were not tested.

Original source metadata declares MIT; the repository MIT license covers this original code. Referenced SPT/EFT components retain their own terms and are absent from the release.
