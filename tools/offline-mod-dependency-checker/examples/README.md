# Fictional offline rule examples

From the repository root on Windows; use `python3` on Linux/macOS:

```powershell
py -3.12 -B tools/offline-mod-dependency-checker/examples/create_example.py --destination ../outlands-dependency-demo
py -3.12 -B tools/offline-mod-dependency-checker/dependency_checker.py --inventory ../outlands-dependency-demo/inventory-clean.json --rules ../outlands-dependency-demo/rules-clean.json
py -3.12 -B tools/offline-mod-dependency-checker/dependency_checker.py --inventory ../outlands-dependency-demo/inventory-review.json --rules ../outlands-dependency-demo/rules-review.json --output ../outlands-dependency-demo/review-report.json
```

The new destination contains four original tiny JSON files. The generator refuses
an existing destination, and reports require a fresh output filename.

Clean inventory: `Core, Addon, Patch`, earliest to latest. The authored rules
require Core for Addon and Addon for Patch, prohibit Patch with Alternative, and
order Core before Addon before Patch. Expected exit **0**: four satisfied rules,
one not-applicable conflict and no cycle groups.

Review inventory: `Patch, Addon, Alternative`. Its catalog adds a reverse
requirement between Addon/Patch and a two-way order rule for inactive Unused A/B.
Expected exit **2**, with these observations:

| Rule/group | Expected result |
|---|---|
| `addon-needs-core` | `missing_requirement`: Addon active, Core absent |
| `patch-needs-addon` | `satisfied` |
| `alternative-conflict` | `active_conflict`: Patch and Alternative active |
| `core-before-addon` | `not_applicable`: Core absent |
| `addon-before-patch` | `load_order_violation`: Addon is later than Patch |
| `addon-needs-patch` | `satisfied` |
| `unused-a-before-b`, `unused-b-before-a` | Directly `not_applicable`; catalog order cycle requests review |
| Addon/Patch requirement cycle | Advisory cycle with both members active; no missing requirement inside this pair |

The two cycle groups are distinct from the three direct findings. A dependency
cycle alone is not proof of incompatibility, and inactive catalog cycles still
request review by policy. Rule coverage/accuracy is the author's responsibility.
The checker reads JSON only; it does not inspect or modify a game installation.
See [rule format](../RULES-FORMAT.md), [report format](../REPORT-FORMAT.md) and
[the tool guide](../README.md).
