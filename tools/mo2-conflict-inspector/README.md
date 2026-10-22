# MO2 Conflict Inspector

A portable, read-only report for a Mod Organizer 2 profile. Find which enabled
mod provides an overlapping loose file, which provider wins, and a few text
patterns that deserve a closer look. This tool grew out of local S.T.A.L.K.E.R.
mod troubleshooting; file-overlap reports also work with other MO2-managed games.
The Lua, LTX, and unlocalizer checks are aimed at X-Ray-style mod setups.

Python **3.12 or newer**, standard library only. No pip packages, game files,
MO2 plugin installation, administrator rights, or network connection are needed
to run it. The original tool, tests, examples, and documentation are covered by
the collection's [MIT license](../../LICENSE). This is an independent utility,
not an official Mod Organizer 2 or game project.

**A finding is a review prompt, not proof of incompatibility.** Patches commonly
override files on purpose. The report does not fix files, merge mods, change
priority, or promise that a game will launch. Read the
[limits](#what-the-report-cannot-tell-you) before using a winner to make changes.

## Get the tool

Download the repository using GitHub's **Code → Download ZIP**, extract it, and
open PowerShell in `tools\mo2-conflict-inspector`. Keep the extracted tool
outside your MO2 mods and overwrite folders. You can also clone the repository
if you already use Git.

Check your Python installation and the command help:

```powershell
py -3.12 --version
py -3.12 -B mo2_conflicts.py --help
py -3.12 -B mo2_conflicts.py --version
```

If your installation uses `python` instead of the Windows `py` launcher, use
`python --version`, then replace `py -3.12` with `python` in the examples. Confirm
that interpreter is 3.12 or newer. On Linux or macOS, `python3` may be the command.
The `-B` switch prevents Python from creating bytecode cache files beside source.

## Find the right MO2 paths

Select the instance and profile you want to inspect in MO2. In its settings,
look at **Paths** and record **Mods**, **Profiles**, and **Overwrite**. The
modlist input is `modlist.txt` inside the selected profile's folder under the
Profiles path. Use the **Mods** path itself, which contains one directory per
installed mod; do not point at an individual mod or at the game's data folder.

MO2 lets these paths live in different locations. A portable installation may
keep them beside MO2, while an instance can use folders elsewhere. Read the
configured paths rather than assuming they are under the game. See MO2's
[official Paths documentation](https://github.com/ModOrganizer2/modorganizer/wiki/Settings-window#paths).

Close MO2 after its profile is saved for a stable scan. If you leave it open,
do not install, update, rename, enable, disable, or reorder mods during the run.
Also stop tools that are generating files into Overwrite. This inspector reads
the saved files on disk; it cannot take an atomic snapshot of a changing setup.

## Inspect your profile

Replace the sample paths with your own. In this example, `D:\MO2-Reports`
already exists and `profile-report.json` does **not** exist:

```powershell
py -3.12 -B mo2_conflicts.py `
  --mods-dir 'D:\MO2\mods' `
  --modlist 'D:\MO2\profiles\My Profile\modlist.txt' `
  --overwrite-dir 'D:\MO2\overwrite' `
  --output 'D:\MO2-Reports\profile-report.json'
$LASTEXITCODE
```

`--mods-dir` and `--modlist` are required. Include `--overwrite-dir` for the
instance's real Overwrite folder; omitting it excludes those files from the
report and can change a reported winner. Empty Overwrite folders are fine.

The inspector only reads the selected modlist and mod folders. It creates a
report file only when you supply `--output`, which must name a **new file** outside the
mods and Overwrite folders, with an existing parent directory. It also refuses
the input modlist as a destination. Use a separate reports folder away from
the whole profile. Existing files are refused,
so use a fresh report name for each run. Linked folders/files, junctions, and
reparse points are refused or reported as incomplete rather than followed.
This is deliberate: the tool must not silently scan another location or write
through a linked output path.

Without `--output`, JSON goes to the terminal (standard output). Prefer
`--output` when saving a report: shell redirection such as `> report.json` can
truncate an existing file **before** the inspector checks its inputs. Do not
redirect output to a modlist, mod file, or anything under your inputs.

To view JSON in the terminal instead of creating a report:

```powershell
python -B mo2_conflicts.py --mods-dir 'D:\MO2\mods' --modlist 'D:\MO2\profiles\My Profile\modlist.txt'
```

On a system where Python is called `python3`, the equivalent looks like this
(use real local paths):

```bash
python3 -B mo2_conflicts.py --mods-dir '/home/player/MO2/mods' --modlist '/home/player/MO2/profiles/Example/modlist.txt'
```

Open a saved report in a text editor, or read its summary in PowerShell:

```powershell
$report = Get-Content -LiteralPath 'D:\MO2-Reports\profile-report.json' -Raw | ConvertFrom-Json
$report.summary
$report.file_conflicts | Select-Object path, winner
$report.errors
$report.warnings
```

## Commands and exit codes

| Option | Meaning |
|---|---|
| `--mods-dir PATH` | Required folder containing the installed mod directories. |
| `--modlist PATH` | Required saved MO2 profile `modlist.txt`. Native MO2 order is expected. |
| `--overwrite-dir PATH` | Include this instance's Overwrite folder as the highest-priority provider. |
| `--output PATH` | Create a new JSON file. Parent must exist; no replacement of existing files. Without this option, emit JSON to stdout. |
| `--max-text-bytes N` | Maximum size of each script/configuration file parsed for text checks. Default: `2097152` bytes (2 MiB). Must be positive. A skipped text file makes the scan incomplete. |
| `--fail-on-conflicts` | Return exit code 2 for a complete report with findings. Useful for scripts and CI. It does not change the findings or modify files. |
| `--version` | Print the tool version. |
| `--help` | Show usage and available options. |

| Exit code | Meaning |
|---|---|
| `0` | Scan complete. Findings may still exist unless `--fail-on-conflicts` was used. |
| `1` | Invalid input, an incomplete scan, or a report-write error. Check `summary.complete`, `errors`, `warnings`, and terminal messages. |
| `2` | Scan complete and findings exist, with `--fail-on-conflicts`. |

Check `$LASTEXITCODE` immediately after the Python command in PowerShell. A
completed scan with zero findings means only that these checks found nothing
in the supplied inputs. It is not a gameplay test.

## What it checks

### Loose-file providers and winners

For each relative loose-file path, the inspector collects enabled providers,
using case-insensitive matching. `file_conflicts` lists paths supplied by more
than one provider, their order, and the winning provider. It compares names and
priority; it does **not** compare file bytes or decide whether duplicates are
identical or safe to remove. A winner means the selected provider wins among
the scanned loose files under this model. Matching uses Python's Unicode
casefold approximation, which is not identical to NTFS/Win32 collation. Confirm
unusual Unicode filename cases in MO2.

The saved native `modlist.txt` lists higher-priority entries first. The
inspector uses that order directly. This differs from the common ascending
Priority display in MO2's left pane. Do not reverse or alphabetically sort the
file. See MO2's [profile file writer](https://github.com/ModOrganizer2/modorganizer/blob/master/src/profile.cpp)
for the native file ordering. Overwrite, when supplied, ranks above enabled
mods, matching MO2's [documented Overwrite behavior](https://github.com/ModOrganizer2/modorganizer/wiki/Troubleshooting#there-are-files-in-your-overwrite-mod-directory).

Disabled `-` entries are not scanned. Separator rows are ignored. The root
`meta.ini` in a mod is MO2 metadata and is excluded. Entries with a path
component ending in `.mohidden` are excluded as hidden content. Foreign `*`
entries and unsupported modlist syntax make the report incomplete; the tool
does not guess where unmanaged content lives. Enabled names must be safe,
single Windows folder components. Malformed or case-ambiguous names make the
scan incomplete. Network/UNC/device paths are outside this local-file tool's
scope. Mods and Overwrite must be separate, non-overlapping input directories.

### Text checks on effective files

These checks use only winning loose files, so a completely masked older copy
does not create a duplicate text warning:

- **Repeated qualified Lua function declarations:** the same qualified symbol,
  such as `ui.refresh_menu`, declared in two or more effective `.script` or
  `.lua` files. Comments and strings are stripped heuristically. This does not
  resolve aliases, scopes, dynamic assignments, callbacks, or execution order.
- **Duplicate LTX keys within a file:** repeated keys in the same section of
  one effective `.ltx` file. The report records section, key, and line numbers;
  it does not evaluate includes, inheritance, DLTX, or a final merged config.
- **Repeated unlocalizer symbols:** simple bare declarations under a section,
  such as `[ui]` followed by `refresh_menu`, in effective `.ltx` files in
  an `unlocalizers` directory, within or across files. These are reported as
  `ui.refresh_menu`.

Text must be readable UTF-8 (a UTF-8 BOM is accepted). Unreadable, undecodable,
NUL-containing, or over-limit candidate text files are skipped and mark the
report incomplete. Unsupported LTX section/key labels, including path-like or
overlong labels, also make text coverage incomplete; the tool will not copy
those labels into the report. Other file types are inventoried by path without
parsing their contents.

Read [REPORT-FORMAT.md](REPORT-FORMAT.md) for the JSON structure and how to
interpret counts and declaration references.

## Try a small example without a game

The [example generator](examples/create_example.py) creates an original toy
profile in a **new** directory. It contains no game assets, downloaded mods, or
third-party code. It refuses an existing destination and never edits your
installed profile. Keep the generated fixture outside your real MO2 setup.

Run from this tool's directory. Use a new destination name if you have already
run the example:

```powershell
$demo = Join-Path $env:TEMP 'outlands-mo2-example-01'
$demoReport = Join-Path $env:TEMP 'outlands-mo2-example-01-report.json'
py -3.12 -B examples/create_example.py $demo
py -3.12 -B mo2_conflicts.py `
  --mods-dir (Join-Path $demo 'mods') `
  --modlist (Join-Path $demo 'profiles\Example\modlist.txt') `
  --overwrite-dir (Join-Path $demo 'overwrite') `
  --output $demoReport `
  --fail-on-conflicts
$LASTEXITCODE
$example = Get-Content -LiteralPath $demoReport -Raw | ConvertFrom-Json
$example.summary
```

Expected exit code: **2**, because this complete toy scan intentionally has
findings. `summary.complete` should be `true`, with 2 enabled mods, 3 scanned
providers, 8 loose files, 6 effective files, and 5 findings:

| Finding | Expected result |
|---|---|
| File overlap | `gamedata/configs/toy.ltx`: `Hotfix` wins over `Base`. |
| File overlap | `gamedata/textures/toy.asset`: `<overwrite>` wins over `Base`. |
| Lua repeat | `ui.refresh_menu`, in two effective script files. |
| LTX duplicate | `speed` repeated in `[toy]` in Hotfix's config. |
| Unlocalizer duplicate | `ui.refresh_menu`, in two effective unlocalizer files. |

The disabled toy mod should not contribute files. Change only this disposable
fixture to explore priority or additional findings. See
[the worked example](examples/README.md) for its file tree and expected report
fragments.

## What the report cannot tell you

- It does not read archive contents (`.bsa`, `.ba2`, game databases, ZIPs, or
  other packed assets). It can see an archive filename as a loose file, but
  does not know which files that archive contains or how the engine loads it.
- It does not recreate MO2's full virtual filesystem, game-specific plugins,
  root deployment, unmanaged/base-game data, executable arguments, or runtime
  redirections. It does not inspect an active game process.
- It does not sort or validate ESP/ESM/ESL plugin load order, parse records, run
  LOOT/xEdit, check Lua syntax, or execute a script or game.
- Its LTX parser does not apply DLTX operations, resolve `#include`, evaluate
  inheritance, or decide which declaration the engine ultimately uses.
- Its text recognition is heuristic. Conditional declarations, unusual
  syntax, or dynamic behavior can create missed findings or false positives.
- A scan may be incomplete because of missing mods, invalid rows, access
  failures, linked content, case collisions, decoding, or size limits.
  Review incomplete coverage before drawing conclusions from winners.
- Files may change during a scan. A completed report is a local observation,
  not a transactionally consistent copy or a compatibility certification.

Use MO2's own conflicts/data views and the mod author's instructions to review
the result. If you decide to alter a real setup, back up the relevant profile,
files, and saves first and test the change separately. This tool never makes
those changes for you.

## Troubleshooting

| Problem | What to check |
|---|---|
| `py` or `python` is not found | Install/use Python 3.12+ and reopen the terminal. Check the interpreter's version before retrying. No package installation is required. |
| Script file cannot be opened | Run from the extracted `tools/mo2-conflict-inspector` folder, or use the full path to `mo2_conflicts.py`. |
| Missing enabled mod / unexpected winners | Confirm both paths belong to the same MO2 instance and selected profile. Use its saved `modlist.txt`, keep native order, and include its Overwrite folder. |
| Foreign `*` or unsupported row | The profile includes content the inspector cannot locate reliably. Review that content in MO2; do not rewrite the live modlist to suppress the warning. |
| Invalid/overlapping input folders | Use the instance's real Mods and separate Overwrite folders. Network paths, linked paths, and overlapping roots are not supported. |
| Output already exists | Choose a new filename. Existing reports are deliberately preserved. |
| Output path is refused | Use a new regular file outside `mods` and `overwrite`, with an existing non-linked parent. Do not target the input modlist; a separate reports directory is recommended. |
| Permission/link/case error | Read the error code and relative reference. The tool will not elevate permissions or follow junctions; inspect those files independently or use a regular copied test fixture. |
| Text decoding warning | The text checks expect UTF-8. Do not change the live mod's encoding just for the scanner; share a tiny original reproduction instead. |
| `binary_text` or `unsupported_ltx_name` | NUL-containing text or an unsupported section/key label prevented complete text coverage. Inspect that file locally; report a minimal original example rather than publishing private labels or paths. |
| Text size warning | Use a larger positive `--max-text-bytes` if appropriate for that file. The larger setting increases parsing memory/time; archives and binary files still are not parsed as text. |
| Many overlaps but the game works | Overrides are normal. Start with the affected path and expected winner, then check the mod's instructions. Counts are not a severity score. |
| No overlaps but the game fails | The failure may involve archives, plugins, syntax, engine behavior, or other checks outside this tool. Zero findings does not establish compatibility. |
| A run returns 1 | Check errors and `summary.complete` before using the report. A write failure may leave a partial new output file; inspect it and use a fresh filename on retry. |

## Tests and reproducibility

From this directory:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Tests use original synthetic inputs and temporary directories. See the
collection's [validation record](../../VALIDATION.md) for the checks actually
run for a release. Tests of priority, parsing, CLI behavior, and read-only
handling are separate from gameplay testing. The report's `tool.version` and
`schema_version` identify the behavior and format used for a saved result.

## Suggestions, questions, bugs, and contributions

[Open a suggestion or bug report](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new/choose).
Ideas from users are welcome, including easier report views, additional
game formats, clearer output, and examples of a workflow the tool should help.
You do not need to write code to contribute.

For a useful report, include the tool/Python/OS versions, the behavior you
expected, what happened, the exit code, and a minimal original example that
reproduces it. Explain how you confirmed the expected winner in MO2. Read the
[contribution guide](../../CONTRIBUTING.md) before submitting a patch.

**Review reports before posting.** Absolute input paths and source values are
omitted from JSON, but mod names, relative filenames, Lua symbols, LTX section
and key names, and unlocalizer symbols remain. Those can identify private
projects or disclose information. Terminal/shell errors may show local paths.
There is no automatic upload or telemetry. Share a redacted excerpt or a toy
fixture instead of an entire profile, raw source, saves, or proprietary files.

Mod Organizer 2 and game/mod names belong to their respective owners. The MIT
license here covers this utility's original source and examples; it grants no
rights to redistribute someone else's mods or game assets.
