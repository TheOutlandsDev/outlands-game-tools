# Mod Content Manifest & Diff

Create a relative-path SHA-256 inventory of selected loose files, then compare
two inventories for additional, missing or changed content. An optional saved
MO2 profile model records the winning provider for each loose virtual path,
including equal-byte files whose winning mod changed. Python **3.12+** and its
standard library are sufficient; there are no package dependencies.

This is original MIT utility code. It reads selected inputs and writes only an
optional **new** JSON report. It does not launch a game, edit mods/profiles,
copy game assets, repair files, install packages, upload reports or integrate
with an engine. A content match helps narrow a troubleshooting difference; it
does not establish that either installation is correct or that a game will run.

## Setup

Download the repository using **Code → Download ZIP**, extract it outside game
and save folders, and open PowerShell in `tools\mod-content-manifest`:

```powershell
py -3.12 --version
py -3.12 -B content_manifest.py --help
py -3.12 -B content_manifest.py scan --help
py -3.12 -B content_manifest.py diff --help
```

Use `python` if that is your Python 3.12+ interpreter. On Linux/macOS, replace
`py -3.12` with `python3`; change example backslashes to `/` and PowerShell
continuation backticks to your shell's syntax. No virtual environment,
administrator rights or execution-policy changes are required. `-B` avoids
bytecode caches beside the downloaded source.

## Try a generated example

The [example generator](examples/README.md) creates original tiny toy files,
not actual game content. Choose a new demo directory outside the repository
and your game folders. Reports below live beside the scan roots:

```powershell
$demo = Join-Path $env:TEMP ('outlands-manifest-demo-' + [guid]::NewGuid().ToString('N'))
py -3.12 -B examples\create_example.py --destination $demo
py -3.12 -B content_manifest.py scan `
  --source-dir "$demo\baseline" --output "$demo\baseline.json"
$LASTEXITCODE
py -3.12 -B content_manifest.py scan `
  --source-dir "$demo\candidate" --output "$demo\candidate.json"
$LASTEXITCODE
py -3.12 -B content_manifest.py diff `
  --baseline "$demo\baseline.json" --candidate "$demo\candidate.json" `
  --output "$demo\comparison.json"
$LASTEXITCODE
```

Both scans return **0**. The diff returns **2**, with one `added` path, one
`removed` path, one `changed` path and one identical file. `removed` means
present in the baseline but absent from the candidate. Nothing is deleted.
The changed file deliberately has different bytes; the comparison checks the
SHA-256 value as well as byte length. JSON appears on stdout unless `--output`
saves it to the chosen new file. Existing output files are refused, so use a new
filename for a repeat run.

For a MO2 example with a known override chain:

```powershell
py -3.12 -B content_manifest.py scan `
  --mods-dir "$demo\mo2\mods" --modlist "$demo\mo2\modlist.txt" `
  --base-dir "$demo\mo2\base" --overwrite-dir "$demo\mo2\overwrite" `
  --extensions .ltx --output "$demo\mo2.json"
$LASTEXITCODE
```

Expect exit **0**, three effective files and a conflict for
`gamedata/configs/shared.ltx`. Its provider is `overwrite`, above `mod:High Toy`,
`mod:Low Toy` and `base`. The disabled toy provider contributes no files.
Delete only your generated demo directory using your normal file manager when
finished; neither the tool nor the generator performs automatic cleanup.

The corresponding Linux/macOS shell example is:

```sh
demo="${TMPDIR:-/tmp}/outlands-manifest-demo-$$"
python3 -B examples/create_example.py --destination "$demo"
python3 -B content_manifest.py scan --source-dir "$demo/baseline" --output "$demo/baseline.json"
python3 -B content_manifest.py scan --source-dir "$demo/candidate" --output "$demo/candidate.json"
python3 -B content_manifest.py diff --baseline "$demo/baseline.json" --candidate "$demo/candidate.json" --output "$demo/comparison.json"
echo "$?"
```

The final status is **2** for the deliberate differences; the scans return
**0**. Run the commands interactively or account for the expected diff status
in scripts using `set -e`. Reusing the same destination is intentionally refused.

## Inventory a chosen directory

Close the game, mod manager, deployment/sync utility and other writers that
could change your selection. The tool cannot freeze the filesystem or confirm
those programs are closed. Supply a narrow local root containing only what
you intend to compare:

```powershell
py -3.12 -B content_manifest.py scan `
  --source-dir 'D:\Games\Example\gamedata' `
  --extensions .ltx --extensions .script `
  --output 'D:\Reports\example-content-before.json'
$LASTEXITCODE
```

Paths in this report are relative to `gamedata`, such as
`configs/example.ltx`. Repeat `--extensions` with one dot-prefixed suffix per
argument. Matching is case-insensitive; the stored extension policy is sorted
and lowercase. Without `--extensions`, every ordinary file not covered by the
fixed exclusions is eligible, including binary assets. Only file lengths and
streamed hashes enter the inventory; file contents are not embedded.

Each scan root must be an existing ordinary local directory. Links, junctions,
reparse points, special files, unsafe/ambiguous portable path names and
case-colliding paths prevent a complete scan. Network/device paths are rejected.
An optional report must be new with an existing ordinary local parent, outside
every selected input root and separate from the modlist. There is no merge,
overwrite, recursive output directory creation or automatic deletion.

## Inventory a saved MO2 profile model

Choose the actual `mods` directory and saved native `modlist.txt` for the
profile you intend to examine. Optional loose base and Overwrite roots use the
**same virtual root** as each mod:

```powershell
py -3.12 -B content_manifest.py scan `
  --mods-dir 'D:\Modding\Example\mods' `
  --modlist 'D:\Modding\Example\profiles\Testing\modlist.txt' `
  --base-dir 'D:\Games\Example' `
  --overwrite-dir 'D:\Modding\Example\overwrite' `
  --extensions .ltx --extensions .script `
  --output 'D:\Reports\example-profile-before.json'
$LASTEXITCODE
```

If mods contain `gamedata/configs/...`, the example base root contains
`gamedata/configs/...` too. Selecting `D:\Games\Example\gamedata` as base would
introduce a different relative layout. Roots must not overlap. Base and
Overwrite are optional; omitting either also omits those files from the model.

Native saved MO2 lists are read **highest enabled priority first**. Blank lines
and `#` comments are ignored, `+Name` enables a named mod, and `-Name` disables
it. UTF-8 with an optional BOM is supported. Names ending `_separator` represent
MO2 separator rows and are skipped. Missing enabled mods, duplicate or
unsafe names, and foreign `*` plugin-list syntax are rejected. A missing disabled
mod does not make the selection incomplete.

Priority is Overwrite, enabled mods in saved order, then loose base. Provider
IDs are `overwrite`, `mod:Name` and `base`. Only the effective winning file is
hashed. `file_conflicts` records providers for overlapping relative paths; it
does **not** compare the masked copies. MO2 provider-root `meta.ini` and files
or directories ending `.mohidden` are excluded. The ordinary directory mode preserves these
names unless another fixed exclusion/filter applies.

This models saved loose-file priorities. It does not inspect a running virtual
filesystem, archives, plugins, deployments, game-specific loaders, MO2 plugins,
INI redirection or live unsaved profile changes. A report is not proof that a
game loaded the reported winner. Base archives remain ordinary opaque files if
included; their members are not enumerated.

## Compare two manifests

Generate each manifest independently using the same root layout and selection
policy, then compare:

```powershell
py -3.12 -B content_manifest.py diff `
  --baseline 'D:\Reports\example-profile-before.json' `
  --candidate 'D:\Reports\example-profile-after.json' `
  --output 'D:\Reports\example-profile-diff.json'
$LASTEXITCODE
```

The diff reads only the two JSON files. It does not revisit either installation,
so it cannot tell whether files changed after their scan. Both inputs must be
complete supported manifests. The parser rejects malformed JSON, duplicate
keys, unsafe/duplicate paths, invalid hashes/types, inconsistent summaries and
provider/conflict references. An unfamiliar schema or exclusion policy is
rejected. Directory and MO2 modes, extension filters and fixed exclusion lists
must agree; scan limits can differ when both scans completed.

`added` and `removed` describe candidate membership relative to the baseline.
`changed` means size or SHA-256 differs at a shared path. `provider_changes`
means bytes match but the selected provider differs. A byte-changed path with
a new provider appears in `changed`, with both providers included there.
Provider changes return exit **2** even when all effective bytes match. Changing
only a masked provider does not create a finding unless the effective content
or winning provider changes.

Path matching is case-insensitive for this portable Windows-oriented model.
Changing only a path's letter case between two individually valid manifests
does not create a difference. Case-colliding entries within one scan or imported
manifest are rejected. `identical_files` counts matching bytes, including paths
listed separately under `provider_changes`.

## Limits and exit codes

Scan limits accept positive integers below Python's `sys.maxsize`:

| Option | Default | What it bounds |
|---|---|---|
| `--max-file-bytes` | `1073741824` (1 GiB) | A selected effective file's length/read. |
| `--max-total-bytes` | `8589934592` (8 GiB) | Combined effective bytes hashed. |
| `--max-files` | `100000` | Eligible file copies encountered across providers, including masked copies. |
| `--max-entries` | `200000` | Directory entries traversed, including filtered entries. |

Manifest import and output are capped at 32 MiB; saved modlists are capped at
2 MiB. A scan without eligible candidates is incomplete. Up to 1000 extension
arguments are accepted. Relative paths are limited to 128 components; retained
entry-name metadata is separately bounded. Excessively nested/complex inputs
may fail rather than producing a full report. Hashing reads bounded chunks
rather than loading whole assets. Reads and file
identity/stat checks reduce accidental acceptance of changing inputs, but do
not provide a filesystem snapshot or a hostile-input sandbox. A limit, unreadable
input, missing enabled provider, unsafe entry or observed input change makes
the result incomplete. Do not treat a partial inventory as a complete match.

| Exit | Meaning |
|---|---|
| `0` | A complete scan, or a complete diff without content/provider differences. |
| `2` | A complete diff with at least one addition, removal, byte change or provider change. |
| `1` | Invalid/incomplete input, a limit/read/stability failure, or output failure. |

An invalid command line can exit before JSON is available. Check both the process
exit and JSON `complete`. A scan's conflicts alone are not an error and do not
return **2**. The [report reference](REPORT-FORMAT.md) describes all fields.

## Privacy and trust

Reports omit absolute roots, usernames from those roots, timestamps, copied
content and raw exception messages. Fixed exclusions cover common repository,
runtime, save, log, credential and key names; the complete policy is documented
in the [report reference](REPORT-FORMAT.md). These are name-based filters, not
secret detection. A private file with another name can still be hashed, and an
explicit root named `saves` is not a reason to select private saves accidentally.

**Review relative paths, mod/provider names, byte counts and hashes before
sharing a report.** They can identify private or copyrighted material. A hash
can reveal a guessable short file by matching candidate values. A manifest is
editable JSON, not a signature: matching hashes do not prove authorship,
ownership, authenticity, safe licensing, mod compatibility or game readiness.
Do not upload game files to demonstrate a report.

## Tests and suggestions

From this directory, run the black-box tests with generated toy data:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Tests check hashing, differences, provider priority, selection compatibility,
strict manifest imports, output guards and input preservation. Link/junction
fixtures explicitly skip where the platform cannot create them. The suite does
not launch games, read your installed mod packs or prove runtime compatibility.

Open a [bug report](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml)
or [suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml).
Include OS, Python/tool version, the exact command with private roots replaced,
exit status and a small original reproducer. Review JSON metadata before
attaching it. Helpful suggestions include clearer reports, portable edge cases
and additional generated fixtures. Contributions follow the collection's
[contributing guide](../../CONTRIBUTING.md). Code, tests, documentation and toy
examples are covered by the repository's [MIT license](../../LICENSE).
