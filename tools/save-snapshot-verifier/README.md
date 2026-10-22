# Save Snapshot Verifier

Create a **new** local backup of explicitly selected save/configuration files,
verify every copied file with SHA-256, and later check the snapshot for missing,
changed or unexpected files. Python 3.12+ and the standard library are sufficient.
No game, mod manager, administrator rights or package installation is required.

This original utility grew out of local pre-mod-testing backups. It does not
discover games, restore files, overwrite a backup, prune old copies, validate
save formats, upload data or run in the background. It never modifies selected
source files. Snapshot creation writes only into your new destination and an
optional new report; verification reads the snapshot and can create a report.

## Setup

Download the repository using **Code → Download ZIP**, extract it outside your
game/save folders, and open PowerShell in `tools\save-snapshot-verifier`:

```powershell
py -3.12 --version
py -3.12 -B save_snapshot.py --help
py -3.12 -B save_snapshot.py snapshot --help
py -3.12 -B save_snapshot.py verify --help
```

Use `python` instead if it is your Python 3.12+ interpreter. Linux/macOS users
can replace `py -3.12` with `python3`. No virtual environment, dependencies or
execution-policy change is needed. `-B` avoids bytecode caches beside source.

## Try the original example

Close the game and anything that might write selected inputs before creating a
real snapshot. For the following example, only original generated toy files are
used. Choose a new demo folder and snapshot filename for each run:

```powershell
$demo = Join-Path $env:TEMP ('outlands-save-demo-' + [guid]::NewGuid().ToString('N'))
py -3.12 -B examples\create_example.py --destination $demo
py -3.12 -B save_snapshot.py snapshot `
  --source "saves=$demo\saves" `
  --source "profile=$demo\profile.ini" `
  --destination "$demo\snapshot-001" `
  --confirm-closed
$LASTEXITCODE
py -3.12 -B save_snapshot.py verify --snapshot "$demo\snapshot-001"
$LASTEXITCODE
```

Expect exit **0** for both operations and three matched files on verification.
The snapshot contains `manifest.json` plus `data\saves\slot1.dat`,
`data\saves\slot2.dat` and `data\profile\profile.ini`.

To demonstrate detection, change **only a copied toy file**, then verify again:

```powershell
Set-Content -LiteralPath "$demo\snapshot-001\data\saves\slot1.dat" -Value 'Changed original toy copy'
py -3.12 -B save_snapshot.py verify --snapshot "$demo\snapshot-001"
$LASTEXITCODE
```

Expect exit **2** and `changed_file` for that relative path. The original toy
save under `$demo\saves` is unchanged. Delete only your generated demo folder
with your normal file manager when finished. No automatic cleanup is performed.

## Back up selected saves and configuration

Supply each file or recursive folder explicitly as `--source LABEL=PATH`.
Labels are short portable names used inside the snapshot, rather than absolute
source paths. Use letters, numbers, `_` or `-`; labels must be unique without
regard to case. Up to 64 sources are accepted. Choose only the folders/files you
intend to preserve; a selected directory includes **all ordinary files** below
it, including hidden files. There is no extension filter or automatic log capture.

```powershell
py -3.12 -B save_snapshot.py snapshot `
  --source 'saves=D:\Games\Example\Saves' `
  --source 'profile=D:\Games\Example\profile.ini' `
  --destination 'D:\Backups\Example-before-mods-001' `
  --confirm-closed `
  --output 'D:\Reports\snapshot-001.json'
$LASTEXITCODE
```

Replace example paths with your own. The destination and optional report must
be new, with existing local parents. The destination cannot overlap any input;
source roots cannot overlap each other. The report must be outside all inputs
and the snapshot. Existing folders/files are never merged or replaced.

`--confirm-closed` is your attestation that the game, cloud-save sync, editor and
other writers are closed or paused as appropriate. The tool does not stop or
detect those programs. Check whether your game needs additional save/profile
files before relying on a selection. A verified copy of an incomplete selection
does not make it a complete game backup.

Files are copied into `data\LABEL\relative-path`. A single-file source uses
`data\LABEL\original-filename`. Empty files are preserved; empty directories,
permissions, ACLs, original timestamps, alternate streams and special files are
not backed up as independent metadata. No compression or encryption is applied.

## Verify a snapshot

```powershell
py -3.12 -B save_snapshot.py verify `
  --snapshot 'D:\Backups\Example-before-mods-001' `
  --output 'D:\Reports\verify-001.json'
$LASTEXITCODE
```

Verification compares the ordinary files under `data` with `manifest.json`.
Changed contents/lengths, missing files and unexpected files are findings.
Unexpected root entries, incomplete markers, unsafe paths, unreadable data,
malformed manifests and limits prevent a complete verification.

The manifest is editable and is **not a signature**. Someone able to change both
the manifest and copied data can make a different snapshot verify. Hashes do not
prove authorship, authenticity, save-format validity or that a game will load.
Store valuable backups separately and protect them using your normal storage
practices. The tool has no automatic restoration or repair command.

## Limits, failures and exit codes

Both modes accept these positive integers below Python's `sys.maxsize`:

| Option | Default | Scope |
|---|---|---|
| `--max-file-bytes` | `1073741824` (1 GiB) | Maximum ordinary file length/read. |
| `--max-total-bytes` | `8589934592` (8 GiB) | Selected data bytes; verification also checks observed data size. |
| `--max-entries` | `100000` | Traversed entries per tree and combined selected file count; directory entries count too. |

Manifest reading is separately capped at 16 MiB. Large manifests or extremely
deep trees can fail within operating-system limits. File contents are processed
in chunks of at most 1 MiB; the tool does not load save data into JSON reports.

| Exit | Meaning |
|---|---|
| `0` | Snapshot created with copies verified, or complete verification with no differences. |
| `2` | Complete verification found changed, missing or unexpected files. |
| `1` | Invalid/incomplete operation, unsafe path, limit, changed input, copy failure or report failure. |

A snapshot starts with an `INCOMPLETE.json` marker. Only after all copies,
hash checks and source stability checks pass is the manifest written and the
marker removed. Failure can leave a **new partial folder**, which verification
refuses. The tool leaves it for inspection rather than deleting data during
cleanup. Choose a new destination for retry; remove only your own partial folder
with your normal file manager after reviewing it. If report creation fails after
a snapshot completed, the command returns 1; verify the snapshot separately.

Preflight/operation errors are printed as JSON on stdout, even if `--output`
was requested. A report file is created only after the operation returns
successfully from its guarded workflow. Read the exit code as well as the JSON.
Prefer `--output` for saved reports: shell redirection can overwrite a file
before this tool runs, bypassing its destination protections.

## Read-only and privacy boundaries

Links, junctions/reparse points, network/device paths, Windows stream syntax,
ambiguous case names and non-regular files are refused. Case handling is a
conservative Unicode casefold approximation, not exact Windows collation.
File identity/size/modification time and directory membership are checked
again, but this is **not an atomic filesystem snapshot** and cannot detect every
race. Keep sources and destination stable; do not use it in a hostile shared
directory or as an untrusted-input sandbox.

Reports and manifests omit absolute source roots and file contents, but relative
names, labels, sizes, hashes and timing can still disclose information. Snapshot
data contains the actual selected files and may contain private player data or
third-party content. Do not upload a real snapshot, save, config or raw log to a
public issue. Share a small generated reproduction you own instead.

See [REPORT-FORMAT.md](REPORT-FORMAT.md) for exact field meanings.

## Tests, suggestions and license

From the tool directory:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Tests create disposable original files, including multi-chunk data and injected
copy failures. Native link/case fixtures may be skipped when the account or
filesystem cannot create them; skips remain visible. Passing tests do not prove
game save compatibility, crash-safe persistence or full protection against races.

[Suggest an improvement or report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new/choose).
Name **Save Snapshot Verifier**, include Python/OS/tool versions, a sanitized
command, exit code and expected/actual result. Ideas and documentation feedback
are welcome without code. Never attach a real backup or private data. See
[CONTRIBUTING.md](../../CONTRIBUTING.md).

The original code, tests, generator and documentation use the root [MIT
license](../../LICENSE). No game files or third-party implementation are bundled.
The license does not grant redistribution rights to files you select for backup.
To uninstall, remove the extracted tool folder; it installs no service or game
component. Keep your backups/reports unless you intentionally remove them.
