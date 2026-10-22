# Scav Life Console (experimental)

Local PowerShell 7 browser dashboard for the companion Scav Life Framework. It shows scav status, dossier, raid plans, local profile-health checks, installed mod summaries, and diagnostic log summaries. It reads files from an explicitly selected SPT installation and proxies a fixed set of framework routes.

## Run

Install the framework into a backed-up test SPT installation and start that backend yourself, then run from this module:

```powershell
.\Start-ScavLifeConsole.ps1 -GameRoot 'D:\Games\SPT' -ProfileId local-test -NoBrowser
```

Open `http://127.0.0.1:7777/`. Remove `-NoBrowser` to open the browser automatically. Profile IDs may contain 1-64 letters, digits, underscores, or hyphens. Use your own profile ID locally; never commit profile files or screenshots containing private identifiers.

`-SptBaseUrl` defaults to `https://127.0.0.1:6969`; `-ListenPrefix` defaults to `http://127.0.0.1:7777/`. Both must use literal loopback IP addresses. The browser listener uses HTTP on loopback only. Backend HTTPS uses normal certificate validation and redirects are disabled. Configure a trusted local certificate for a self-signed backend; this release has no blanket TLS-validation bypass.

## State changes and local request protections

State-changing proxy routes are disabled unless you explicitly start with `-EnableMutations`. This enables customization, pending-haul decisions, and debug routes. Backend debug methods separately require `developmentMode=true` in the framework config. Use disposable or backed-up profiles: reset is destructive and stash transfers can modify inventory. Even display routes can initialize framework state on the backend, so the default dashboard is not a guarantee of zero backend writes.

The dashboard serves its own assets and API on the same origin. It does not enable cross-origin access. Every API POST requires the exact local Origin, JSON content type, and a random per-run token obtained by the same-origin UI. Exact Host checks and Fetch Metadata checks reject browser cross-site requests and DNS rebinding attempts. Request bodies are capped at 1 MiB. Mutation controls are disabled in the UI while mutations are disabled on the server.

These boundaries protect a local browser workflow. They do not authenticate other programs running as your user, harden the independent SPT backend, or make this an internet-facing service. Do not proxy it publicly. Dashboard data can expose local paths, mod lists, identifiers, and log messages; keep screenshots and exports private unless redacted.

## Offline checks

```powershell
.\Test-ConsoleSecurity.ps1
node --check .\www\app.js
```

The security checks exercise pure URL/request-policy functions without opening a listener or contacting any backend. Publication preparation did not start a backend, browser dashboard, or game. Live UI behavior, real profile operations, and multiplayer compatibility remain unverified.

## License and dependencies

The original source here is covered by the repository MIT license. PowerShell/.NET, SPT, mods listed in dashboard checks, and game dependencies retain their own licenses. Their binaries, assets, profiles, runtime state, and telemetry are excluded.
