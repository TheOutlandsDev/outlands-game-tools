# Mod Asset Reference Checker

Check selected literal LTX references against one local loose-file root, an
optional asset-path index, and section declarations in an explicit config
include graph. This original MIT utility reports presence observations. It does
not load a game, validate mesh/texture/audio formats, merge mods or prove that a
game can resolve a reference.

Python **3.12+** and the standard library are sufficient. Inputs are read only;
the optional report is an exclusive new JSON file. No game assets, actual mod
configuration, third-party implementations or binary dependencies are included
with the tool. The example generator creates original toy text/placeholders.

## Setup

Download the collection using **Code → Download ZIP**, extract it outside game,
save and mod-manager folders, and open PowerShell in
`tools\mod-asset-reference-checker`:

```powershell
py -3.12 --version
py -3.12 -B asset_references.py --help
```

Use `python` if that is your Python 3.12+ interpreter. Linux/macOS users can use
`python3`, with `/` paths and their shell's continuation syntax. No pip packages,
virtual environment, administrator rights or execution-policy changes are
required. `-B` avoids bytecode caches beside downloaded source. This guide
describes current source on `main`; older collection release archives may not
contain this utility.

## Try the generated example

Choose a new demo directory outside this repository and game folders:

```powershell
$demo = Join-Path $env:TEMP ('outlands-assets-demo-' + [guid]::NewGuid().ToString('N'))
py -3.12 -B examples\create_example.py --destination $demo
py -3.12 -B asset_references.py `
  --config-root "$demo\gamedata\configs" --entry toy.ltx `
  --asset-root "$demo\gamedata" --output "$demo\loose-report.json"
$LASTEXITCODE
```

Expect exit **2**, a complete report and three references: one `found_loose`,
one `unresolved_coverage`, and one `declared_in_selection`. The missing loose
mesh is coverage-unknown because a game could use files outside the selected
loose root, including packed assets. Its absence is not proof of a broken mod.

The generator also creates a tiny original path index:

```powershell
py -3.12 -B asset_references.py `
  --config-root "$demo\gamedata\configs" --entry toy.ltx `
  --asset-root "$demo\gamedata" --packed-index "$demo\index.json" `
  --output "$demo\indexed-report.json"
$LASTEXITCODE
```

Expect exit **0**: the absent loose file becomes `listed_in_index`. The index
asserts a name only; no archive payload is opened or verified. The generator's
`.ogf` is plain original text and is **not a valid game mesh**. An empty or
invalid-format placeholder can still be present because the tool checks file
metadata, not asset bytes or codec/engine compatibility.

Linux/macOS equivalent:

```sh
demo="${TMPDIR:-/tmp}/outlands-assets-demo-$$"
python3 -B examples/create_example.py --destination "$demo"
python3 -B asset_references.py --config-root "$demo/gamedata/configs" --entry toy.ltx --asset-root "$demo/gamedata" --output "$demo/loose-report.json"
echo "$?"
python3 -B asset_references.py --config-root "$demo/gamedata/configs" --entry toy.ltx --asset-root "$demo/gamedata" --packed-index "$demo/index.json" --output "$demo/indexed-report.json"
echo "$?"
```

The statuses are **2** then **0**. Account for the first status in scripts using
`set -e`. Existing demo/output paths are refused. Delete only your generated
demo folder with your normal file manager when finished; no automatic cleanup
is performed. See [example notes](examples/README.md).

## Select inputs explicitly

Close editors, deployment/sync programs and other writers that could change
the selected inputs. The tool does not close or lock those programs.

```powershell
py -3.12 -B asset_references.py `
  --config-root 'D:\Modding\Example\gamedata\configs' `
  --entry 'weapons\toy_weapon.ltx' --entry 'items\toy_items.ltx' `
  --asset-root 'D:\Modding\Example\gamedata' `
  --output 'D:\Reports\example-asset-references.json'
$LASTEXITCODE
```

Replace paths with your own. Entries are relative to `--config-root`, not
absolute paths. Literal `#include "relative/file.ltx"` paths resolve from the
including file's folder and must stay within the config root. A contained
include such as `../shared.ltx` is allowed; an escape is refused. Included
files are parsed once, while include occurrences remain in the context report.
Missing includes, cycles, ambiguous case, duplicate sections or duplicate keys
within a section prevent a complete check.

The config root may be inside the asset root, as in these examples. All roots,
selected files, index and output parents must be ordinary local paths; linked
ancestors, symlinks, Windows junctions/reparse points and network/device paths
are refused. Reports must be new, outside **both roots**, and separate from the
index. Parent directories must already exist. Without `--output`, JSON goes to
stdout; otherwise it is saved to the selected new file.

This uses **one loose asset root**, with an optional separate name index. It
does not model MO2's virtual filesystem, plugin priority, game archives,
mount order or an engine's search paths. Pointing it at a mod folder can help
check that mod's own files; absence may be satisfied by base-game assets or
other mods. No archives are opened, extracted, decrypted or searched.

## File rules and section references

The default file rule is `visual=meshes:.ogf`. It maps a selected direct
assignment such as `visual = toy\present` to `meshes/toy/present.ogf` beneath
the asset root. An existing matching `.ogf` suffix is retained; another explicit
suffix is unsupported. The declared subdirectory is always prefixed: a value
already starting `meshes/` would produce `meshes/meshes/...`. Choose rule/input
pairs with the intended relative layout.

This is an explicit tool mapping, not a complete implementation of an engine's
asset-resolution rules. To replace the default, repeat `--file-rule`:

```powershell
py -3.12 -B asset_references.py `
  --config-root 'D:\Modding\Example\gamedata\configs' --entry toy.ltx `
  --asset-root 'D:\Modding\Example\gamedata' `
  --file-rule 'icons_texture=textures:.dds' `
  --file-rule 'snd_draw=sounds:.ogg'
```

These examples accept only one literal path per selected file assignment.
Sound lists with commas, optional parameters, conditional expressions, dynamic
tokens and sentinel/numeric values are unsupported; they are not guessed.
Whole double quotes are supported for a file literal. Semicolons outside
quotes start comments; a semicolon inside a quoted literal remains part of the
filename. `//` comments and whole single-quoted wrappers are unsupported;
apostrophes inside a filename remain ordinary characters. Blank selected values,
including `""` for a file rule, are recorded
as informational `empty_reference` rather than fabricated paths.

The default section key is `ammo_class`, whose literal comma-separated values
are checked against section declarations in the selected graph. For example,
`ammo_class = ammo_one, ammo_two` creates two section-reference records.
Section names are case-sensitive ASCII identifiers; no inherited/effective
value is computed. Repeated `--section-key` arguments replace the default:

```powershell
py -3.12 -B asset_references.py `
  --config-root 'D:\Modding\Example\gamedata\configs' --entry toy.ltx `
  --asset-root 'D:\Modding\Example\gamedata' --section-key requires
```

Up to 64 distinct file rules and 64 distinct section keys are supported.
Duplicate/conflicting rule keys are rejected, including a key selected as both
a file and section reference. Keys are exact and case-sensitive: `Visual` is
not the default `visual`. Unconfigured keys and their values are not inspected
for references or copied into the report.

Ordinary `[section]:parent_one,parent_two` headers are recorded as declaration
context. The tool checks direct assignments it reads; it does not merge
inheritance, validate parent existence, apply overrides or calculate the game's
effective configuration. DLTX modifications and unsupported syntax make the
check incomplete. A complete result with zero selected references means no
findings under the chosen keys; it does **not** mean all config content has
been validated.

## Packed-name index and coverage

An optional index is a local UTF-8 JSON file with exactly this schema:

```json
{
  "schema_version": 1,
  "kind": "asset-path-index",
  "paths": ["meshes/toy/absent.ogf"]
}
```

Paths are portable relative paths from the same virtual asset root. The parser
rejects unsupported schemas/types, extra/duplicate JSON keys, traversal,
absolute paths and ambiguous case duplicates. The index contains names only;
it has no payload hashes or trusted proof that the named files exist, are
mounted or are compatible. An unlisted path remains coverage-unknown by default,
even when other paths appear in the index.

Only if you intend to attest that your selected loose root plus optional index
constitute all relevant asset names, use `--assume-complete-assets`. Separately,
`--assume-complete-sections` attests that the selected config graph contains all
relevant section declarations. Absences then become
`missing_in_declared_coverage`. These flags record **your assumptions**, not an
independent check that an installation or index is complete. One assumption
does not enable the other.

| Status | Meaning |
|---|---|
| `found_loose` | An ordinary loose file was observed; metadata only. |
| `listed_in_index` | The relative name appears in the supplied index; payload unverified. |
| `declared_in_selection` | The section name was declared in the selected graph. |
| `empty_reference` | A selected assignment was blank; no target guessed. |
| `unresolved_coverage` | No resolution in the selection and completeness not attested. |
| `missing_in_declared_coverage` | No resolution within coverage the caller explicitly attested. |

Loose/index file lookup is case-insensitive for portability. A match with
different case records `found_case_mismatch: true` and returns review status
**2** even if otherwise resolved. Case-colliding entries are incomplete.
Entry/include path spelling mismatches also require review and contribute to
the case-mismatch summary. Section declaration matching remains case-sensitive.

## Limits and process statuses

| Option | Default | Hard ceiling |
|---|---:|---:|
| `--max-files` | 1000 configs | 10000 |
| `--max-file-bytes` | 2097152 (2 MiB) | 16777216 (16 MiB) |
| `--max-total-bytes` | 16777216 (16 MiB) | 134217728 (128 MiB) |
| `--max-depth` | 64, with entry depth 1 | 128 |
| `--max-references` | 10000 records | 100000 |
| `--max-directory-entries` | 100000 | 1000000 |

Limits accept positive integers up to their ceilings. Index and encoded report
sizes are separately capped at **8 MiB**; retained metadata is capped at
**16 MiB**. Indexes allow up to 100000 names. Each config line is limited to
65536 decoded characters; local/relative paths are limited to 1024 characters
and 128 components. Loose target file contents are never read or hashed. Config/index
read identities/hashes and observed directory metadata are checked for changes,
but this is not an atomic snapshot or hostile-filesystem sandbox. Pause other
writers and review incomplete results.

| Exit | Meaning |
|---|---|
| `0` | Complete check with resolved or blank selected references, or no selected references. |
| `2` | Complete check requiring review: unknown coverage, absence under attested coverage or case mismatch. |
| `1` | Invalid, unsupported or incomplete check, including limits, unstable inputs or output failure. |

Check both process exit and JSON `complete`. Unsupported syntax or a read/guard
failure takes priority over review findings. Invalid command lines can fail
before JSON is available. See [REPORT-FORMAT.md](REPORT-FORMAT.md).

## Privacy, tests and suggestions

Reports omit absolute input roots, unselected values, raw exceptions and file
payloads. They **do contain** relative config/asset paths, section names, key
names, line numbers, file sizes and config/index hashes. These can identify
private content. Review every report before sharing; there is no general secret
redactor or anonymity guarantee. Hashes are not signatures or licensing proof.

Run the generated-fixture tests from this module directory:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Tests cover mapping, include/section scope, coverage uncertainty, strict indexes,
privacy, input preservation, no asset-payload reads, guards and limits. Native
link/case fixtures explicitly skip when unavailable on the platform/account.
The tests do not read installed mods or establish game/runtime compatibility.

[Bug reports](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml)
and [suggestions](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
are welcome. Include OS, Python/tool version, sanitized command, exit status and
a small original config/index pair. Review metadata before attaching a report;
do not upload actual game assets or private configurations. Read the collection's
[contributing guide](../../CONTRIBUTING.md) and [MIT license](../../LICENSE).
