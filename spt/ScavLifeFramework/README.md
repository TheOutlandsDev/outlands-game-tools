# Scav Life Framework (experimental)

MIT-licensed source for a persistent scav state prototype for SPT 4.0.x. It records scav raid outcomes, tracks a dossier and raid plan, supports customization, and can move a survived pending haul into its separate stash only after removing matching PMC items. This can change profile inventory; use disposable or backed-up test profiles.

The repository contains original mod source and a default configuration. SPT, Fika, Unity, game binaries, user profiles, logs, and saved state are not included or covered by this repository's license. The original metadata declares MIT and SPT `~4.0.0`; compatibility with other versions has not been established.

## Build

Requires .NET SDK 9 and your own compatible SPT installation. Run from this module:

```powershell
.\Build-ScavLifeFramework.ps1 -GameRoot 'D:\Games\SPT'
```

`GameRoot` is the installation containing the `SPT` subdirectory. Dependencies are referenced in place with `Private=false`. Output is placed under `artifacts/ScavLifeFramework`; the script never installs into the game. `-OutputDirectory` changes the package destination; `-NoRestore` uses an existing restore. A normal build may restore SDK dependencies. No game or dependency DLL is packaged.

To install manually into a backed-up test installation, copy the built assembly and default `config` folder into `SPT/user/mods/000-ScavLifeFramework`. Do not overwrite an existing custom configuration without reviewing the changes. Runtime state is written under that mod's `data` directory. Keep these files private: post-raid audit files can contain profile and inventory identifiers.

## Defaults and test helpers

- `developmentMode=false`: debug seed, complete-run, and reset methods refuse mutations until explicitly enabled in the installed config.
- Live-scav customization sync and automatic stash storage are off. Raid observation and pending-haul capture are enabled.
- Post-raid audit-file output is off. Enabling it produces private telemetry, not release content.
- SPT routes are intended for a trusted local installation. This prototype does not add independent authentication to the backend. Do not expose the SPT backend to an untrusted network.

`Test-ScavLifeFramework.ps1` is a **destructive integration smoke test**, not an offline unit test. It resets its selected Scav Life state, applies customization, and simulates outcomes. It refuses to run without `-AllowStateChanges`; debug operations also require `developmentMode=true`. Use only a disposable profile, for example `local-test`, on your own loopback backend. `Set-ScavLifeCustomization.ps1` likewise requires `-AllowStateChanges`.

Both helpers use normal TLS certificate validation, reject non-loopback backend URLs, and disable redirects. Configure a trusted local certificate if your HTTPS backend uses a self-signed certificate. There is no blanket certificate bypass.

## Validation and limits

Publication preparation includes source inspection and offline compilation against the installed dependencies. No integration helper, game client, SPT backend, or raid was run. Inventory transfers, real raid capture, save migration, coexistence with other mods, and two-PC Fika play remain unverified. This is a development prototype, not a finished persistent scav mode.
