# Source Release Builder

Build a new **source-only ZIP** from an explicitly reviewed SHA-256 inventory,
then read back every ZIP member and produce a SHA-256 checksum file. Python
3.12+ and its standard library are sufficient. No installation, game, mod
manager, network connection or administrator rights are required.

This original MIT utility turns a local source-packaging helper into a portable
command. It does not discover content, generate a real publication inventory,
extract archives, restore files, change source files, sign releases or upload
anything. A maintainer must review the selected source, licensing and privacy
before building. A successful hash check does not establish ownership, remove
secrets or make third-party material eligible for MIT licensing.

## Setup

Download the collection with **Code → Download ZIP**, extract it outside game
folders, and open PowerShell in `tools\source-release-builder`:

```powershell
py -3.12 --version
py -3.12 -B source_release.py --help
py -3.12 -B source_release.py --version
```

Use `python` if that is your Python 3.12+ interpreter. Linux/macOS users can use
`python3`. No dependencies, virtual environment or execution-policy changes are
needed. `-B` avoids creating bytecode caches beside source.

## Try the generated example

The example uses original toy source and copies this collection's MIT notice.
Choose a new folder each time; it must be outside the downloaded collection:

```powershell
$demo = Join-Path $env:TEMP ('outlands-source-demo-' + [guid]::NewGuid().ToString('N'))
py -3.12 -B examples\create_example.py --destination $demo
py -3.12 -B source_release.py `
  --source-root "$demo\source" `
  --output "$demo\demo-source.zip" `
  --prefix example-v1.0.0
$LASTEXITCODE
Get-Content -LiteralPath "$demo\demo-source.zip.sha256"
```

Expect exit **0**, `status: PASS`, three source files and four archive members:
`LICENSE`, `README.md`, `hello.py`, and the exact `SOURCE-MANIFEST.json`, all under
`example-v1.0.0/`. The generated `unlisted.md` is deliberately excluded.

Build again with a different output filename and the same inputs/prefix:

```powershell
py -3.12 -B source_release.py `
  --source-root "$demo\source" `
  --output "$demo\demo-source-second.zip" `
  --prefix example-v1.0.0
(Get-FileHash -Algorithm SHA256 -LiteralPath "$demo\demo-source.zip").Hash -eq `
  (Get-FileHash -Algorithm SHA256 -LiteralPath "$demo\demo-source-second.zip").Hash
```

Expect `True`. Reusing an existing output refuses the build. Changing a listed
toy source without updating its reviewed manifest also refuses the build.
Delete only your generated demo folder with your normal file manager when done.
See [the example notes](examples/README.md).

## Build a reviewed collection

Stop editors, generators and sync tools that might write selected inputs. Use
an existing local source tree whose canonical root `SOURCE-MANIFEST.json` is
already reviewed and current. Both output parents must already exist; the tool
creates only a new ZIP and its new adjacent checksum file:

```powershell
py -3.12 -B source_release.py `
  --source-root 'D:\Projects\outlands-game-tools' `
  --manifest 'D:\Projects\outlands-game-tools\SOURCE-MANIFEST.json' `
  --output 'D:\Releases\outlands-game-tools-v0.1.0-source.zip' `
  --prefix outlands-game-tools-v0.1.0
$LASTEXITCODE
```

Replace example paths with your own. `--manifest` is optional and can only name
that canonical root manifest. Omit `--prefix` for files directly at the ZIP
root. A prefix is one portable folder name, 1–80 ASCII letters/numbers, `_`, `-`
or `.`, starting with a letter/number; reserved device names and trailing dots
are rejected.

The builder never inventories the whole source tree. It copies **only** files
listed in the manifest, plus that manifest's exact bytes. Unlisted files remain
excluded, even if their extensions are allowed. This makes the reviewed list
the publication boundary, rather than whatever happens to be in a folder.

For this collection, maintainers use `tools/verify_source_release.py` to inspect
the source selection before regenerating `SOURCE-MANIFEST.json`. That separate
gate checks additional collection-specific rules. Do not point an inventory
generator at a game directory or treat automatic inventory generation as a
review. The builder itself does not search for credentials, personal data,
private endpoints or third-party copyright.

## What can be included

The schema is described in [REPORT-FORMAT.md](REPORT-FORMAT.md). A manifest must
declare `schema_version: 1` and `license: "MIT"`; it must list the root `LICENSE`
with its current byte count and SHA-256. The license text must contain the
standard MIT grant, notice condition and disclaimer. This format/text check
does not establish legal rights over the other selected files.

Allowed source suffixes are `.md`, `.py`, `.cs`, `.csproj`, `.ps1`, `.json`,
`.yml`, `.yaml`, `.config`, `.html`, `.js`, `.css`, `.cfg`, `.gsc` and `.csv`.
Files named exactly `LICENSE`, `.gitignore` or `.gitattributes` are also allowed.
Only these two dependency-list paths are allowed as `.txt`:

- `tools/lua-syntax-checker/requirements.txt`
- `tools/audio-integrity-checker/requirements.txt`

Every selected file must be UTF-8 text without NUL bytes. Executables, DLLs,
ZIPs, media, game assets, actual saves and raw `.log` files are outside this
allowlist. Text/code extensions can still contain private or third-party data;
maintainers must review their contents and provenance. Actual profile exports
and renamed binary files do not become appropriate release content merely by
using an allowed suffix.

## Limits and path protections

| Limit | Maximum |
|---|---:|
| Manifest bytes | 16 MiB |
| Listed source files | 100,000 |
| Each listed file | 2 MiB |
| Sum of listed source bytes | 256 MiB |
| Relative path length | 1,024 ASCII characters |
| Path depth including filename | 128 components |

The manifest is additional to the 256 MiB source-byte total. Integer values
must be real nonnegative JSON integers, not booleans. Duplicate JSON keys,
unknown fields, self-listed manifests and case-colliding paths/directories are
rejected. Paths use `/` separators and portable ASCII components: no traversal,
backslashes, control characters, drive/UNC/device paths, alternate data streams,
reserved device names, trailing spaces/dots or file/directory collisions.
Runtime/repository directories such as `.git`, `.venv`, `bin`, `obj`,
`__pycache__`, `node_modules`, `.audit`, `.validation` and `artifacts` are excluded.
A component trie checks file/directory and casing collisions without retaining
every joined ancestor path; the depth budget bounds per-path traversal work.

Source roots, selected files, manifests, output parents and all their ancestors
must be ordinary local paths. Symbolic links, Windows junctions/reparse points,
special files and network namespaces are refused. ZIP/checksum destinations
must be outside the source root and must both be new. Parent folders are never
created automatically. Source files are opened read-only; identity, length,
mtime and SHA-256 are checked across the build, including after copying.

Pause other writers. These are local consistency checks, not an atomic snapshot,
hostile-filesystem sandbox or lock against a writer changing and restoring a
file between checks. The tool does not control operating-system caching,
concurrent processes, permissions or cloud synchronization.

## ZIP format and failed builds

Members are sorted, use a fixed `1980-01-01 00:00:00` timestamp and ordinary
`0644` file permissions, and contain no absolute source roots. ZIP members are
stored **without compression** (`ZIP_STORED`), so original bytes and metadata
produce deterministic archives without a zlib dependency. No symlink or
directory entries are emitted. ZIP64 is used by Python only when required by
the member count. Source bytes are streamed in 64 KiB blocks; the whole archive
is never buffered in memory. The bounded manifest and file table are kept in
memory. Each completed ZIP member is read back with CRC and SHA-256 checks.

Both destinations are exclusively created before archive writing. If a failure
occurs, the tool attempts to delete only output files this invocation created
and still owns by file identity. Existing outputs are never removed. A normal
failure reports how many outputs were removed; `partial_outputs_possible: true`
means manual inspection is necessary. A forced process termination or power
loss can leave partial files, and no automatic future cleanup occurs. Never
publish an output from a failed or interrupted run.

## Verify the downloaded checksum

In PowerShell, compare the downloaded ZIP's hash with the adjacent checksum:

```powershell
$zip = 'D:\Downloads\outlands-game-tools-v0.1.0-source.zip'
$expected = (Get-Content -LiteralPath ($zip + '.sha256') -Raw).Substring(0, 64)
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash
$actual -ieq $expected
```

Expect `True`. On Linux, open a terminal in the download folder and run:

```bash
sha256sum -c outlands-game-tools-v0.1.0-source.zip.sha256
```

The checksum file uses the standard `HASH`, two spaces, ZIP filename and LF
format. It detects accidental byte differences when the checksum is trusted;
it is not a signature or a guarantee of authentic origin, safe code or licensing.
Download the checksum and ZIP from the same intended release and review its
source/release notes.

## Results, privacy and tests

Exit **0** means the ZIP members and checksum were verified. Exit **1** means
refusal or failed/incomplete creation. Standard output is one bounded JSON
object; ordinary failures use controlled codes rather than raw exception text
or absolute input roots. `--help` and `--version` print normal human-readable
text. See [REPORT-FORMAT.md](REPORT-FORMAT.md) for fields and failure codes.

Archive basenames, relative source paths, source content and hashes may still
be sensitive. A manifest records content fingerprints; renaming its parent
folder does not anonymize the files. Review the actual archive and manifest
before sharing them. No data is sent anywhere by this tool.

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Tests generate original toy files, exercise member-byte/checksum equality,
determinism, input immutability, changed/missing data, strict schemas, path and
link guards, caps, exclusive outputs and failure cleanup. Native symlink tests
skip with an explicit reason when the account cannot create them; a separate
Windows junction test runs where supported. Tests do not use installed games,
actual saves, profiles or logs. Their success is source-packaging evidence,
not gameplay validation.

## Suggestions and license

Original code, tests, examples and documentation use the collection's
[MIT license](../../LICENSE). Python and third-party source selected by other
projects retain their own terms. This tool must not be used to relabel AGPL
code or other third-party implementations as MIT.

Use [suggestions](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
for ideas, or [bug reports](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml)
for failures. Include the tool version, OS/Python version, controlled error code
and a small original synthetic reproduction. Review attachments and remove
private paths, source contents, credentials, real profiles and third-party
assets before posting. Contributions and practical usability suggestions are
welcome; describe the problem and expected behavior before a large change.
