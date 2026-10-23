# XML Mod Configuration Diff

Compare two explicitly selected XML files for changed attributes, parsed leaf
text, added/removed elements and reordered common children. This original MIT
utility uses Python's standard library and reports structural observations; it
does not merge, patch, validate a game's schema or establish mod compatibility.

Inputs are read only. The tool does not search installations, load game code,
resolve external documents, modify configuration, install packages, contact a
server or upload reports. An optional output is a **new** local JSON file.
Examples and tests use original toy XML, with no game or downloaded mod data.

## Runtime and setup

Use a maintained patch release of **Python 3.12+ with Expat 2.7.2 or newer**.
Python's major/minor version alone is insufficient: its bundled native XML
parser version varies by build. Check the interpreter you will actually use:

```powershell
py -3.12 --version
py -3.12 -c "from xml.parsers import expat; print(expat.EXPAT_VERSION)"
py -3.12 -B xml_diff.py --help
```

An older parser produces a controlled failure rather than parsing the inputs.
Update the interpreter used for the tool to a maintained Python build whose
version check meets the floor. No pip dependencies, virtual environment,
administrator rights or execution-policy
changes are required. The requirement follows Python's
[XML security guidance](https://docs.python.org/3/library/xml.html#xml-security)
and the [Expat runtime information](https://docs.python.org/3/library/pyexpat.html).

Download the collection using **Code → Download ZIP**, extract it outside game,
save and mod-manager folders, then open PowerShell in `tools\xml-config-diff`.
Use `python` instead of `py -3.12` if it is your verified supported interpreter.
On Linux/macOS use `python3` after checking the same parser version. `-B` avoids
bytecode caches beside downloaded source. The module's guide describes current
source on `main`; older tagged collection archives may not contain this tool.

## Try the original generated example

Choose a new demo folder outside the downloaded collection and game folders:

```powershell
$demo = Join-Path $env:TEMP ('outlands-xml-demo-' + [guid]::NewGuid().ToString('N'))
py -3.12 -B examples\create_example.py --destination $demo
py -3.12 -B xml_diff.py `
  --baseline "$demo\baseline.xml" --candidate "$demo\candidate.xml" `
  --output "$demo\comparison.json"
$LASTEXITCODE
Get-Content -LiteralPath "$demo\comparison.json"
```

Expect exit **2** and four change records: one added element, one removed
element, one changed attribute and one changed leaf text. There is one unchanged
item. The surviving common children keep their order, so no reorder is reported.
Each document has four elements; three are matched. New/removed subtree counts
describe the unmatched subtree, rather than printing its XML.

The corresponding Linux/macOS shell commands are:

```sh
demo="${TMPDIR:-/tmp}/outlands-xml-demo-$$"
python3 -B examples/create_example.py --destination "$demo"
python3 -B xml_diff.py --baseline "$demo/baseline.xml" --candidate "$demo/candidate.xml" --output "$demo/comparison.json"
echo "$?"
```

The final status is **2**, expected for deliberate differences. Account for
that status if you use `set -e` in a shell script. The generator refuses an
existing destination, linked parents and destinations inside the source tree.
Use a new report filename on repeat runs. Delete only your generated demo
directory with your normal file manager when finished; nothing auto-cleans it.
See [the example notes](examples/README.md).

## Compare two selected configuration files

Close editors, mod deployment/sync utilities and any program that might write
these files. The tool does not close or freeze other programs. Then run:

```powershell
py -3.12 -B xml_diff.py `
  --baseline 'D:\Reference\example-settings.xml' `
  --candidate 'D:\Modding\example-settings.xml' `
  --output 'D:\Reports\example-settings-diff.json'
$LASTEXITCODE
```

Replace the example paths with your own. Both inputs must be existing ordinary
local files. Input/output paths and their ancestors must not be symlinks,
Windows junctions/reparse points or network/device namespaces. The optional
report must be new, have an existing ordinary local parent, and cannot replace
either input. No output parent directories are created automatically.

JSON is written to stdout when `--output` is absent, or to the exclusive new
file when it is supplied. Input fingerprints contain byte counts and SHA-256
hashes, without filenames or absolute roots. Source consistency checks can
detect observed changes during comparison; they do not create an atomic
filesystem snapshot or lock another writer.

## How elements are matched

Elements and attributes use expanded XML namespace names. For example,
`<a:item xmlns:a="urn:toy">` and `<b:item xmlns:b="urn:toy">` have the same
name `{urn:toy}item`; changing the namespace URI is a change. Attribute order
and namespace-prefix spelling are ignored.

Sibling identities use the expanded element tag and the **first present**
configured key attribute. Defaults, in order, are `id`, `Id`, `ID`, `name`,
`Name`, `Label`. Attribute names and values are case-sensitive. The selected
key attribute's name is part of the identity; `id="a"` and `name="a"` are
different identities. Duplicate sibling identities make the operation
incomplete, including inside an added/removed subtree.

To replace the defaults, repeat `--key-attribute` in your desired precedence:

```powershell
py -3.12 -B xml_diff.py `
  --baseline 'D:\Reference\toy.xml' --candidate 'D:\Modding\toy.xml' `
  --key-attribute Code --key-attribute '{urn:toy}Code'
```

The second argument demonstrates Clark notation for a namespaced attribute.
A prefix such as `toy:Code` does not select a namespace URI. Custom keys replace
the defaults; an element with only `id` is unkeyed under this custom policy.
Names use a plain ASCII XML local name, or a nonblank namespace URI in braces
followed by an ASCII local name. Up to 64 distinct custom keys are accepted;
repeated identical arguments preserve their first position. Each key argument
is limited to 4096 UTF-8 bytes.

An unkeyed tag occurring only once among a parent's unkeyed children can be
matched by tag. Ambiguous repeated unkeyed siblings with the same tag are
refused by default. If you explicitly intend positional comparison, opt in:

```powershell
py -3.12 -B xml_diff.py `
  --baseline 'D:\Reference\toy.xml' --candidate 'D:\Modding\toy.xml' `
  --unkeyed ordinal
```

Ordinal matching uses same-tag sibling occurrence, including keyed siblings
of that tag. Inserting/reordering an unkeyed element can therefore cause a
series of positional changes. It is an explicit matching policy, not a claim
that the game identifies those elements the same way.

Added/removed elements are reported once for each unmatched subtree root, with
`subtree_elements` describing its size. Root/tag changes are removal plus
addition; no rename heuristic is applied. A change to a selected key usually
creates a removed/added identity rather than an attribute change on a matched
child. Document roots pair by expanded tag without key matching; a changed key
attribute on a same-tag root is an ordinary attribute change. Reordering is reported when the sequence of **common matched child
identities** changes. Insertion alone does not count as reordering, and reorder
records do not invent leaf/attribute changes for otherwise matched children.

## Supported text and parsing scope

Leaf text is compared exactly **after XML parsing**, including whitespace.
XML parser normalization still applies, and CDATA/character references can
produce identical parsed text. Whitespace between child elements is ignored.
Comments and processing instructions are ignored.

Nonwhitespace mixed text plus child elements is unsupported and makes the
comparison incomplete. This prevents a report silently dropping meaningful
head/tail text. The tool is a narrow configuration-tree comparator, not an XML
editor, general-purpose text diff, canonicalization service or XML schema/DTD
validator. It rejects DOCTYPE/entity/external-document declarations. It does
not fetch or expand referenced documents. These guards and resource limits
reduce parser risk; they do not sandbox the native parser or promise hostile
input isolation.

Inputs must be **UTF-8 XML 1.0**, with an optional UTF-8 BOM. Other encodings,
NUL bytes, XML 1.1, XInclude elements and `xml:space` values other than `default`
are refused. Built-in/numeric character references use normal XML parsing;
external/custom entity declarations are not permitted. XML 1.0 newline and
attribute-value normalization still applies, so differing source hashes can
produce an equal structural comparison.

## Privacy and value disclosure

By default, changed text/attribute values and unmatched element key identities
are represented by character counts and SHA-256 fingerprints. Paths use
expanded tag names plus structural sibling occurrences, with no raw key values.
Neither full source XML nor added/removed subtree payloads are embedded.

For a local inspection where you intend to disclose changed values explicitly:

```powershell
py -3.12 -B xml_diff.py `
  --baseline 'D:\Reference\toy.xml' --candidate 'D:\Modding\toy.xml' `
  --include-values --output 'D:\Reports\toy-with-values.json'
```

`--include-values` adds raw parsed values to the emitted value/identity
descriptors; it does not turn unmatched subtrees into a full XML patch. Review
these reports carefully before sharing. Even default reports contain tag and
attribute names, namespace URIs, counts and hashes that can reveal private
information. Hashes of guessable values can be matched against guesses.
Fingerprinting is not anonymization, secret detection or a signature. A match
does not prove ownership, licensing, game compatibility or authenticity.

## Limits and exits

Limits apply independently to each parsed input, except change/report limits:

| Option | Default | Hard ceiling |
|---|---:|---:|
| `--max-bytes` | 2097152 (2 MiB) | 16777216 (16 MiB) per file |
| `--max-depth` | 64 | 128, with the document root at depth 1 |
| `--max-elements` | 10000 | 100000 per file |
| `--max-attributes` | 50000 | 200000 per file |
| `--max-changes` | 10000 | 100000 records |

Each option accepts a positive integer up to its hard ceiling. Encoded JSON
reports have an additional fixed **8 MiB** cap. Retained expanded names,
attributes and text also have a fixed **8 MiB per-input** budget. A limit, unsafe input, malformed
XML, unsupported parser/mixed content, ambiguous identity, observed source
change or output failure prevents a complete result. A partial list of changes
must not be interpreted as an exhaustive diff.

| Exit | Meaning |
|---|---|
| `0` | Complete comparison with no observed differences under the recorded policy. |
| `2` | Complete comparison with at least one structural/text/attribute/order change. |
| `1` | Invalid, unsupported or incomplete comparison, including output failure. |

Check both process status and JSON `complete`; invalid command lines can fail
before JSON exists. The [report reference](REPORT-FORMAT.md) documents exact
fields and the distinction between change-record and subtree counts.

## Tests and suggestions

From this module directory, using your verified supported interpreter:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

The suite requires an actual supported Expat runtime and fails clearly rather
than silently skipping parser tests. Tests use original generated XML and cover
matching, namespaces, additions/removals, order, exact leaf text, fingerprints,
malformed/declaration inputs, limits, output guards and source preservation.
Native link fixtures explicitly skip when the platform/account cannot create
them. These are source-level tests, not game or mod-pack testing.

[Bug reports](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml)
and [suggestions](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
are welcome. Include OS, Python/Expat/tool version, sanitized command, exit
status and a small original XML pair. Review report metadata and opt-in values
before attaching them; do not upload actual game files or private configuration.
Useful contributions include safer edge cases, matching-policy clarity and
original regression fixtures. See [CONTRIBUTING.md](../../CONTRIBUTING.md) and
the [MIT license](../../LICENSE).
