# LTX Definition Inspector

Find missing parent declarations, duplicate section names, repeated includes,
and cycles in a selected set of loose LTX configuration files. This standalone
Python tool produces a JSON report without changing the inspected files or
starting a game.

**This is a narrow structural inspector.** It records section names, ordered
parent references, and literal relative includes. It does not merge values,
apply DLTX patches, calculate effective settings, reproduce an engine loader,
or certify that a game or modpack works. A clean report applies only to the
explicit entry files and their reachable, supported includes.

The implementation, tests, documentation, and fictional example generator are
original MIT-licensed source under the repository's [MIT license](../../LICENSE).
No game files or third-party parser implementation are bundled. Python **3.12
or newer** is required. There are no third-party Python dependencies.

## Setup

Download this repository with **Code → Download ZIP**, extract it outside your
game/configuration tree, and retain the root license. Open PowerShell in
`tools\ltx-definition-inspector`:

```powershell
py -3.12 --version
py -3.12 -B ltx_inspector.py --help
py -3.12 -B ltx_inspector.py --version
```

On Linux or macOS, from the same folder:

```bash
python3 --version
python3 -B ltx_inspector.py --help
```

No installation, administrator privileges, virtual environment, package
downloads, or network access are needed to inspect files. `-B` suppresses
Python bytecode cache files beside the source.

## Inspect a configuration tree

Use an existing local directory as the boundary and give each entry relative
to that directory. Includes resolve relative to the file containing them:

```powershell
py -3.12 -B ltx_inspector.py `
  --root 'D:\ConfigCopy' `
  --entry 'system.ltx' `
  --output 'D:\Reports\ltx-report.json'
$LASTEXITCODE
```

`D:\Reports` must already exist and the report filename must be new. Reports
cannot be placed anywhere inside `--root`. Omit `--output` to write JSON to
standard output. The tool never overwrites a report, creates a parent folder,
or modifies the inputs. Avoid redirecting stdout into the input tree because
your shell creates redirected files independently of this tool's safeguards.

Several entries contribute to one declaration scope:

```powershell
py -3.12 -B ltx_inspector.py `
  --root 'D:\ConfigCopy' `
  --entry 'items\items.ltx' `
  --entry 'shared\bases.ltx'
```

Choose entries that represent the context you intend to review. A missing
parent means that the declaration was absent from **this selected graph**;
another game configuration or omitted entry might supply it. The inspector
does not infer which other entries your game loads, mount archives, inspect
MO2's virtual filesystem, or establish mod priority. Use an already prepared
loose-file copy with the intended providers selected when checking a mod stack.

## Supported subset

Supported input filenames end in `.ltx` or `.ini`. The subset accepts:

- `[section]` and `[section]: parent_one, parent_two` declarations. Identifiers
  use ASCII letters, digits, underscores, dots, or hyphens, beginning with a
  letter, digit, or underscore. Names are normalized to lowercase; parent
  order is retained in the report.
- `#include "relative/path.ltx"` with one literal filename. Both `/` and `\`
  separators are accepted. An include may use `..` if the result remains
  inside the chosen root. Entry arguments themselves cannot use `.` or `..`.
- Blank lines, `;` and `//` comments outside double-quoted strings, ordinary
  assignments, and bare list keys within a section. Keys may additionally
  contain `$`. Values are discarded after checking for unsupported quoting.
- Strict UTF-8 by default, including a UTF-8 BOM. Use `--encoding cp1251` for a
  known Windows-1251 source tree. Decoding never silently replaces characters.

DLTX operations such as `![section]`, `@[section]`, `>[section]`, removal or
list-edit prefixes, unknown directives, wildcard includes, multiline strings,
escaped double quotes, complex identifiers, and unfamiliar structural syntax
produce an incomplete report. The rest of that file is not parsed after the
first unsupported construct; previously read declarations remain partial
evidence. This deliberately conservative behavior avoids silently pretending
to apply a different configuration language.

The syntax reference used to check ordinary includes, section inheritance,
and comment forms was the primary [OpenXRay configuration loader](https://github.com/OpenXRay/xray-16/blob/dev/src/xrCore/xr_ini.cpp).
That loader also supports behavior outside this tool's subset, including
wildcard includes and multiline values. Its source is referenced for context;
none of its implementation is included here.

## Interpreting results

| Exit | Meaning |
| --- | --- |
| `0` | The supported selected graph was inspected completely and no review findings were found. |
| `2` | Inspection completed and found missing parents, duplicate sections, repeated includes, or declared inheritance cycles. |
| `1` | Inspection was incomplete or could not run: missing/unreadable includes, include cycles, unsupported syntax/encoding, path rejection, limits, empty declaration scope, or report-write failure. |

Incomplete status takes precedence over review findings. A normal JSON report
includes `complete` and `exit_code`; invalid command-line syntax returns exit
`1` with usage text and `INVALID_ARGUMENTS`, without a JSON report. Use `--help`
to check option names and limit requirements.

Every reachable file is parsed **once**, rather than textually expanded at
every include occurrence. Repeated includes are review findings; they do not
duplicate the same file's declarations in the report. Duplicate sections mean
two or more explicit declarations across the unique files. No winning
definition is selected. Inheritance cycles refer to the union of the recorded
parent edges, including edges from duplicate declarations; they are review
candidates rather than an effective merged configuration. Cycle reporting uses
DFS back edges and supplies example closed paths, not every possible cycle.

Missing includes and include cycles are both findings worth investigating and
reasons the selected include graph cannot be considered complete. A pass does
not validate key/value types, scripts, resource paths, runtime registration,
parent load order, or engine compatibility. File order in the JSON is an
inspection order, not a promise of engine processing order.

See [REPORT-FORMAT.md](REPORT-FORMAT.md) for fields, codes, and a small report
example, and [examples/README.md](examples/README.md) for a runnable walkthrough.

## Resource and path safeguards

| Option | Default |
| --- | ---: |
| `--max-file-bytes` | 2,097,152 (2 MiB) |
| `--max-total-bytes` | 33,554,432 (32 MiB) |
| `--max-files` | 4,096 attempted distinct files |
| `--max-depth` | 64 include edges from an entry |
| `--max-records` | 100,000 combined includes, declarations, and parent references |
| `--max-report-bytes` | 16,777,216 (16 MiB) of serialized graph-report JSON |
| Directory entries per case lookup | 100,000 (fixed; input, output, and example destination) |

All limit arguments must be positive integers below Python's `sys.maxsize`.
Entries have depth zero. The first traversal reaching a file determines its
inspection depth; a report hitting a depth limit remains incomplete even if
another selected path later reaches that file more directly. Bounds are
also applied to cycle-report expansion: each graph can report at most
`--max-records` total nodes across its example cycle paths. Reaching this cap
or a fixed 4 MiB estimated JSON character budget per graph marks the report
incomplete with `CYCLE_REPORT_LIMIT`. Serialization is also bounded: if the
graph report exceeds `--max-report-bytes`, it is replaced by a small incomplete
report containing `REPORT_BYTE_LIMIT` and empty result arrays. This minimal
error report may exceed an impractically tiny user-selected byte budget.
These are
conservative controls, not a hostile-input sandbox. Use trusted local copies
and practical limits rather than raising every limit to its maximum.

The tool rejects symlinks, Windows junctions/reparse points, network/device
paths, unsafe portable filenames, case ambiguity/mismatches, and includes
escaping the root. It reads validated regular files through read-only handles
and checks file identity/metadata before and after reading. Input ancestry is
also checked. These checks detect ordinary concurrent replacement or change;
they do not provide a transactional filesystem snapshot or defend against an
attacker racing directory changes. Close editors or work on a stable copy.
Directory case checks stream entries and stop with `DIRECTORY_ENTRY_LIMIT`
after 100,000 entries instead of loading an unbounded directory listing.
Windows device basenames, including console aliases and COM/LPT superscript
variants, are rejected on every platform.

Reports omit absolute input roots, raw values, comments, directive text, and
raw system exception messages. They retain relative paths, section/parent
names, and line numbers, which can still reveal private project information.
Review a report before sharing it publicly. The tool never uploads a report.

## Test and contribute

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Linux/macOS: replace `py -3.12` with `python3`. Tests create original temporary
text files, exercise both successful and incomplete scans, test graph/path
limits and source immutability, and run the CLI as a subprocess. Windows tests
use temporary junctions; platforms that cannot create the relevant link mark
that check explicitly skipped. The case-only filename collision test is
explicitly skipped on ordinary Windows filesystems. No game is needed.

[Suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
or [report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml).
Include your OS, Python/tool version, command with private paths removed,
expected behavior, exit code, and a **small original example** that reproduces
the issue. Review JSON before attaching it. Please do not upload game files,
modpack source, saves, or private logs. Useful suggestions include additional
documented syntax with minimal original fixtures and clearer scope guidance.
See the collection's [contribution guide](../../CONTRIBUTING.md).
