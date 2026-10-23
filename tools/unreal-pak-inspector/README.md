# Unreal PAK Index & Conflict Inspector

Read selected **standard, unencrypted version-3 Unreal PAK indexes** and report
overlapping virtual file paths. This original MIT utility verifies each index's
SHA-1 and checks metadata bounds without extracting files, opening entry payloads
or running a game. It also reports file/directory prefix conflicts across PAKs.

Support is deliberately narrow. Modern PAK versions, encrypted entries/indexes,
IoStore `.utoc`/`.ucas`, custom game layouts and non-ASCII asset names are outside
this version. An unsupported result does not diagnose a corrupt game installation.
No game assets, actual PAKs, encryption keys or third-party parser code are bundled.

## Download and setup

Use **Code → Download ZIP** on the collection's current `main` branch, and extract
outside game/save/mod-manager folders. This tool is absent from older v0.1.0
release assets. Open PowerShell in `tools\unreal-pak-inspector`:

```powershell
py -3.12 --version
py -3.12 -B pak_inspector.py --help
```

Python **3.12+**, using only its standard library, is sufficient. No pip packages,
administrator rights or execution-policy changes are required. Use `python` if
that is your verified Python 3.12+ interpreter. Linux/macOS users can use `python3`
and `/` paths; Windows and Ubuntu are tested in CI, while macOS is unverified.
`-B` prevents bytecode caches beside the downloaded source.

## Try original generated archives

The generator creates three small toy PAKs in a new directory outside the source
tree. Payloads are original placeholder text, not game assets. The generator is
a fixture builder, not a production packer or a game-ready mod creator.

```powershell
$demo = Join-Path $env:TEMP ('outlands-pak-demo-' + [guid]::NewGuid().ToString('N'))
py -3.12 -B examples\create_example.py --destination $demo
py -3.12 -B pak_inspector.py --pak "base=$demo\base.pak" --pak "mod=$demo\mod.pak" --output "$demo\overlap.json"
$LASTEXITCODE
py -3.12 -B pak_inspector.py --pak "base=$demo\base.pak" --pak "clean=$demo\clean.pak" --output "$demo\disjoint.json"
$LASTEXITCODE
```

Expect **2** then **0**. The first comparison has four entries and three unique
virtual paths, including one overlap: `toy/content/shared.uasset`. The second has
three disjoint virtual paths. `clean.pak` includes UTF-16-encoded ASCII names and
compressed-block metadata; the inspector does not decompress its payload.

Linux/macOS equivalent:

```sh
demo="${TMPDIR:-/tmp}/outlands-pak-demo-$$"
python3 -B examples/create_example.py --destination "$demo"
python3 -B pak_inspector.py --pak "base=$demo/base.pak" --pak "mod=$demo/mod.pak" --output "$demo/overlap.json"
echo "$?"
python3 -B pak_inspector.py --pak "base=$demo/base.pak" --pak "clean=$demo/clean.pak" --output "$demo/disjoint.json"
echo "$?"
```

Account for review status **2** in scripts using `set -e`. Existing demo folders
and report files are refused; use new names when rerunning. See the
[example notes](examples/README.md) and [JSON report guide](REPORT-FORMAT.md).

## Inspect your own selected PAKs

Close editors, deployment/sync tools and other writers for these files. The
inspector does not stop programs or lock files.

```powershell
py -3.12 -B pak_inspector.py `
  --pak 'base=D:\Modding\Comparison\base.pak' `
  --pak 'qol=D:\Modding\Comparison\qol.pak' `
  --output 'D:\Reports\pak-index-review.json'
$LASTEXITCODE
```

Repeat `--pak LABEL=FILE` for each explicit archive, or supply just one to inspect
its index. Labels are shareable aliases, not priority positions: 1–64 ASCII
letters/digits/`_`/`.`/`-`, starting with a letter/digit. Labels must be unique
ignoring case. Reports use aliases instead of local archive filenames/paths.
Do not put private information in labels. Argument order is not load order.

Inputs and ancestors must be ordinary local paths. Symlinks, Windows junctions/
reparse points, UNC/network/device paths, drive-relative paths and unsafe portable
names are refused. Repeated physical archives, including hardlink aliases, are
refused rather than reported as self-conflicts. No directory discovery or whole
installation scan occurs. Extensions do not select or override the parser.

Without `--output`, JSON goes to stdout. Optional output is a new file with an
existing ordinary parent directory; it may be beside the inputs, but must be
separate from all inputs. Existing paths and casefold-equal input/output names
are refused. The checker creates no directories and overwrites no file.

## Supported format and path policy

The supported subset has a 44-byte footer at EOF, magic `0x5A6F12E1`, version
exactly `3`, and a bounded flat index ending immediately at the footer. The
declared index SHA-1 must match its exact bytes. There is no checksum bypass,
version forcing, scanning for hidden footers, key input or decryption support.
Other versions may return `unsupported_pak_version` or `unsupported_footer`.

The flat index contains a mount string, count, and filename/entry records. Positive
FString lengths use strict ASCII; negative lengths use strict UTF-16LE. Both must
include their terminator, with no embedded NUL. Decoded virtual paths must still
be ASCII. Raw index bytes also receive a SHA-256 fingerprint for report comparison;
the whole archive and entry payloads are not hashed by this tool.

Mounts must use `../../../` plus an optional contained directory suffix, and end
in `/`, for example `../../../Toy/Content/`. These three parent components identify
the supported **virtual namespace**; they are never resolved against the local
filesystem. Entry names must be contained relative paths with forward slashes.
The tool strips only that agreed mount prefix and joins its suffix with the entry:

| Mount | Entry | Combined virtual path |
|---|---|---|
| `../../../` | `Toy/Content/shared.uasset` | `Toy/Content/shared.uasset` |
| `../../../Toy/Content/` | `shared.uasset` | `Toy/Content/shared.uasset` |

Empty components, `.`, `..`, absolute paths, backslashes, controls, reserved
portable device names and trailing dot/space components are refused. Paths are
limited to 1024 characters and 64 components; components to 255 characters.
Different mounts outside this subset are unsupported, not guessed or remapped.

Combined paths compare **ASCII case-insensitively** as an explicit tool policy.
Reports preserve each entry's spelling and use lowercase conflict keys. This is
not a promise about every engine/platform's case rules. Duplicate/case-colliding
file names or file/directory prefix collisions within one archive are incomplete.

## What metadata checks establish

Each declared local-entry-header plus stored-data range must fit before the index.
Ranges within an archive must not overlap or alias. Stored entries require equal
stored/uncompressed lengths. Compressed entries use the v3 absolute block-range
layout: positive bounded block counts, contiguous ordered blocks covering the
declared stored range, and a consistent uncompressed block count/size. Compressed
empty entries are unsupported. Every entry flag must be zero.

Compression identifiers are reported as raw numbers. A nonzero method can be
indexed under this block layout even when the tool has no decoder for it; no
codec or decompressed-byte claim is made. Local entry headers are **not read or
compared** with index records, payload SHA-1 values are only declared metadata,
and compressed streams/asset formats are not validated. A matching index checksum
does not authenticate an archive; someone who changes an index can replace its
checksum too. Identity/stat checks are best effort, not an atomic snapshot or
a hostile-filesystem sandbox. Pause other writers and review incomplete results.

Every overlapping path is review-worthy, even if providers declare the same
lengths or hashes. Identical index metadata does not establish identical payloads.
The tool predicts no winner, mount priority, patch suffix handling, plugin order,
live MO2 VFS, engine compatibility or game behavior. No overlap among selected
indexes says nothing about unselected PAKs, loose files, dependencies or IoStore.

## Limits and exit statuses

| Option | Default | Hard ceiling |
|---|---:|---:|
| `--max-paks` | 32 | 128 |
| `--max-archive-bytes` | 68719476736 (64 GiB) per PAK | 1099511627776 (1 TiB) |
| `--max-index-bytes` | 8388608 (8 MiB) per index | 67108864 (64 MiB) |
| `--max-total-index-bytes` | 33554432 (32 MiB) combined | 134217728 (128 MiB) |
| `--max-entries` | 50000 combined | 200000 |
| `--max-conflicts` | 10000 combined groups | 100000 |

Additional fixed ceilings: 1024 blocks per entry; 2049 serialized FString units
including the terminator; 1024 characters/128 components per absolute local path;
a cumulative **32 MiB metadata accounting budget**; and **8 MiB encoded JSON**.
Accounting charges entries, lookup keys and conflict metadata before retaining
them. It is conservative accounting, not a process-RAM guarantee. No allocation
or decompression is based on a declared uncompressed payload size.

| Exit | Meaning |
|---|---|
| `0` | Complete selected-index inspection with no conflicts. |
| `2` | Complete inspection with path overlaps or file/directory conflicts. |
| `1` | Unsupported, invalid or incomplete inspection, limit, input change or output failure. |

Check both process status and JSON `complete`. Any incomplete result clears the
PAK list, conflicts and summary instead of emitting partial success claims. Empty
supported indexes are valid but prove no game health. Errors use controlled codes
with a supplied archive alias and zero-based entry number when known, without
source strings or native exception text. Output/CLI failure may emit a small
incomplete JSON report to stdout; inspect the exit status and both streams.

## Privacy, tests and suggestions

Reports expose aliases, mount/asset paths, offsets, sizes, compression metadata,
index fingerprints and declared entry hashes. They omit added local input paths
and payload bytes; this does not anonymize data or detect all secrets. Review
every report before sharing. Hashes establish neither ownership nor redistribution
rights over inspected names or content.

Run the original generated-fixture tests from this module directory:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Tests exercise known expected metadata/conflicts, malformed binary fields,
checksums, paths, ranges, compression assertions, limits, privacy, unchanged
inputs, exclusive output and explicit platform link fixtures. They also verify
that only index/footer regions are requested. No installed PAK or game runtime
is required; synthetic passes establish no specific game's archive compatibility.

[Bug reports](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml)
and [suggestions](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
are welcome, including simpler approaches, documentation fixes and proposed
format extensions. Include OS/Python/tool version, sanitized command, status and
a small **original generated** reproduction. Do not upload game archives, keys,
real mod payloads or private reports. Read the collection's
[contributing guide](../../CONTRIBUTING.md) and [MIT license](../../LICENSE).
