# Scav Life Client (experimental)

MIT-licensed BepInEx panel for the companion Scav Life Framework. Press `F8` to show pending scav hauls and stored item trees. The panel can request a haul transfer through the framework backend, so use a disposable or backed-up test profile.

## Build

Requires the .NET SDK, .NET Framework 4.7.2 reference assemblies, and a compatible SPT installation containing BepInEx, `spt-common`, Unity, and Newtonsoft.Json assemblies. These dependencies retain their respective licenses and are not redistributed here.

```powershell
.\Build-ScavLifeClient.ps1 -GameRoot 'D:\Games\SPT'
```

The build resolves dependencies from your installation with `Private=false` and packages only `Codex.ScavLife.Client.dll` under `artifacts/ScavLifeClient`. It never installs into the game. `-OutputDirectory` changes the package destination; `-NoRestore` uses an existing restore. A normal build may restore SDK dependencies.

For manual installation into a backed-up test instance, copy the built DLL into `BepInEx/plugins/ScavLifeClient`. Install the matching server-side framework separately. The client depends on `/singleplayer/scavlife/stash/status` and `/singleplayer/scavlife/stash/decision`.

Source inspection and offline compilation do not establish runtime compatibility. No game launch, panel interaction, raid, or real inventory transfer was tested during publication preparation. No proprietary assemblies, saved profiles, or telemetry are included.
