# Download and try one tool

**v0.2.0-rc.1 review candidate.** Use the reviewed custom ZIP and checksum
supplied together for review. Confirm public download availability on the
[release list](https://github.com/TheOutlandsDev/outlands-game-tools/releases).
The earlier published
[v0.1.1-rc.1 source prerelease](https://github.com/TheOutlandsDev/outlands-game-tools/releases/tag/v0.1.1-rc.1)
contains eleven tools; this candidate contains all nineteen.

The eight additions cover XML and INI/LTX comparisons, literal asset references,
PAK and ZIP metadata, saved MO2 changes, authored dependency rules and captured
session evidence. Source, tests, original example generators and documentation
are included under the existing license boundaries. Game/mod payloads, real
profiles/saves/logs, compiled plugins and installed dependency wheels are absent.

## Verify and extract the review package

Keep these exact companion assets together:

- `outlands-game-tools-v0.2.0-rc.1-source.zip`
- `outlands-game-tools-v0.2.0-rc.1-source.zip.sha256`

GitHub's automatic source archives are different containers and do not use the
custom ZIP's checksum. From PowerShell in the folder containing both files:

```powershell
$zip = 'outlands-game-tools-v0.2.0-rc.1-source.zip'
$expected = ((Get-Content -LiteralPath ($zip + '.sha256') -Raw) -split '\s+')[0]
$actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw 'ZIP checksum mismatch; do not use this package.' }
Expand-Archive -LiteralPath $zip -DestinationPath '.\outlands-v020-review'
Set-Location '.\outlands-v020-review\outlands-game-tools-v0.2.0-rc.1'
py -3.12 -B tools\verify_source_release.py
```

Choose a new extraction folder outside games, saves and mod managers. `py -3.12`
means a separately installed Python 3.12 interpreter; use a checked `python`
command if the launcher is unavailable. Linux users can run `sha256sum -c` on
the checksum, extract the ZIP and use `python3 -B`. The XML tool separately
requires Expat 2.7.2 or newer, regardless of Python version:

```sh
python3 -c "import xml.parsers.expat as e; print(e.EXPAT_VERSION); assert e.version_info >= (2, 7, 2)"
```

A checksum detects a difference relative to the supplied value; it does not
independently authenticate its publisher. The source inventory checks unpacked
paths, lengths and full hashes. Neither check proves game compatibility.

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
| Compare XML structure and selected values | [XML Mod Configuration Diff](../tools/xml-config-diff/README.md) | Python 3.12+ and Expat 2.7.2+; namespace-aware comparison with conservative matching. No effective configuration or engine validation. |
| Inspect literal LTX asset and section references | [Mod Asset Reference Checker](../tools/mod-asset-reference-checker/README.md) | Python 3.12+; distinguishes loose-file presence, supplied index listings and unknown coverage. No archive extraction or loader emulation. |
| Compare stored INI/LTX settings | [INI/LTX Configuration Value Diff](../tools/ini-ltx-value-diff/README.md) | Python 3.12+; explicit file pairs, literal values hidden by default. No interpolation, include resolution or inherited-value calculation. |
| Inspect version-3 PAK indexes and virtual overlaps | [Unreal PAK Index & Conflict Inspector](../tools/unreal-pak-inspector/README.md) | Python 3.12+; standard unencrypted v3 metadata only. No payload validation, extraction, decryption or load-order prediction. |
| Inspect classic ZIP package layout | [Mod Package ZIP Layout Inspector](../tools/mod-package-zip-inspector/README.md) | Python 3.12+; bounded supported ZIP32 metadata. No extraction, decompression or payload-integrity claim. |
| Explain saved modlist changes | [MO2 Profile Change Report](../tools/mo2-profile-change-report/README.md) | Python 3.12+; additions, removals, states and relative ordering in explicit saved files. No live MO2 or plugin/load-order acceptance. |
| Check authored dependency and order rules | [Offline Mod Dependency Rule Checker](../tools/offline-mod-dependency-checker/README.md) | Python 3.12+; explicit JSON catalogs, presence/conflict/order findings and bounded cycle witnesses. No inferred compatibility database. |
| Audit captured files and launch/exit receipts | [Game Session Evidence Auditor](../tools/game-session-evidence-auditor/README.md) | Python 3.12+; selected sizes, hashes and generic receipt consistency. No process observer, authenticity or gameplay attestation. |

Each module includes its own commands and scope notes. The newer standalone
tools include generators that create original toy files in a new external
folder. Select a new destination outside the checkout and any live installation;
example generators have different path guards. Try those before supplying real
data. Game files are unnecessary for the synthetic test suites. Run tests from the relevant tool directory:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

The upstream main revision passed its documented Windows/Ubuntu CI jobs with
Python 3.12/3.13. XML has Windows 3.13 and Ubuntu 3.12/3.13 jobs with an independent
Expat gate. Before publication, require hosted CI for the exact final candidate revision;
see [validation](../VALIDATION.md). Native link/case
fixtures declare skips where unavailable. macOS and engine/gameplay acceptance
remain unverified.

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
