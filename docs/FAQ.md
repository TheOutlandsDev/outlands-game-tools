# Questions, limits, and troubleshooting

Start with [Getting started](GETTING-STARTED.md) for tool selection and build paths. Each [module README](../README.md) describes its own behavior. If something still does not fit, open an issue with a short explanation. Questions, rough ideas, and reports of what worked are useful too.

## What is actually ready?

The source was prepared for public review, compiled where applicable, and exercised with the offline checks recorded in [VALIDATION.md](../VALIDATION.md). That does not mean the entire collection has been tested together in a game.

The preparation did not launch a game or SPT backend, complete a raid, test two-PC Fika play, validate the live browser dashboard, or run the third-party Fika installer. Treat runtime behavior, compatibility, overhead, and profile-changing operations as work still to verify.

## Do I install everything?

No. Pick the module that solves your problem. The telemetry and diagnostics plugins have separate capture formats. Small compatibility patches target specific behavior. Scav Life is a related stack: its client and console depend on the framework routes. Fika helpers require their separately obtained compatible installer or an existing headless installation.

There is no supported all-in-one modpack or automatic dependency setup in this repository.

## Does this include EFT, SPT, Fika, or other mods?

No. The repository contains the selected original tool/mod source, documentation, default configurations, and synthetic tests. Obtain the game and dependencies separately. See [THIRD-PARTY.md](../THIRD-PARTY.md) for the license boundary.

MIT covers this collection's original contributions. It does not give permission to redistribute proprietary game assemblies, assets, another mod's implementation, or other external components under MIT. A compiled distribution needs its own dependency review.

## Which versions are supported?

The local compile baseline was SPT 4.0.13, EFT 0.16.9.40087, and BepInEx 5.4.23.2 where applicable. Several server metadata records target `~4.0.0`. That identifies the source's intended API generation; it does not establish compatibility with every 4.x build or mod combination.

Reports from other versions are welcome. Include exact versions, the module/repository revision, what you tested, and whether the result was a compile check, synthetic test, client launch, raid, or multiplayer session. Do not describe an untested version as supported based only on a successful build.

## Why does a build ask for GameRoot or SptServerDirectory?

`GameRoot` points to the full installation, such as `D:\Games\SPT`. `SptServerDirectory` points to its server assembly directory, such as `D:\Games\SPT\SPT`. Mixing the two is a common source of missing-reference errors.

Use the parameter in that module's actual build script. The [build table](GETTING-STARTED.md#compile-one-module) groups the scripts by their parameters. References stay in your installation; do not add DLLs to the source repository.

## The build cannot find an assembly or reference pack. What should I check?

Check the supplied directory, the exact dependency filenames in the project's `.csproj`, the installed SDK, and the target framework. Scav Life Client targets .NET Framework 4.7.2 and needs its reference assemblies; other client projects target .NET Standard 2.1, and the server projects target .NET 9.

Use dependencies from one compatible installation rather than mixing arbitrary DLL versions. Several modules deliberately disable NuGet package feeds; they fail if required local SDK packs are missing. Scav Life's normal builds may restore SDK dependencies. `-NoRestore` cannot replace a missing initial restore.

If the error refers to Windows SDK registry discovery, include that sanitized error in your report. The preparation sandbox used explicit installed targeting paths or SDK discovery overrides for some builds; those environment restrictions do not prove the source is broken on an ordinary Windows installation.

## Does running a build change my game?

Default builds do not install into or launch the game. Codex Diagnostics, QuakeBrain, Vagabond Scav Access, and FPV Parent Cache Preload can copy their own DLL if you explicitly pass `-InstallDirectory`. Scav Life's `-OutputDirectory` selects its package output. Choose destinations carefully.

The Fika scripts are separate operational helpers. They preview by default; `-Apply` permits their documented installation/configuration/move operations. Read their README before using them.

## I installed a DLL, but nothing appears. Is the module broken?

Confirm the correct client or server destination, the assembly filename, the module's dependencies, and whether the host actually loaded it. Review a short local startup excerpt for load errors. A compile result cannot show that BepInEx or the server loaded the assembly in your current setup.

Avoid moving a collection of unknown DLLs around to experiment. Use one backed-up test installation, one module change at a time, and the exact versions in the report. For the Scav Life panel, also check its `F8` toggle and the companion framework's routes.

## Why are there no diagnostic or telemetry reports?

The summarizers do not create capture data. The corresponding plugin must have loaded and produced it during runtime. Confirm its generated BepInEx configuration, capture settings, log directory, and filenames before running the summarizer.

Codex Diagnostics uses `Logs/CodexDiagnostics/client-*.jsonl`; QuakeBrain uses `Logs/QuakeBrainTelemetry/raid-*.jsonl` under the game installation. Select the exact file with `-Path` or use the documented capture-directory parameter. There are no real player logs included as samples.

## Does QuakeBrain improve AI behavior?

The current module is passive telemetry. It records observations and optional advisory utility scores; it does not take control of bots. Future behavior layers and ML helpers are ideas, not shipped functionality. Position samples and generic raycast probes also do not establish what the game's actual AI perceived.

Useful next steps include measurement quality, runtime overhead checks, privacy controls, and clear interpretation of the captured fields. See the [roadmap](ROADMAP.md).

## Is Scav Life a finished persistent scav mode?

No. It is a framework prototype with state tracking, customization, raid-plan suggestions, and pending-haul/stash integration. It can alter persistent state and inventory. Live raid capture, migrations, transfers, and coexistence with other mods still need runtime validation.

Use a disposable profile or a verified backup before testing it. Post-raid audit output is disabled by default; if enabled, those files can contain private identifiers and inventory data. Keep runtime state out of issues and pull requests.

## The console opens, but its backend calls fail. What should I check?

Check that you started your own compatible backend, selected the correct `-GameRoot`, supplied the intended `-ProfileId`, and installed the matching framework routes. The console is a separate local listener; opening its page does not start SPT or make backend routes available.

The default listener is `http://127.0.0.1:7777/`, and the default backend is `https://127.0.0.1:6969`. Both endpoints must use literal loopback IP addresses. Profile IDs are limited to 1-64 letters, digits, underscores, or hyphens. Those checks are intentional.

## Why does the console reject my self-signed certificate?

It uses normal TLS certificate validation. Configure a trusted local certificate that is valid for the configured backend endpoint. The public release removes the unconditional certificate-acceptance callback; there is no blanket bypass option to turn on.

Do not send certificate private keys, passwords, or your whole machine's certificate export in a bug report. A sanitized exception and the endpoint scheme/loopback-port choice are enough to start describing the problem.

## Why does a console request return 403, 405, or 415?

The console expects its own same-origin UI. It checks the Host header, browser Origin/Fetch Metadata, JSON content type, and random per-run API token. External sites, stale pages after a restart, manual cross-origin requests, and missing headers can be rejected.

Reload the page from the exact listener URL after restarting. State-changing proxy routes also return 403 unless you explicitly enabled them with `-EnableMutations`. Do not loosen request checks to make an unrelated frontend connect. A report should state the action and status code without copying the token.

## How do I enable Scav Life debug operations?

Only do this in a disposable or backed-up test profile. Backend debug seed, complete-run, and reset methods require `developmentMode=true` in the framework config. The console additionally requires `-EnableMutations` to expose its mutation routes.

`Test-ScavLifeFramework.ps1` is a destructive integration smoke test that resets its selected framework state and simulates outcomes. Both that script and `Set-ScavLifeCustomization.ps1` require `-AllowStateChanges`. They are not part of the offline checks. Default display routes can still initialize backend state, so the console's default mode should not be treated as a promise of zero writes.

## Can I use the dashboard over the internet or expose it through a tunnel?

The implemented workflow is trusted-local use on loopback. The framework does not add independent backend authentication, and the console is not designed as a public service. Its local browser request checks do not authenticate other programs running under your account or harden the separate SPT backend.

Remote administration would need a separately reviewed design. It is not a supported switch in this release.

## Why did traders change, and why did removing Open Scav Transits not restore them?

Its optional trader feature updates profile trader `Disabled`/`Unlocked` flags, which can be saved. The included configuration enables that feature. Read and edit the config before first use if you want only transit adjustments.

Removing the plugin does not reverse persisted profile edits. Restore a known-good backup or inspect the affected flags separately. Route state is currently shared by server sessions, so concurrent players can influence each other's trader route. See [Open Scav Transits](../spt/OpenScavTransits/README.md).

## Can Fika helpers recover my installation automatically?

They provide explicit setup/configuration/plugin moves, not general recovery. Repair saves previous files to a unique backup directory with a manifest. Pruning moves selected entries rather than deleting them. The [Fika README](../spt/FikaHeadless/README.md) explains how to inspect the manifests and restore files while processes are stopped.

The wrappers do not obtain credentials, change firewall/VPN settings, create your profile, or validate the third-party installer end to end. The actual installer is separate software and may perform its own operations. Symlink-based installations are deliberately unsupported by these helpers.

## Can I post logs, inventories, screenshots, or save files with an issue?

Prefer a short redacted error excerpt or a synthetic reproduction. Do not attach whole logs, profiles, saves, backend state files, tokens, credentials, device identifiers, private network addresses, or certificate material.

Telemetry can include account/profile IDs, nicknames, group IDs, equipment, paths, positions, and free-form messages. Inventory reports can reveal private filenames even though they omit file contents. Screenshots can expose all of the same information. Reports and captures have no anonymization or upload service. Review them locally before sharing anything.

For a security concern, do not publish exploit steps or sensitive data in an ordinary public issue. Check whether this repository offers GitHub private vulnerability reporting. If it does, use that route; otherwise, a public issue should only ask for a private reporting route without disclosing the sensitive details.

## Will issues get a response or roadmap date?

Suggestions, questions, bug reports, docs fixes, and pull requests are welcome. Public feedback can help identify useful priorities, but there is no guaranteed response time, support commitment, or delivery date. A small reproducible report is easier to assess than an entire modpack archive.

Use [the contribution guide](../CONTRIBUTING.md) for a useful report or change proposal. If the existing forms do not fit, blank issues remain available.
