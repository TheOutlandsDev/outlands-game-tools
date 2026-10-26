# Fika Headless Helpers

PowerShell helpers for a separately obtained Fika headless client: invoke its installer, preview/repair selected launch and network configuration, verify backups, restore original configuration, and move explicitly selected plugins out of the load path. These are original wrapper scripts, not Fika itself. Fika, SPT, EFT, and all plugins retain their own licenses and are absent from this source release. See [provenance](PROVENANCE.md).

The release replaces machine-specific paths, automatic profile discovery, embedded VPN addresses, and a fixed plugin-removal list with explicit inputs. Every script previews by default. Use `-Apply` to change files; `-WhatIf` still suppresses those changes. Stop the game, server, and headless manager before applying changes, and keep a profile backup.

## Install wrapper

Place your compatible `Fika-Installer.exe` in the main SPT directory. Select an existing Fika headless profile and a **new**, separate headless directory:

```powershell
.\Install-FikaHeadless.ps1 -MainSptRoot 'D:\Games\SPT' -HeadlessRoot 'D:\Games\SPT-Headless' -ProfileId 'YOUR_HEADLESS_PROFILE_ID'
```

Review the preview, then repeat with `-Apply`. This wrapper uses `HardCopy`, invokes the local third-party installer, and does not configure or prune plugins afterward. The installer may perform its own downloads or profile operations; review its documentation and version before execution. No installer was run during release preparation.

## Repair configuration

The profile must already exist at `SPT/user/profiles/<ProfileId>.json`; nothing is guessed from your latest profile. Choose the backend URL and host IP appropriate for your own setup:

```powershell
.\Repair-FikaHeadlessConfig.ps1 -MainSptRoot 'D:\Games\SPT' -HeadlessRoot 'D:\Games\SPT-Headless' -ProfileId 'YOUR_HEADLESS_PROFILE_ID' -BackendUrl 'https://127.0.0.1:6969' -ForceIp 'Disabled' -BindIp 'Disabled' -UdpPort 25565
```

Preview is the default: it lists the selected relative paths and before/after
SHA-256 fingerprints without creating files or directories. Add `-Apply` after
review; `-Apply -WhatIf` remains read-only. Inputs are re-read and validated on
each invocation, so a prior preview does not approve later file contents.

The default scope is exactly three files:

| Root | Relative path | Change |
| --- | --- | --- |
| Headless | `BepInEx/config/com.fika.core.cfg` | Replace exactly one existing `Force IP`, `Force Bind IP` and `UDP Port` value. |
| Headless | `HeadlessConfig.json` | Set top-level `ProfileId` and `BackendUrl`; add `StartMinimized: false` only if absent. |
| Main | `SPT/user/mods/fika-server/assets/scripts/<ProfileId>/HeadlessConfig.json` | Same selected launch settings, preserving unrelated content. |

Existing JSON properties, nested values, numeric text, whitespace and UTF-8 BOM
are retained outside selected edits. An existing `StartMinimized` boolean is
preserved. Missing launch files may be created; an existing empty/malformed file
is rejected. Fika core settings must exist exactly once across the selected
file; duplicate section-local keys are deliberately ambiguous and rejected.
Optional `-IncludeMainClient` applies those same three core settings to the
main client's existing `BepInEx/config/com.fika.core.cfg`, adding a fourth file.
The selected profile file must exist, but its contents are never read.

`BackendUrl` must be an HTTP(S) origin, for example
`https://127.0.0.1:6969`, without a path, query, fragment or embedded credentials.
`ForceIp` and `BindIp` are literal IP addresses or `Disabled`; `UdpPort` is
1 through 65535. These are operator-selected settings, not a connectivity test.

### Try fictional files first

Run from this module's folder in Windows PowerShell 5.1 or PowerShell 7 on Windows.
No extra package, game, installer, server or account is needed for the demo.
Choose a **new** destination; never point this generator at a real installation.

```powershell
.\Create-FikaRepairDemo.ps1 -Destination 'D:\Scratch\FikaRepairDemo'
$settings = @{
    MainSptRoot = 'D:\Scratch\FikaRepairDemo\Main'
    HeadlessRoot = 'D:\Scratch\FikaRepairDemo\Headless'
    ProfileId = 'demo_headless'
    BackendUrl = 'https://127.0.0.1:6969'
    ForceIp = '192.0.2.42' # documentation-only address; not a real host
    BindIp = 'Disabled'
    UdpPort = 25565
}
.\Repair-FikaHeadlessConfig.ps1 @settings
.\Repair-FikaHeadlessConfig.ps1 @settings -Apply -WhatIf
.\Repair-FikaHeadlessConfig.ps1 @settings -Apply
```

The preview reports three selected configurations, including the missing
server launch file. Applying prints a private `_outlands_backups/<unique-id>`
directory. The demo's `FictionalNote` and `StartMinimized: true` survive.
The `192.0.2.42` setting is only to demonstrate a visible change: choose actual
settings from your own supported installation when working outside the demo.
No command above starts a server or connects to the address.

### Restore verified backups

All original bytes are copied into a new recovery directory and verified before
the first configuration write. `manifest.json` maps only the fixed selected
paths to original and repaired hashes. Existing targets are held with exclusive
handles during writes and rechecked against the plan. New files use exclusive
creation. Output is flushed and re-read for verification.

Use the directory printed by your repair, with the same main/headless roots:

```powershell
$recovery = @{
    MainSptRoot = $settings.MainSptRoot
    HeadlessRoot = $settings.HeadlessRoot
    BackupDirectory = 'D:\Scratch\FikaRepairDemo\Headless\_outlands_backups\REPLACE_WITH_PRINTED_ID'
}
.\Restore-FikaHeadlessConfig.ps1 @recovery
.\Restore-FikaHeadlessConfig.ps1 @recovery -Apply -WhatIf
.\Restore-FikaHeadlessConfig.ps1 @recovery -Apply
```

Restore verifies all selected original backups and current destinations before
changing any configuration. It restores exact original bytes and removes a
newly created launch file only while its hash still matches this repair. It
refuses later user edits, missing originally existing files, corrupt backups,
unexpected paths and mismatched roots. Already-restored originals and already
absent newly created files are accepted, so a completed restore can be repeated.
Recovery files and empty directories are retained. **Use only your own trusted
backups**: hashes detect mismatches, not deliberate changes to both a manifest
and its data. Old backups made by earlier versions use a different format and
need the earlier manual recovery instructions.

### Boundaries and interrupted operations

Repair and restore support **fixed local NTFS volumes on Windows**. Linked paths,
hard-linked files, overlapping installations, UNC/network roots, alternate
streams, unsupported encodings, inputs over 1 MiB, excessive nesting, duplicate
JSON keys (including case variants), JSON comments and trailing commas are
rejected. Accepted encoding is strict UTF-8, with or without BOM. JSON nesting
is bounded to 24 containers and token count to 32,768. Conservative rejection
can require you to normalize an unsupported configuration yourself first.

Stop EFT, SPT, Fika headless managers, launchers and anything else writing these
configurations before preview/apply/restore. The script does not stop processes
or prove they are stopped. Use an isolated backed-up installation. This is not
an adversarial filesystem race boundary, and multi-file writes are **not atomic**.
An I/O error, disk loss or power failure can leave partial changes despite the
retained originals. Keep the printed recovery directory. If the restore command
rejects a partially written file, keep all files and inspect the manifest and
original bytes before performing manual recovery. Do not edit hashes to force
a restore. No automatic rollback or power-loss guarantee is claimed.

The repair deliberately excludes automatic profile discovery, all-profile
updates, launcher-wide URL replacement, server `fika.jsonc`, AI location/mod
templates, VPN/firewall/TLS changes and game launches. The historical local
repair input covered some of these; they are not safely inferred from a
generic installation. No current SPT/Fika gameplay compatibility is claimed.

### Privacy, tests and feedback

Public source and generated examples contain fictional values. Your previews,
errors and recovery manifests may contain paths, profile labels and hashes;
backup bytes contain your original configurations. Keep them private. Share a
small invented reproduction instead of real output or backup folders. The tool
does not automatically upload reports, contact endpoints or discover profiles.

```powershell
.\Test-FikaHeadless.ps1
.\Test-FikaRepair.ps1
```

These generate disposable files and exercise real Windows file operations,
including hard-link and junction rejection. Windows permissions must allow
creating those test links. No game, installer or network operation is run.
See [the review and validation record](../../docs/FIKA-REPAIR-2026-10-26.md).

[Report a repair bug or suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=fika_repair.yml).
Suggestions, alternative approaches, documentation fixes and fictional test
cases are welcome; you do not need to contribute code.

## Disable selected plugins

The tool does not decide which mods a particular headless setup needs. Supply direct child filenames/folder names from its plugin directory:

```powershell
.\Prune-FikaHeadlessClient.ps1 -HeadlessRoot 'D:\Games\SPT-Headless' -PluginName 'ExampleVisualPlugin.dll','ExampleUiPlugin'
```

Repeat with `-Apply` to move those entries into a fresh `_outlands_disabled` directory. Nothing is deleted or overwritten. `moves.json` records source/destination pairs for manual restoration while processes are stopped. It is a planned-moves manifest, so inspect the two locations if an I/O failure interrupted the move. Never disable Fika or required raid/dependency plugins without checking their requirements.

## Limits and validation

Windows PowerShell 5.1 or PowerShell 7 on Windows. This layout and installer syntax come from a local SPT 4.0.x/Fika setup; no precise Fika version was encoded by the original scripts. Changes to installer CLI/config layout need review. Drive roots, overlapping main/headless roots, reparse-point paths, plugin traversal names, and invalid network/profile inputs are rejected. Symlink-based installs are unsupported. The helpers do not manage TLS certificates, firewall rules, VPNs, services, profile generation, or game launches.

`Test-FikaHeadless.ps1` retains the existing wrapper regression checks.
`Test-FikaRepair.ps1` adds the repair/restoration cases described above.
End-to-end installer behavior and multiplayer hosting remain unverified.
Source is covered by the repository MIT license; dependency and inspected-file
rights remain separate. Installer/pruning helpers retain their earlier behavior
and do not acquire the repair engine's stronger backup or restore guarantees.
