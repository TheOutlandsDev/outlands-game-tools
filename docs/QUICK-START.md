# Download and try one tool

The [v0.1.0 source pre-release](https://github.com/TheOutlandsDev/outlands-game-tools/releases/tag/v0.1.0)
is the first tagged collection download. It contains original source, tests,
generated-example scripts and documentation under the root MIT license. It
contains no installed games, upstream mod payloads, saves, real logs, compiled
plugins or native Python dependency wheels. It is an experimental source kit;
the version does not establish gameplay compatibility for every module.

**New on main after v0.1.0:** [XML Mod Configuration Diff](../tools/xml-config-diff/README.md)
compares selected XML configuration files, the
[Mod Asset Reference Checker](../tools/mod-asset-reference-checker/README.md)
inspects supported literal LTX references, and
[INI/LTX Configuration Value Diff](../tools/ini-ltx-value-diff/README.md)
compares stored literal settings in a selected pair. Download the current repository with
**Code → Download ZIP** for these additions; they are absent from the v0.1.0 assets.
Follow each module's requirements and original example. XML comparison has an
additional Expat version check; the asset and INI/LTX checkers use only the standard library.
The tagged download instructions below still apply to the v0.1.0 snapshot.

## Download and verify

Open the release page and download both custom assets:

- `outlands-game-tools-v0.1.0-source.zip`
- `outlands-game-tools-v0.1.0-source.zip.sha256`

GitHub also offers automatically generated source archives. The checksum above
applies only to the specifically named custom ZIP, not those automatic archives.
From PowerShell in your download folder:

```powershell
$zip = 'outlands-game-tools-v0.1.0-source.zip'
$expected = ((Get-Content -LiteralPath ($zip + '.sha256') -Raw) -split '\s+')[0]
$actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw 'ZIP checksum mismatch; do not use this download.' }
Expand-Archive -LiteralPath $zip -DestinationPath '.\outlands-source-extracted'
Set-Location '.\outlands-source-extracted\outlands-game-tools-v0.1.0'
py -3.12 -B tools\verify_source_release.py
```

Use a new extraction folder outside games, saves and mod-manager folders.
`py -3.12` means a separately installed Python 3.12 interpreter; Python 3.13
is also tested. Use `python` after checking its version if you do not have the
Windows launcher. Linux users can run `sha256sum -c` on the checksum file,
extract the ZIP with their archive tool, and use `python3 -B` for commands.

A matching SHA-256 detects a difference from the published checksum. It does
not authenticate the author if an attacker can replace both assets. The source
manifest separately checks the selected unpacked files against reviewed hashes;
neither check proves ownership or game compatibility.

## Choose the tool for the job

You do not need to install the whole collection into a game. Most standalone
tools use Python's standard library and run directly from the extracted source.
Read the linked module guide before selecting inputs or creating outputs.

| Job | Guide | Requirements and limits |
|---|---|---|
| Compare mod file contents between folders or selected MO2 profiles | [Mod Content Manifest & Diff](../tools/mod-content-manifest/README.md) | Python 3.12+; read-only hashes and comparison reports. Matching manifests do not prove current live files or game/network compatibility. |
| Back up selected saves/configuration and verify copies | [Save Snapshot Verifier](../tools/save-snapshot-verifier/README.md) | Python 3.12+; creates a new snapshot; no automatic restore or retention deletion. |
| Make a separate limited MO2 comparison profile | [MO2 Baseline Profile Builder](../tools/mo2-profile-builder/README.md) | Python 3.12+; preview first; apply requires closed-program attestation. Saves/settings may remain shared. |
| Inspect saved MO2 loose-file priority and possible conflicts | [MO2 Conflict Inspector](../tools/mo2-conflict-inspector/README.md) | Python 3.12+; does not mount the live VFS or unpack archives. |
| Check Lua syntax without running inspected chunks | [Lua Syntax Checker](../tools/lua-syntax-checker/README.md) | Python 3.12+ plus separately installed pinned Lupa; select the intended parser. |
| Decode-check selected loose audio | [Audio Integrity Checker](../tools/audio-integrity-checker/README.md) | Python 3.12+ plus separately installed pinned SoundFile/NumPy; no playback or repair. |
| Summarize selected X-Ray log markers | [X-Ray Log Summary](../tools/xray-log-summary/README.md) | Python 3.12+; static categories/counts/line numbers, not raw log excerpts or a complete redactor. |
| Inspect a selected LTX declaration/include graph | [LTX Definition Inspector](../tools/ltx-definition-inspector/README.md) | Python 3.12+; narrow structural syntax; unsupported DLTX makes the report incomplete. |
| List filtered folder/file metadata | [Game Folder Inventory](../tools/game-tree-exporter/README.md) | Python 3.12+; metadata only, without reading contents. |
| Observe the native exit code of a process you start | [Process Exit Observer](../tools/process-exit-observer/README.md) | Windows PowerShell; does not start or stop the game. |
| Build a reviewed source ZIP from its manifest | [Verified Source Release Builder](../tools/source-release-builder/README.md) | Python 3.12+; maintainer utility; source files only and new outputs. |

Each module includes its own commands and scope notes. The newer standalone
tools include generators that create original toy files in a new external
folder. Try those before supplying real data. Game files are unnecessary for
the synthetic test suites. Run tests from the relevant tool directory:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Python 3.12/3.13 on Windows/Ubuntu are exercised in CI for the documented
portability jobs. Native link/case fixtures have explicit platform skips.
These checks do not establish macOS or engine/gameplay compatibility.

## SPT source modules

Start with [Getting started](GETTING-STARTED.md) and the chosen module's README.
C# plugins need the separately installed compatible game/server references and
documented .NET targeting tools. The source ZIP has no compiled plugin DLLs or
game assemblies. Build only the selected module; installing into a test game is
a separate explicit step. Compilation is separate from runtime, raid and Fika
multiplayer testing. See [VALIDATION.md](../VALIDATION.md) for actual evidence.

## Reports and feedback

Keep real reports, saves, logs and snapshots local. Relative filenames, mod
names, sizes, hashes, settings and session context can still disclose private
information even when absolute roots/source text are omitted. Never upload a
whole installation or real snapshot to demonstrate a problem.

[Suggestions, questions and bug reports are welcome](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new/choose).
Name the tool, version, operating system, sanitized command, exit code and what
you expected. Prefer the generated example or a small original reproduction.
Documentation feedback is useful without code. See [CONTRIBUTING.md](../CONTRIBUTING.md)
and [dependency/license boundaries](../THIRD-PARTY.md).
