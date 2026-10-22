# Contributing, questions, and suggestions

Suggestions, bug reports, documentation fixes, compatibility results, and pull requests are welcome. These tools started in a personal game setup; opening the source is a chance to make the useful parts easier for other people to understand and improve. You do not need a finished implementation to suggest a better approach.

If a tool helped, failed, or was confusing to set up, say what happened. Constructive criticism and simpler alternatives are useful. There is no guaranteed response time, support commitment, or delivery date, and an open roadmap item is not a promise that it will ship.

## Start with the right context

Read [Getting started](docs/GETTING-STARTED.md), the relevant module README, and [the FAQ](docs/FAQ.md). Check existing issues when practical so related reports can stay together. The [roadmap](docs/ROADMAP.md) lists useful next work and smaller contributions, but other ideas are welcome too.

The repository contains original source and synthetic tests. The games, dependency assemblies, profiles, and upstream mods are obtained separately. [THIRD-PARTY.md](THIRD-PARTY.md) explains what the MIT license covers.

Use the Bug report form for unexpected behavior and the Feature or suggestion form for ideas, requests, questions about direction, and improvements. Blank issues remain available if neither form fits. A clear short issue is better than an oversized report with private data.

## Report a bug or compatibility result

Include the module name and repository revision, the exact game/SPT/plugin versions involved, your Windows/PowerShell/.NET versions where relevant, and the command or UI action after replacing personal paths and identifiers. Explain the expected result, actual result, and the smallest steps that reproduce it.

State what you actually checked:

- Source inspection or compilation only.
- An offline test using synthetic files or fixture processes.
- Client/server loading in a backed-up test instance.
- A specific raid or profile-changing flow.
- A multiplayer flow, identifying the host/client setup without private addresses or player IDs.

If you could not test a stage, say so. A successful compile is useful evidence, but it does not prove raid behavior, performance, save safety, or multiplayer compatibility. A report that a documented version works is welcome if it describes the tested scope.

For log-related bugs, start with the exception type and a few redacted lines surrounding the failure. A small synthetic example that reproduces a parser problem is especially helpful. If the problem only occurs in a larger mod stack, summarize the relevant dependencies and changes instead of uploading the installation.

## Keep public reports private-data free

Do not attach full diagnostic captures, telemetry files, profiles, saves, backend state, credentials, session/API tokens, certificate private keys, private network addresses, device identifiers, or whole-game archives. This also applies to screenshots, filenames, commit messages, and commands pasted into an issue.

QuakeBrain and diagnostics captures can include account/profile IDs, nicknames, group IDs, equipment, coordinates, local paths, and free-form error text. Inventory reports can expose private filenames. Backups and Fika manifests can reveal profile IDs and local installation details. There is no automatic anonymization or telemetry-upload service.

Keep the originals locally and write a small redacted description or synthetic fixture. Remove identifiers consistently so the example is still understandable. Never replace real credentials with another working credential. You do not need to share your entire log to ask for help.

For a suspected security vulnerability, check whether GitHub private vulnerability reporting is available for this repository. Use it if enabled. If no private route is listed, open a public issue that asks for a private reporting route without posting exploit details, secrets, or affected users' data. Do not assume a private inbox or response schedule exists.

## Suggest a feature or different direction

Describe the problem you want to solve, who encounters it, and what a useful result would look like. Include a concrete example when possible. Alternatives and tradeoffs are welcome, including reasons the existing approach may be too complicated.

It is fine to say you are unsure how to implement the idea. Do not promise a feature on behalf of the project. If you want to work on a large change, start with an issue so its scope, compatibility effects, and validation can be discussed before a substantial rewrite.

Small pull requests do not need an issue first. Good candidates include a corrected instruction, a focused error message, an input-validation fix, a synthetic regression case, or a compatibility change with clear evidence.

## Make a focused pull request

Explain the user-visible problem and resulting behavior. Identify the affected module, versions, important tradeoffs, and validation you performed. Keep unrelated cleanup separate so the change is easy to review. Screenshots are optional and must be redacted.

Include only source you have permission to publish. Original contributions are offered under the root [MIT license](LICENSE). Identify any adapted upstream implementation with its source, license, required notices, and the exact portion reused. Do not add a conflicting license or assume dependency APIs, game assets, and upstream code are covered by this repository's MIT license.

Do not add game/SDK/mod binaries, installers, proprietary assemblies, real captures, player data, secrets, or generated build output. Keep game references external and parameterized. Default builds must remain build-only; installation or other operational changes need clear explicit inputs and the module's documented opt-in behavior.

Use synthetic fixtures for parser, inventory, backup, and request-policy tests. Avoid tests that require a game launch, real backend, player profile, network download, or another person's data. If a runtime test is necessary, document it separately and run it only in an authorized backed-up or disposable test setup.

AI-assisted contributions are welcome under the same review expectations: understand the code, confirm its provenance, and describe the checks you actually ran. Generated claims, unrun tests, and guessed compatibility results should not be presented as evidence.

## Check and describe the change

Run checks relevant to the code you changed. Documentation-only changes need link and content review; they do not need a game launch. Available offline commands, run from the repository root, include:

```powershell
python -B -m unittest discover -s tools/game-tree-exporter/tests -v
.\spt\CodexDiagnostics\tests\Test-Summary.ps1
.\spt\QuakeBrain\tests\Test-Summary.ps1
.\spt\ScavLifeConsole\Test-ConsoleSecurity.ps1
.\spt\FikaHeadless\Test-FikaHeadless.ps1
.\tools\process-exit-observer\tests\Test-Observer.ps1 -PythonPath (Get-Command python.exe).Source
node --check .\spt\ScavLifeConsole\www\app.js
```

The process-observer test starts short-lived Python fixtures; it does not start a game. Scav Life's `Test-ScavLifeFramework.ps1` is a separate destructive integration helper and is intentionally absent from this list. Read that module's README before considering it.

For C# changes, compile against your own matching installation using the module's documented path parameter. Do not commit the referenced DLLs. Describe any build-environment overrides and any checks you could not run.

The [source manifest](SOURCE-MANIFEST.json) records the reviewed public package. Changes will produce an expected inventory mismatch until the changed files are reviewed and the manifest is regenerated. Review the diff and publication exclusions before using `python -B tools/verify_source_release.py --write-manifest`; then run `python -B tools/verify_source_release.py` again. Never regenerate it simply to conceal an unexpected mismatch. Maintainers may perform the final manifest update during review.

See [VALIDATION.md](VALIDATION.md) for preparation evidence and remaining runtime work. Helpful contributions make the limits clearer as well as the tools better.
