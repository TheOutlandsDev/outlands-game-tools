# JSON report reference

This reference describes schema version **1**. A report is evidence about the
bytes and selected parser observed during a scan, not a game compatibility
certificate. See the [README](README.md) for setup, priority, and limitations.

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | Integer format version, currently `1`. Consumers should reject or explicitly handle an unfamiliar version. |
| `tool` | Checker name and version. |
| `mode` | `tree` for `--source-dir`, or `mo2` for the saved-profile overlay model. |
| `runtime` | Selected and observed Lua runtime metadata. |
| `summary` | Completion and candidate/check totals described below. |
| `providers_priority_highest_first` | Input providers in the order used to select an effective loose file. |
| `scripts` | Records for effective script paths, with compilation or skip results. Masked copies are counted but not compiled. |
| `warnings` | Structured warnings; review these even when compilation succeeds. |
| `errors` | Structured problems affecting the scan. A report may contain useful partial results while incomplete. |
| `modlist` | Saved modlist hash and stability result in MO2 mode; `null` in source-tree mode. |
| `limitations` | Scope statements recorded with the report. |

Reports deliberately contain no absolute root paths, raw Lua error messages,
or source excerpts. **They can still contain sensitive information:** mod
names, relative paths, hashes, byte sizes, and counts. Review before sharing.

## Runtime metadata

| Field | Meaning |
|---|---|
| `requested` | CLI selector: `luajit21`, `lua51`, or `lua54`. |
| `module` | Lupa module used for that selection. |
| `lupa_version` | Installed Lupa version. The supported dependency is pinned to 2.8. |
| `lua_version` | Observed VM language/version value. |
| `implementation` | Observed implementation identifier. |
| `operation` | Describes compilation without invoking scanned chunks. |

Do not compare results from different VMs as though they were the same check.
LuaJIT's Lua 5.1 family, Lua 5.1, and Lua 5.4 have different accepted syntax.
VM details are not evidence of a game's engine fork or preprocessing behavior.

## Summary

| Field | Meaning |
|---|---|
| `complete` | `true` only when the scan completed under the tool's input and read checks. A skipped/problem input makes the scan incomplete. |
| `enabled_mods` | Enabled mod providers selected from the modlist; not base/Overwrite. Source-tree mode has no enabled MO2 mods. |
| `scanned_providers` | Provider directories traversed. |
| `loose_scripts` | Candidate `.lua`/`.script` copies observed before overlay winners are selected. |
| `effective_scripts` | Selected relative script paths after overlay priority. |
| `checked_scripts` | Final checked records: `passes + syntax_errors`. A script that changes after compilation becomes skipped instead. |
| `passes` | Checked scripts accepted by the selected parser. |
| `syntax_errors` | Checked scripts rejected by the selected parser. |
| `skipped_scripts` | Effective candidates not successfully checked, for example because of size or input/read restrictions. |
| `shadowed_scripts` | Lower-priority candidate copies masked by selected effective paths. These copies are not parsed. |

A complete scan with zero syntax errors returns `0`. A complete scan with one
or more syntax errors returns `2`. An invalid/incomplete scan or output failure
returns `1`, even if some files passed or syntax errors were found. Inspect
both the process exit code and `summary.complete`; a process can also fail
before a report is available.

## Providers and priority

Each provider has `name`, `kind`, and `priority`. The containing array is
ordered highest priority first. Source-tree mode has one provider named
`<source>` with kind `source`. In MO2 mode, the supplied `<overwrite>` provider
has kind `overwrite`, enabled mod names have kind `mod`, and the optional
`<base>` provider has kind `base`.

Native saved modlist order is first enabled entry highest. Matching uses a
case-insensitive relative-path model; ambiguous cases are rejected rather than
silently choosing an arbitrary file. This is a loose-file model, not MO2's
live VFS, an archive extractor, or a game-engine loader.

## Script records

| Field | Meaning |
|---|---|
| `path` | Relative path under the matching virtual data root; no absolute input root. |
| `provider` | Name of the selected provider. |
| `kind` | Provider kind: `source`, `mod`, `overwrite`, or `base`. |
| `status` | `PASS`, `SYNTAX_ERROR`, or `SKIPPED`. |
| `bytes` | Original source-file byte length when available. |
| `sha256` | SHA-256 of original read bytes when available. It includes a leading BOM if present. |
| `utf8_bom` | Whether one leading UTF-8 BOM was removed from the parser input. |
| `parser_input_sha256` | SHA-256 of the prepared parser bytes after optional BOM removal, when available. It can be computed even when format checks subsequently refuse the input. |
| `line` | Optional numeric source line from the fixed-label parser diagnostic. It can be absent; no source token or raw message is retained. |
| `code` | Optional error/skip category, rather than a raw native exception. |

Fields whose values are unavailable for a skipped input may be absent or null.
Consumers should allow omitted optional fields and new diagnostic categories.
Never assume every `SYNTAX_ERROR` record contains a line number.

The checker parses bytes without rewriting or decoding source into another
encoding. `.lua` and `.script` suffix matching is case insensitive. It refuses
bytecode and NUL-containing files; it does not load precompiled chunks. A size
limit applies to the original source bytes. BOM normalization affects only the
bytes passed to the parser, not files on disk.

## Warnings, errors, and stability

Diagnostic records have a `code` and may identify a relative `path`, a
`provider`, or a numeric modlist/source `line`. Codes describe categories such
as invalid modlist entries, missing or unsafe providers, links/reparse points,
ambiguous names, oversized inputs, rejected source formats, read failures, or
input changes. They are not repair instructions. Use the identified local file
and the [troubleshooting guide](README.md#troubleshooting-and-removal) to
investigate.

In MO2 mode, `modlist.sha256` identifies the initially read modlist bytes and
`modlist.unchanged` records the stability check. Effective source bytes are also
reread to detect changes. Passing rereads do not create an atomic snapshot or
protect against every filesystem race; keep the inputs stable during a scan.

Linked/reparse inputs and linked output ancestors are outside the supported
local-file model. An output file is created exclusively only after its
destination is validated. It must be new, have an existing parent, and remain
outside all source/MO2 inputs. No output option means stdout. Do not use shell
redirection to overwrite an existing file or anything under scanned inputs.

## Reading a report in PowerShell

```powershell
$report = Get-Content -LiteralPath 'D:\Reports\lua-check-001.json' -Raw | ConvertFrom-Json
$report.runtime
$report.summary
$report.scripts | Where-Object status -ne 'PASS' | Select-Object path, provider, status, code, line
$report.errors
$report.warnings
```

Open the reported local script separately to inspect the error. Reports omit
source excerpts by design, but hashes and relative names can identify private
files. Share the generated original fixture or a small reproduction you have
permission to publish rather than copying game/mod source into an issue.

To produce a reproducible report without any game files, follow the
[example walkthrough](examples/README.md). A fresh report is generated locally
so its runtime metadata and hashes describe the installation you actually ran.
