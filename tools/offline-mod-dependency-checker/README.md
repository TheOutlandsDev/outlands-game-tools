# Offline Mod Dependency Rule Checker

Check an explicit active mod list against your own **requires**, **conflicts** and
**load before** rules. Report missing requirements, active conflicts, order
violations and cycle groups, with rule IDs that explain where each observation
came from. This is an offline checker for authored assertions, not an automatic
mod compatibility database.

Original source, tests and fictional examples use the root [MIT license](../../LICENSE).
Python **3.12+**, standard library only. No game, mod manager, account, service
or additional Python package is required. No game/mod files are bundled.

## Quick start

Download current **main** through GitHub **Code → Download ZIP**, or clone the
[collection](https://github.com/TheOutlandsDev/outlands-game-tools). This tool was
added after the historical v0.1.0 release assets. From the repository root on
Windows:

```powershell
py -3.12 -B tools/offline-mod-dependency-checker/examples/create_example.py --destination ../outlands-dependency-demo
py -3.12 -B tools/offline-mod-dependency-checker/dependency_checker.py --inventory ../outlands-dependency-demo/inventory-clean.json --rules ../outlands-dependency-demo/rules-clean.json
py -3.12 -B tools/offline-mod-dependency-checker/dependency_checker.py --inventory ../outlands-dependency-demo/inventory-review.json --rules ../outlands-dependency-demo/rules-review.json --output ../outlands-dependency-demo/review-report.json
$LASTEXITCODE
```

On Linux/macOS replace `py -3.12` with `python3`. The generator requires a new
destination whose parent already exists. Clean example exit: **0**. Review
example exit: **2**, with a missing requirement, conflict, order violation,
dependency cycle and an inactive catalog order cycle. See the
[worked examples](examples/README.md).

## Write an inventory and rules

The first input is a small JSON document listing **active** logical mod names,
from **earliest to latest in the order you want checked**:

```json
{
  "schema_version": 1,
  "load_order": ["Core", "Addon", "Patch"]
}
```

The second input is your rule catalog:

```json
{
  "schema_version": 1,
  "rules": [
    {"id": "addon-needs-core", "type": "requires", "mod": "Addon", "target": "Core"},
    {"id": "patch-conflict", "type": "conflicts", "mod": "Patch", "target": "Alternative"},
    {"id": "core-first", "type": "load_before", "mod": "Core", "target": "Addon"}
  ]
}
```

Save these as, for example, `inventory.json` and `rules.json`. Then run:

```powershell
py -3.12 -B tools/offline-mod-dependency-checker/dependency_checker.py --inventory 'D:/ModChecks/inventory.json' --rules 'D:/ModChecks/rules.json' --output 'D:/Reports/new-dependency-report.json'
```

Use ordinary local files and a new output path with an existing ordinary parent
directory. Reports are exclusive: existing files and either input are never
overwritten. Without `--output`, JSON goes to standard output. Inputs are read
as data; names do not execute expressions, commands, imports or callbacks.
The tool does not launch, install, download, reorder or repair anything.

The [rule format guide](RULES-FORMAT.md) defines exact fields, validation,
direction and self-rule behavior. The [report guide](REPORT-FORMAT.md) defines
results, cycles, limits and error codes.

## Interpret the rules

| Rule | Checked condition |
|---|---|
| `requires` A → B | If A is active, B must also be active. Presence only; no implied ordering. |
| `conflicts` A → B | A and B must not both be active. Symmetric regardless of how the pair was written. |
| `load_before` A → B | When both are active, A's supplied position must be earlier than B's. Does not require either to be active. |

Rules with an inactive source are not applicable for `requires`. Conflict/order
rules are not applicable when either endpoint is absent. Every rule receives an
evaluation, including not-applicable rules. Requirements are direct assertions:
if A requires absent B and B requires C, the report flags missing B for active A;
it does not pretend absent B is active or invent a transitive requirement for A.
If B is active, its own rule for C is checked normally.

Names match with Python Unicode **casefold**, without Unicode normalization.
Inventory names that collide under this policy are refused. Duplicate rule IDs,
duplicate typed relations and reversed duplicates of a symmetric conflict are
also refused. Rules are not merged silently. This matching policy does not
reproduce every game engine, filesystem or mod manager.

### Cycles need context

The checker analyzes **the whole rule catalog**, including inactive names, in
two separate directed graphs: requirements and load-before constraints. It does
not mix them into a single graph. Each cyclic strongly connected group is
reported once, with all internal rule IDs and one concrete closed-loop witness.
This bounds output instead of enumerating every possible cycle.

A requirement cycle may describe a valid co-required set; it is an **advisory
review observation**, not proof that the mods are incompatible. An order cycle
cannot be satisfied if all its members must be ordered simultaneously. An
inactive catalog cycle still requests review; `active_members` shows which names
are currently selected. That list describes presence only. A partly active
component may contain a smaller active cycle; the tool does not separately
enumerate active-only components. The witness may include inactive names.

No automatic removal, dependency resolution, topological rewrite or guessed
load order is produced. Contradictory presence/conflict assertions are evaluated
individually; this is not a SAT solver or a global consistency proof.

## Exits, coverage and privacy

| Exit | Meaning |
|---|---|
| 0 | Complete supported check with no direct findings and no catalog cycle groups |
| 2 | Complete supported check with direct findings or catalog cycles to review |
| 1 | Incomplete, invalid, unsupported, limited or failed operation |

`--help` and `--version` are successful informational exits with plain text.
For automated use inspect both the exit code and `complete`. An incomplete
report discards inventories, evaluations, findings and cycles. A report/output
failure falls back to small incomplete JSON on stdout when possible.

**A clean report only means the supplied assertions passed.** Rule accuracy and
coverage are the author's responsibility. Empty rules are allowed and explicitly
report zero rules. There is no built-in database, online lookup, version-range
evaluation, optional/alternative dependency expression, archive/file inspection,
game launch or multiplayer/save compatibility test.

Inventory order is explicitly supplied. This version does **not** import MO2
`modlist.txt`, `plugins.txt` or another manager's export directly. In particular,
MO2's saved physical order is not automatically the earliest-to-latest order
your rule author intends. Translate names/order deliberately into the JSON
inventory and include only entries you consider active. For saved-profile changes
use [MO2 Profile Change Report](../mo2-profile-change-report/README.md).

Absolute selected-file paths are omitted, but reports include mod names, rule
IDs, rule contents and input hashes. These can be private. Review before sharing.
The checker makes no network requests or telemetry uploads. Symlink/reparse
ancestors, UNC, device/stream and drive-relative paths are refused. Input identity,
size and timestamp checks detect ordinary concurrent changes; they are not an
atomic snapshot against a hostile writer. Use stable local files.

Hard limits: 2 MiB per JSON file, JSON container nesting depth 8, 10,000 active
mods, 10,000 rules, 20,000 distinct catalog endpoint names, 32 MiB cumulative
serialized-metadata-plus-overhead accounting and an 8 MiB report. Accounting is
not a process resident-memory guarantee. One limit can be reached before another;
maximum counts do not promise that every combination fits the final report.
Graph traversal is iterative, so long dependency chains do not rely on Python's
recursion depth.

## Test and leave suggestions

```powershell
py -3.12 -B -m unittest discover -s tools/offline-mod-dependency-checker/tests -v
```

Tests use original synthetic JSON only. An independent reachability oracle
checks all 512 directed graphs on three names, including self edges, and verifies
each cycle witness against its authored rules. Additional tests cover direct
evaluation, graph separation, long chains, duplicate/unknown fields, encodings,
JSON depth, resource limits, guarded output and input preservation. CI runs
Windows/Linux on Python 3.12/3.13, declaring unavailable native link fixtures.
See [validation](../../VALIDATION.md).

[Suggest a feature](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_request.yml)
or [report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml).
Suggestions and questions are welcome without a code contribution. Select this
tool in the bug form; include OS/Python/tool versions, the relevant rule IDs,
expected versus actual results, exit/error codes and a minimal fictional
inventory/rule pair. Replace private names and paths. Useful requests include
clearer cycle explanations, manager-specific importers and separately specified
version/alternative rule formats. Do not attach saves or somebody else's assets.
See [contributing](../../CONTRIBUTING.md).

Original collection filesystem/report patterns informed the guards. JSON handling
was checked against [Python 3.12 documentation](https://docs.python.org/3.12/library/json.html).
No third-party parser, compatibility database, game code or separate AGPL launcher
implementation is bundled.
