# INI/LTX Configuration Value Diff

Compare literal settings in two explicitly selected local text files. Reports
show added/removed sections and keys, changed values, and changed ordered LTX
parent declarations. This original MIT utility reads inputs without modifying
them; an optional report is an exclusive new JSON file.

This is a documented literal subset, not a game configuration loader. It does
not load includes, apply DLTX, merge inherited/default values, interpolate
variables, evaluate expressions or determine the settings a game actually uses.
No game configurations, third-party parser implementations or assets are bundled.

## Setup and download

Use **Code → Download ZIP** on the collection's current `main` branch and extract
outside game/save/mod-manager folders. This addition is absent from the older
v0.1.0 release assets. Open PowerShell in `tools\ini-ltx-value-diff`:

```powershell
py -3.12 --version
py -3.12 -B config_value_diff.py --help
```

Python **3.12+**, using only its standard library, is sufficient. No pip install,
administrator rights or execution-policy changes are needed. Use `python` if
that is your verified Python 3.12+ interpreter; Linux/macOS users can use
`python3` and `/` paths. `-B` avoids bytecode caches beside the source. Windows
and Ubuntu are covered by CI; macOS has not been independently verified.

## Try original examples first

The generator creates four original toy files in a new folder. It refuses an
existing destination and does not copy anything from an installed game.

```powershell
$demo = Join-Path $env:TEMP ('outlands-value-diff-' + [guid]::NewGuid().ToString('N'))
py -3.12 -B examples\create_example.py --destination $demo
py -3.12 -B config_value_diff.py --before "$demo\before.ini" --after "$demo\after.ini" --dialect ini --output "$demo\ini-report.json"
$LASTEXITCODE
py -3.12 -B config_value_diff.py --before "$demo\before.ltx" --after "$demo\after.ltx" --dialect ltx --output "$demo\ltx-report.json"
$LASTEXITCODE
```

Both comparisons return **2**, meaning a complete comparison with differences.
The INI example has one added, two removed and two changed keys, with three
unchanged keys. The LTX example has one changed parent list, one added, one
removed and one changed key, with four unchanged keys. An empty value and an
absent key are different. Parent declarations are context; no values are inherited.

To see the toy values, explicitly opt in and choose a different new report:

```powershell
py -3.12 -B config_value_diff.py --before "$demo\before.ini" --after "$demo\after.ini" --dialect ini --include-values --output "$demo\ini-values.json"
```

Linux/macOS equivalent:

```sh
demo="${TMPDIR:-/tmp}/outlands-value-diff-$$"
python3 -B examples/create_example.py --destination "$demo"
python3 -B config_value_diff.py --before "$demo/before.ini" --after "$demo/after.ini" --dialect ini --output "$demo/ini-report.json"
echo "$?"
python3 -B config_value_diff.py --before "$demo/before.ltx" --after "$demo/after.ltx" --dialect ltx --output "$demo/ltx-report.json"
echo "$?"
```

Expect **2** then **2**; account for these statuses in scripts using `set -e`.
Comparing a supported file to itself returns **0**. Existing output files are
refused, including when rerunning the same command. See the
[example notes](examples/README.md) and [report guide](REPORT-FORMAT.md).

## Select your own pair

Close editors, deployment/sync programs and other writers for the selected files.
The tool does not close programs, lock files or create an atomic snapshot.

```powershell
py -3.12 -B config_value_diff.py `
  --before 'D:\Modding\Comparison\before.ltx' `
  --after 'D:\Modding\Comparison\after.ltx' `
  --dialect ltx --output 'D:\Reports\settings-diff.json'
$LASTEXITCODE
```

Replace paths with your own. `--dialect ini|ltx` is required; file extensions do
not select a parser. Input files and their ancestors must be ordinary local
paths. Symlinks, Windows junctions/reparse points, devices, UNC/network paths,
drive-relative paths and unsafe portable filenames are refused. The two inputs
may be the same file. No other config files are loaded or recursively inventoried.

Without `--output`, JSON goes to stdout. A selected output must be a new file,
separate from both inputs, with an already existing ordinary parent directory.
It may be beside the inputs. Input/output path comparisons conservatively reject
casefold-equal names even on a case-sensitive filesystem. No directory is created
by the checker, and existing outputs or inputs are never overwritten.

## Literal syntax and policies

| Rule | Behavior |
|---|---|
| Assignments | Split at the first `=`. Trim ASCII space/tab at syntax and value edges; preserve other literal characters and inner whitespace. |
| Identifiers | Nonempty ASCII letters, digits, `_`, `.`, `$`, `-`; keys also allow `:`. INI section names also allow internal spaces. Maximum 255 characters. |
| Case | `--case sensitive` is the default. `--case insensitive` lowercases section/key/parent names for matching and reporting; values remain case-sensitive. |
| Repeated sections | Rejected under the selected case policy, including when duplicate keys use `last`. |
| Duplicate keys | Rejected by default. `--duplicate-keys last` retains the final assignment within a section and reports discarded-assignment counts. |
| INI globals | Assignments before the first section use JSON `section: null`; they are separate from every named section. |
| `[DEFAULT]` | An ordinary named section with no default inheritance. |
| LTX parents | `[child]:parent_one,parent_two` records ordered literal names. Order/spelling under the case policy is compared; parents are not resolved, merged or checked for existence/cycles. |
| Full-line comments | `;` comments in both dialects. INI accepts `#` comments. LTX accepts bare `#` or `#` followed by ASCII space/tab; a tight `#directive` is unsupported. |
| Includes | A directive-looking `#include` line, including spaced/case variants, is unsupported in both dialects. No referenced file is opened. |
| Inline comments | `--inline-comments none` is the INI default; `semicolon` is the LTX default. An explicit option overrides either default. Inline `#` is always literal. |

With inline comments `none`, the entire RHS after ASCII edge trimming is literal,
including semicolons and unmatched quotes. With `semicolon`, the first semicolon
outside double-quote regions starts a comment. Double quotes must balance before
that comment; their spelling stays in the value. Backslash is ordinary, with no
escape processing. Single quotes do **not** protect a semicolon: `x='a;b'` stores
the literal substring `'a` under this selected policy. Use `none` when semicolons
are data. This is a tool policy, not a claim about every INI parser or game engine.

Values are never converted: `1` differs from `01`, `true` from `1`, `"a"` from
`a`, and `a,b` from `b,a`. `%NAME%`, `${name}`, backslashes and condition-like
text remain inert strings. Empty RHS is a present empty string, not a missing key.

Only CR, LF and CRLF form physical lines. U+2028/U+2029 remain literal value
characters; nonbreaking spaces at value edges remain data. C0/C1 controls are
refused except tab and line breaks, even inside comments. Colon-only delimiters,
bare keys, multiline continuations, malformed headers, DLTX and other unsupported
syntax make comparison incomplete. An indented `key=value` is still an assignment,
not a continuation. Both files are parsed fully before any difference is committed,
including content inside added or removed sections.

Section/assignment order, line locations, comment changes and source byte hashes
are not themselves value differences. With `last`, discarded duplicate values
are not compared; their counts are informational. Equality means equality of the
supported parsed maps and parent lists under the recorded policies.

## Encodings, bounds and exit status

`--before-encoding` and `--after-encoding` independently select `utf-8-sig`
(default, accepting optional UTF-8 BOM), `cp1251`, or `utf-16`. UTF-16 requires a
BOM and accepts either byte order. Decoding is strict, with no guessing/fallback.

```powershell
py -3.12 -B config_value_diff.py --before 'D:\Comparison\old.ini' --after 'D:\Comparison\new.ini' --dialect ini --before-encoding utf-16 --after-encoding utf-8-sig
```

| Option | Default | Hard ceiling |
|---|---:|---:|
| `--max-file-bytes` | 2097152 per input (2 MiB) | 16777216 (16 MiB) |
| `--max-lines` | 100000 physical lines per input | 1000000 |
| `--max-records` | 20000 per input | 200000 |
| `--max-changes` | 20000 combined section/value rows | 200000 |

Records count every section header and assignment, including overwritten
duplicates. Blank/comment lines still count toward the line limit. Additional
fixed ceilings are 65536 decoded characters per line, 256 parents per section,
1024 characters/128 components per absolute local path, a cumulative **16 MiB
metadata accounting budget**, and **8 MiB** for encoded JSON. Each parent item is
charged separately before retention. The accounting budget is conservative,
includes overwritten records and both inputs, and is not a process-RAM guarantee.

| Exit | Meaning |
|---|---|
| `0` | Complete literal comparison with no section/value changes. |
| `2` | Complete literal comparison with differences. |
| `1` | Invalid, unsupported or incomplete processing, limit, input change or output failure. |

Check both the process status and JSON `complete`. An incomplete result clears
all difference rows and summary counts; it is not an equality claim. Controlled
errors identify `before`/`after` and a one-based source line when known, without
printing the source line or native exception. Command-line errors may occur before
useful input metadata exists. Pause writers: identity/stat checks are best effort,
not an atomic snapshot or a sandbox against hostile filesystem races.

## Privacy, tests and suggestions

Default reports show parsed-value SHA-256 fingerprints and character lengths,
not RHS text. `--include-values` deliberately exports actual changed/added/removed
values. Neither mode anonymizes a report: section/key/parent names, line numbers,
counts, hashes and lengths may identify private material or permit guessing small
values. The tool adds no absolute input paths/filenames or raw exceptions;
opt-in values can themselves contain private paths. There is
no general secret detector/redactor. Review every report before sharing it.

Run tests from this module directory:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Tests use original generated text and cover syntax/case/duplicate policies,
encodings, exact fingerprints/changes, privacy, unchanged source bytes, guards,
limits and exclusive outputs. Native link fixtures skip explicitly when the
platform/account cannot create them. Tests establish no actual game loader,
modpack, inherited/effective settings, MO2 VFS or gameplay compatibility.

[Bug reports](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml)
and [suggestions](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
are welcome. Include OS/Python/tool version, selected policies, sanitized command,
exit status, and a small original before/after pair. Documentation fixes and
alternative approaches are useful too; you do not need finished code. Avoid real
game configurations or private reports. Read the collection's
[contributing guide](../../CONTRIBUTING.md) and [MIT license](../../LICENSE).
