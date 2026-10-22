# Roadmap and help wanted

This collection is open so the tools can be useful beyond one local setup. Suggestions are welcome, including changes to direction, simpler ways to solve a problem, and reports that a tool is unnecessary or confusing. A feature request does not need finished code.

This page describes work worth considering. It is not a release schedule or a commitment to implement every item. Scope, time, evidence, and community input will determine what moves forward. The [validation record](../VALIDATION.md) describes completed preparation checks; the items below remain open work unless a specific change and its evidence say otherwise.

## First priority: establish runtime behavior

Compilation and synthetic tests passed for the recorded preparation. The next useful evidence is from controlled tests in backed-up or disposable installations, with exact versions and a clear account of what was exercised.

| Area | Useful next check | What a good result should say |
|---|---|---|
| Diagnostics | Load the plugin, collect a short session, stop cleanly, and summarize the capture | Host versions, generated config, events present/missing, queue drops, and observed overhead. |
| QuakeBrain | Validate events across raid start/end and consecutive raids | Capture lifecycle, bot-tracking cap, missing reflection fields, file cleanup, and measured overhead. |
| Scav Life | Test real scav outcomes, restart persistence, migration, and pending-haul decisions | Disposable-profile setup, expected inventory before/after, duplicate-item checks, and failure recovery. Keep private data local. |
| Scav Life dashboard | Exercise page loading, refresh, certificate errors, and disabled mutation controls | Browser/PowerShell versions, the exact action, and sanitized status/error text. |
| Small compatibility mods | Verify the specific UI, warning, watermark, spawn, or transit behavior each targets | Exact dependency versions, visible result, and any conflict introduced by the patch. |
| Fika helpers | Review installer/config layout against a current compatible release | Actual installer version, explicit inputs, backup/restoration behavior, and what was only previewed. |
| Multiplayer | Test the relevant module in a controlled two-PC Fika session | Host/client versions, module parity, tested route or raid flow, and each player's result. |

Do not run destructive test helpers on a valued profile to gather a report. A failed or limited test is still useful if its scope is clear. "Build passed," "client loaded," "one raid completed," and "two players completed the flow" are different observations.

## Small contributions with clear value

- Try the [MO2 inspector's game-free example](../tools/mo2-conflict-inspector/README.md),
  report confusing output, or propose a small synthetic profile that demonstrates
  an unsupported file-priority case. Archive/VFS and engine merge behavior need
  separate designs; do not submit a real modpack or source dump.
- Improve a confusing setup step after trying it in a clean test folder.
- Add synthetic report fixtures covering a real format edge case after removing all private values.
- Improve actionable errors for missing dependencies or malformed input.
- Add meaningful regression cases for a bug, without launching a game or requiring proprietary downloads.
- Review issue forms and docs for accessibility, plain language, or missing assumptions.
- Test native Windows link/junction handling for the inventory exporter; preparation could not create two of those fixtures.
- Report whether cleanup and manual uninstall instructions leave the expected configuration/state files behind.

You can also open a documentation-only issue: say where you got stuck, what you expected, and what wording would have helped. First-time contributions are welcome; there is no need to claim a large feature to be useful.

## Design work that needs discussion

**Privacy controls.** Optional field minimization, explicit capture choices, redaction guidance, and safer synthetic sharing would improve diagnostics and telemetry. Collection currently stays local; no telemetry upload service is implemented. Any proposal that changes collection or sends data elsewhere needs an explicit design discussion before code is added.

**Per-player transit/trader state.** Open Scav Transits currently shares its route state across server sessions. Per-profile routing, recovery of persisted trader flags, and clear migration behavior would need careful design and tests before claiming independent multiplayer routes.

**Scav Life integrity and recovery.** Transaction boundaries, interrupted writes, duplicate-item prevention, state migrations, and manual recovery need more runtime evidence. Changes should define failure behavior as clearly as the happy path. Independent backend authorization would be a separate design task; loopback console checks do not supply it.

**Version compatibility.** A small evidence-backed compatibility table is useful. Automatic claims based only on version ranges are not. Ports should document changed APIs and distinguish compile results from actual gameplay validation.

**QuakeBrain direction.** Passive capture and interpretation should be understandable and measurable before additional behavior layers are considered. AI-control or ML features are not implemented; proposals should identify the actual gameplay problem, required data, performance budget, and a way to test whether the change helps.

**Release ergonomics.** Clearer build discovery and repeatable source packaging are useful. Any future compiled releases need dependency/license review, versioned compatibility evidence, and a plan that avoids bundling game or upstream mod binaries.

## Keep the scope understandable

The collection does not currently provide a whole-game installer, a prebuilt modpack, internet hosting or a cloud telemetry platform. Ideas outside the present scope can still be discussed, but they should be described as proposals rather than existing capabilities.

Keep default builds separate from installation and preserve explicit opt-ins for operational changes. Prefer a focused fix with a clear test over a broad rewrite that makes compatibility harder to evaluate. Do not include game assets, upstream mod payloads, profiles, or real telemetry in a contribution.

## Share an idea or offer help

Open an issue with the problem you want solved, the module involved, and the behavior you would find useful. Screenshots and code are optional; a clear explanation is enough to start. For a compatibility report, include versions and what you actually checked. For a pull request, keep the change focused and explain its validation.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for privacy guidance and review expectations, [Getting started](GETTING-STARTED.md) for setup, and [the FAQ](FAQ.md) for common limits. There is no guaranteed response time or delivery date. Constructive disagreement, alternative approaches, and public suggestions are welcome.
