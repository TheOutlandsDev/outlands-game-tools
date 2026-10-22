# Open Scav Transits and Trader Routes

Experimental SPT 4.0.x server mod, version 0.2.1. It opens selected scav-map flags, enables existing configured map transits, and optionally changes trader availability according to the last raid location. It does not create new transit geometry or supply game assets.

## Build and install

Requires the .NET 9 SDK and a separately installed compatible SPT server:

```powershell
.\Build-OpenScavTransits.ps1 -SptServerDirectory 'D:\Games\SPT\SPT'
```

The supplied directory must contain `SPTarkov.DI.dll`, `SPTarkov.Server.Core.dll`, `SPTarkov.Reflection.dll`, and `SemanticVersioning.dll`. The build does not download packages or install anything. Output is `src/Codex.OpenScavTransits/bin/Release/net9.0/Codex.OpenScavTransits.dll`.

With the server stopped and profiles backed up, copy only that DLL and `config` to `SPT/user/mods/zzz-CodexOpenScavTransits`. Review the configuration before starting. Invalid config falls back to the source defaults.

## Behavior and limitations

`TraderAvailability.Enabled` defaults to true. The trader hook updates PMC and scav profile trader `Disabled`/`Unlocked` flags, including disabling traders outside the selected route. This can be persisted by the server. Set it to false before first use if you want transit changes alone. Removing the mod does not restore previously saved trader flags; restore a backup or review those flags separately. `ReturnOnlyAvailableTraders` is currently unused: the hook returns the full trader list and uses profile flags to enforce availability.

Location and raid-counter state is written to `data/trader_availability_state.json` beside the mod. This state is shared across sessions on the server, rather than per profile. Simultaneous Fika players may therefore influence each other's route state; independent per-player routing is not implemented. New destinations may still have client/game restrictions that a database flag cannot fix.

Source metadata targets `~4.0.0`. Transit, scav-access, trader-unlock, profile-editing, and raid-hook mods may conflict. No exhaustive compatibility testing was performed. Server compilation does not verify transit gameplay or multiplayer synchronization.

## License and validation

Original source metadata declares MIT; repository MIT licensing covers this module's original code and config. SPT, EFT, and referenced assemblies retain their own licenses and are not distributed. Trader constants identify game data, not user profiles.

Release preparation checks compilation against local assemblies. No game/server launch or live profile change was performed.
