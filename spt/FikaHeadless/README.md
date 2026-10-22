# Fika Headless Helpers

PowerShell helpers for a separately obtained Fika headless client: invoke its installer, repair selected launch/network configuration, and move explicitly selected plugins out of the load path. These are original wrapper scripts, not Fika itself. Fika, SPT, EFT, and all plugins retain their own licenses and are absent from this source release.

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

With `-Apply`, this writes the headless `HeadlessConfig.json`, the matching Fika server launch config, and the existing `Force IP`, `Force Bind IP`, and `UDP Port` settings in `BepInEx/config/com.fika.core.cfg`. Missing or duplicate network settings fail before any change. Existing versions of all three files are backed up in a unique `_outlands_backups` directory, with a manifest identifying files that did not previously exist. Restore by copying backed-up files to their original paths; remove only files marked `Existed: false` if reverting newly created files. Config backups contain local paths and profile IDs: do not publish them.

## Disable selected plugins

The tool does not decide which mods a particular headless setup needs. Supply direct child filenames/folder names from its plugin directory:

```powershell
.\Prune-FikaHeadlessClient.ps1 -HeadlessRoot 'D:\Games\SPT-Headless' -PluginName 'ExampleVisualPlugin.dll','ExampleUiPlugin'
```

Repeat with `-Apply` to move those entries into a fresh `_outlands_disabled` directory. Nothing is deleted or overwritten. `moves.json` records source/destination pairs for manual restoration while processes are stopped. It is a planned-moves manifest, so inspect the two locations if an I/O failure interrupted the move. Never disable Fika or required raid/dependency plugins without checking their requirements.

## Limits and validation

Windows PowerShell 5.1 or PowerShell 7 on Windows. This layout and installer syntax come from a local SPT 4.0.x/Fika setup; no precise Fika version was encoded by the original scripts. Changes to installer CLI/config layout need review. Drive roots, overlapping main/headless roots, reparse-point paths, plugin traversal names, and invalid network/profile inputs are rejected. Symlink-based installs are unsupported. The helpers do not manage TLS certificates, firewall rules, VPNs, services, profile generation, or game launches.

`Test-FikaHeadless.ps1` validates previews, `-WhatIf`, backups, configuration replacement, selected plugin moves, invalid inputs, and root overlap using temporary synthetic folders inside this module. It does not invoke any game or installer. End-to-end installer behavior and multiplayer hosting remain unverified. Source is covered by the repository MIT license.
