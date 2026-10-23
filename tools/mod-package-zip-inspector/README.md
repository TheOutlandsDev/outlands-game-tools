# Mod Package ZIP Layout Inspector

Review a downloaded mod's ZIP layout before deciding how to install it. This
standalone Python 3.12+ tool lists member names, declared sizes and layout
findings in JSON. It never extracts, installs, executes, decrypts or decompresses
archive members. Original source, tests and examples use the root [MIT license](../../LICENSE).
No game, account, mod manager or additional Python package is needed.

## Quick start

Download current **main** using GitHub **Code → Download ZIP**, or clone the
[collection](https://github.com/TheOutlandsDev/outlands-game-tools). This tool is
newer than the collection's historical v0.1.0 release assets.
Open a terminal in the repository root. On Windows:

```powershell
py -3.12 -B tools/mod-package-zip-inspector/examples/create_example.py --destination ../outlands-zip-demo
py -3.12 -B tools/mod-package-zip-inspector/zip_inspector.py --archive demo=../outlands-zip-demo/clean.zip
py -3.12 -B tools/mod-package-zip-inspector/zip_inspector.py --archive demo=../outlands-zip-demo/review.zip --output ../outlands-zip-demo/review-report.json
$LASTEXITCODE
```

On Linux/macOS replace `py -3.12` with `python3`. The generator requires a new
destination with an existing parent. It creates three tiny fictional archives;
no real game or downloaded mod files are included. Expected exits are **0** for
`clean.zip`, **2** for `review.zip` and **2** for `wrapper.zip`.

To inspect your own explicitly selected archive:

```powershell
py -3.12 -B tools/mod-package-zip-inspector/zip_inspector.py --archive 'download=D:/ModDownloads/My Mod.zip' --output 'D:/Reports/new-zip-review.json'
```

Use an ordinary local file and an existing ordinary output directory. Output
must be new; the tool refuses to overwrite a report or the input. Without
`--output`, JSON goes to standard output. Quotes preserve spaces. The alias
before `=` must be 1–64 ASCII letters/digits/`_.-`, starting with a letter/digit.
Absolute local input paths are omitted from reports; member names remain visible.
Reports can expose private archive filenames or directory structure, so review
them before posting. Neither archives nor reports are uploaded by this program.

## Reading the result

| Exit | Meaning | Next action |
|---|---|---|
| 0 | Complete inspection of the supported metadata subset; no configured findings | Review the mod author's installation instructions. This is not a safety or compatibility certificate. |
| 2 | Complete metadata inspection with findings | Review member `issues` and archive `issues`; resolve questions before installation. |
| 1 | Incomplete, unsupported, malformed, limited or failed operation | Read `errors[].code`. No partial member inventory is returned as a complete result. |

`--help` and `--version` are informational successful exits with plain text.
The [report format](REPORT-FORMAT.md) defines fields, limits, thresholds and error
categories. A failed output write falls back to a small incomplete JSON report on
standard output when possible. A caller piping JSON should inspect the exit code.

Checks include parent/absolute/drive/stream/backslash paths, reserved Windows
names and trailing dots/spaces; exact duplicate names; case/NFC normalization
collisions; file-versus-directory prefixes; Unix link/special metadata; encryption
flags; unknown extra fields; unusually large declared sizes and ratios.
Non-ASCII names require review because filesystem normalization differs.
The tool preserves embedded NULs in escaped JSON instead of silently truncating them.

A common top-level folder is an observation requiring review, not a claim that a
folder should be removed. `gamedata/`, `BepInEx/` and other legitimate roots can
trigger the same observation. No installation root, mod priority, load order or
automatic repair is inferred. Duplicate names record the first provider; output
does not expand every possible pair of colliding members.

## Supported ZIP subset and limits

The initial implementation reads **single-disk, contiguous classic ZIP32**:
stored/deflated methods 0/8, extraction version at most 2.0, UTF-8 or CP437 names,
ordinary local headers, optional classic signed/unsigned data descriptors, central
directory and end record with an optional archive comment. Local names, flags,
methods, dates and declared CRC/sizes must agree with the central metadata.
Member ranges must be contiguous from byte zero up to the central directory,
without gaps, overlap, prepended executable stubs or trailing data.

ZIP64 (including small files using ZIP64), multi-disk, other compression methods,
central encryption, Unicode override extra fields and advanced flags/layouts
return incomplete. This is a deliberately conservative subset; many valid ZIPs
fall outside it. Traditional entry-encryption flags can be listed and flagged,
but encryption headers and encrypted contents are not validated or decrypted.
Other extra fields are structurally bounded and flagged as uninterpreted.

Before allocating a central-directory inventory, the parser bounds the archive
end search, declared directory bytes and member count. It does not instantiate
`zipfile.ZipFile` on untrusted input. Hard limits: archive below 4,294,967,295
bytes; 10,000 entries; 8 MiB central directory; 1,024 encoded name bytes;
32 MiB cumulative metadata reads; 32 MiB cumulative JSON-plus-overhead accounting;
8 MiB final JSON. Accounting is not a guarantee of process resident memory.
Review thresholds: entry over 1 GiB, total over 8 GiB, or an entry over 1 MiB with
declared expansion greater than 1000×. These are metadata assertions, not measured
decompression costs. Limits and thresholds are fixed in version 1.0.0.

The bounded end-record search may incidentally read compressed bytes in the
last 65,557 bytes of the archive. The program seeks over payload ranges for
structural checks; it does not inspect their contents or verify CRCs. The central
SHA-256 identifies the bytes inspected, not the whole archive or its authenticity.
A structurally consistent archive with corrupted payloads can return exit 0.
Nested archives, executable behavior, malware, packed assets and dependencies are
not inspected. Filesystem identity/size/time checks detect ordinary input changes;
they do not provide an atomic snapshot against a hostile concurrent writer.
Use a stable local file. Input and output ancestor symlinks/reparse points, UNC,
device and drive-relative paths are refused; no network paths are opened.

## Test and contribute

```powershell
py -3.12 -B -m unittest discover -s tools/mod-package-zip-inspector/tests -v
```

The suite uses stdlib-generated original archives and deliberately malformed
metadata, tests no-extraction behavior, corruption scope, path collisions,
bounded parsing, output protection and supported descriptors. CI runs Windows
and Linux on Python 3.12/3.13; native link tests explicitly skip when unavailable.
See [examples](examples/README.md) and the collection's [validation record](../../VALIDATION.md).

[Suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
or [report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml).
Questions and small reproducible examples are welcome; no code contribution is
required. Select this tool in the bug form, include the tool/Python/OS versions,
command with private paths replaced, exit code and relevant error/finding code.
Prefer a generated minimal ZIP recipe over uploading someone else's mod or game
assets. Explain which layout your installer expects and why an observation was
helpful or misleading. See [contributing](../../CONTRIBUTING.md).

Format facts were checked against [PKWARE APPNOTE 6.3.10](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT)
and [Python 3.12 ZIP documentation](https://docs.python.org/3.12/library/zipfile.html).
No specification text or third-party parser implementation is bundled.
