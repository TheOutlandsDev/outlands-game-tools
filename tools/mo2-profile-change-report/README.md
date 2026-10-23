# MO2 Profile Change Report

Explain changes between two saved Mod Organizer 2 `modlist.txt` files: added and
removed mods, enabled/disabled entries, spelling differences and relative-order
changes. Separators and foreign entries have their own report groups. The tool
reads only the two files you select and writes a new JSON report when requested.
It never starts MO2, edits a profile, scans mod folders or launches a game.

Original implementation, tests and examples use the root [MIT license](../../LICENSE).
Python **3.12+**, standard library only. No game, mod manager, account or extra
Python package is needed to try the fictional examples.

## Quick start

Download current **main** through GitHub **Code → Download ZIP**, or clone the
[collection](https://github.com/TheOutlandsDev/outlands-game-tools). This module
was added after the historical v0.1.0 release assets. Open a terminal at the
repository root. On Windows:

```powershell
py -3.12 -B tools/mo2-profile-change-report/examples/create_example.py --destination ../outlands-profile-demo
py -3.12 -B tools/mo2-profile-change-report/profile_change_report.py --before ../outlands-profile-demo/before/modlist.txt --after ../outlands-profile-demo/after/modlist.txt --output ../outlands-profile-demo/changes.json
$LASTEXITCODE
```

On Linux/macOS replace `py -3.12` with `python3`. The example generator requires a
new destination with an existing parent. It creates two fictional profile folders
containing only `modlist.txt`. Expected report exit: **2**, meaning changes found.

The example reports one added mod, one removed, one enabled and one disabled.
Three shared mods participate in a relative-order change, and one separator has
changed its placement. All names and contents are original toy data.
See the [worked example](examples/README.md).

## Compare your own saved files

Close MO2 and other profile writers, or use stable copies of the saved files.
Select the earlier file with `--before` and later file with `--after`:

```powershell
py -3.12 -B tools/mo2-profile-change-report/profile_change_report.py --before 'D:/MO2/profiles/Baseline/modlist.txt' --after 'D:/MO2/profiles/Testing/modlist.txt' --output 'D:/Reports/new-profile-changes.json'
```

Use ordinary local files. Output is optional; omit `--output` for JSON on standard
output. A requested output must be new and its parent must already exist. The
program refuses to overwrite either selected input or an existing report. The
same input can be selected twice for an equality check. The comparison is
directional: reversing the arguments swaps additions/removals and state changes.

| Exit | Meaning |
|---|---|
| 0 | Complete supported comparison, no semantic changes under the documented policy |
| 2 | Complete supported comparison with changes |
| 1 | Incomplete, unsupported, malformed, limited or failed operation |

`--help` and `--version` are successful informational exits with plain text.
Inspect both `complete` and the exit code when scripting. Failed/limited
comparisons return no partial inventories; `errors` contains sanitized codes and
when available the input role and line number. A report/output failure falls back
to small incomplete JSON on stdout when possible.

## What the comparison means

Names match using Python Unicode **casefold**, without Unicode normalization.
Names that match only through casefold produce `name_spelling_changed`; a real
rename with a different comparison key appears as removal plus addition. This
policy does not claim to reproduce Qt, Windows or every game's name lookup.
Duplicate and casefold-colliding names **within either input** make the entire
comparison incomplete, including duplicates across mod/foreign groups. Entries
are not silently dropped or assigned a guessed winner.

`+Name` and `-Name` are regular enabled/disabled entries. Names with the exact
case-sensitive suffix `_separator` are separator metadata, with no enabled
boolean. Separator marker changes appear separately. `*Name` is a foreign entry,
not a regular enable/disable event; its presence does not verify any actual
game/DLC files. A foreign marker combined with `_separator` is ambiguous and
refused. A change between groups appears as removal from one plus addition to
the other, without inventing a state transition.

**Reordering means a changed relative order among shared names in the same
group.** Added/removed entries and other groups are removed before comparison.
Disabled regular mods still participate. Every entry whose order reverses with
at least one other shared entry is reported, with one `crossed_with` witness.
This identifies all affected relationships; it does not guess the smallest set
of drag operations the user performed. A mod can keep its numeric rank while
crossing other mods. Inserting a new mod above existing entries does not count
as reordering those existing entries.

Separators additionally have `relocated`: a crossing of another shared entry
whose group stayed the same, including regular/foreign entries. This catches a
single separator moved across mods without labeling the mods themselves as
reordered. Separator `reordered` compares only shared separators. The two lists
can overlap; counts are observations, not a unique total of changed entries.
Foreign `reordered` compares shared foreign entries only.

Positions and ranks refer to **physical saved-file order**, starting at 1. MO2's
saved order is reversed relative to its internal priority ordering, and UI sort
settings can differ. The tool gives no GUI up/down instruction, plugin load
order, loose-file winner, compatibility or save-safety prediction. It does not
compare `plugins.txt`, `loadorder.txt`, INI files, archives, installed file
contents, overwrite data or runtime state. For file hashes use
[Mod Content Manifest & Diff](../mod-content-manifest/README.md); for selected
loose-file overlap inspection use [MO2 Conflict Inspector](../mo2-conflict-inspector/README.md).

## Accepted syntax and boundaries

UTF-8 with optional initial BOM; LF, CRLF or CR line endings; empty lines and
comments whose first character is `#`; otherwise one `+`, `-` or `*` marker
followed by a nonempty name. Names must be single conservative Windows-compatible
components of at most 255 characters: no slash/backslash, control or forbidden
punctuation, reserved device name, leading/trailing whitespace or trailing dot.
Names are not trimmed. Whitespace-only lines, unmarked entries and unsupported
encodings are refused even where an MO2 version might accept them. The separator
suffix rule is explicit; separator metadata files are not inspected.

Comments, blank lines, BOM and newline style do not affect semantic changes.
`input_bytes_equal` and each input SHA-256 still distinguish different raw files.
Unicode line/paragraph separators are not treated as extra record boundaries.
Names are escaped in JSON. Absolute local paths and comment contents are omitted,
but **mod names and hashes can be private**. Review reports before sharing them.
No input, report or telemetry is uploaded by this program.

Hard limits: 2 MiB per file, 2,048 characters per line (including comments),
50,000 split lines, 10,000 entries per input, 32 MiB cumulative JSON-plus-overhead
metadata accounting and 8 MiB final JSON. A terminal newline adds an empty split
line. Accounting is not a guarantee of process resident memory. Any limit makes
the comparison incomplete; maximum counts are not a promise that every report
fits other limits. Reorder computation is linear after filtering shared entries,
with no pairwise event explosion.

Input/output path ancestors cannot be symlinks or Windows reparse points. UNC,
device/stream and drive-relative paths are refused. Identity, size and timestamp
checks detect ordinary input changes during the comparison; they are not an
atomic snapshot against a hostile concurrent writer. Use stable local files.

## Test and leave suggestions

```powershell
py -3.12 -B -m unittest discover -s tools/mo2-profile-change-report/tests -v
```

Original synthetic tests cover all change categories, common-order relationships,
separators, foreign entries, duplicate rejection, Unicode policy, malformed input,
resource ceilings, input preservation and exclusive outputs. A separate pairwise
oracle checks all 120 permutations of five entries and 100 seeded mixed selections.
CI runs Windows/Linux with Python 3.12/3.13; native link tests declare skips when
the platform or permissions do not support fixture creation.
See [report format](REPORT-FORMAT.md) and [validation](../../VALIDATION.md).

[Suggest a feature](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_request.yml)
or [report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml).
Questions and suggestions are welcome without a code contribution. Select this
tool in the bug form and include OS/Python/tool versions, expected versus actual
change categories, exit/error codes and a minimal pair of fictional modlists.
Replace private names/paths; do not upload saves or somebody else's mod assets.
Useful suggestions include clearer reorder explanations, additional saved formats
and report views. See [contributing](../../CONTRIBUTING.md).

Saved marker/order facts were checked against
[MO2's profile implementation](https://github.com/ModOrganizer2/modorganizer/blob/4ba22f0d8b6f9e08e44008b8395cd774551b4ebe/src/profile.cpp).
Only format facts inform this original implementation; no upstream MO2 source,
Qt implementation, game data or separate AGPL launcher code is included.
