# Dependency rule report, schema 1

UTF-8 JSON with ASCII escapes. Exits: 0 complete/no review, 2 complete/review,
1 incomplete/failure. `--help`/`--version` produce plain text. Reports include
logical mod names and rules, but no selected-file paths or raw exception text.

| Field | Meaning |
|---|---|
| `schema_version`, `kind`, `tool_version` | 1, `offline-mod-dependency-rule-checker`, 1.0.0 |
| `complete` | Both files fully validated, direct rules and catalog cycles checked within limits |
| `review_required` | Any direct finding or catalog cycle; null when incomplete |
| `policy` | Casefold/no normalization, explicit active earliest-to-latest inventory, separate catalog graph cycles, no implied order or compatibility certification |
| `limits` | Fixed byte, count, JSON-depth, graph-node, accounting and report ceilings |
| `inventory` | Actual `bytes`, raw-file `sha256`, original `load_order`; null on incomplete |
| `rule_catalog` | Actual `bytes`, raw-file `sha256`, original `rules`; null on incomplete |
| `evaluations` | One result per rule, in authored array order |
| `findings` | Direct failing rule references, in authored order |
| `catalog_cycles` | Cyclic strongly connected groups, described below |
| `summary` | Active-mod/rule counts, per-result counts, per-type catalog cycle counts |
| `errors` | Sanitized codes; optionally `input` role and 1-based `rule` array index |

Each evaluation repeats the original rule fields and adds `mod_position`,
`target_position` (1-based, null for absent), and `result`:

| Result | Meaning |
|---|---|
| `satisfied` | Applicable requirement or order assertion passes |
| `not_applicable` | Requires source absent, or either conflict/order endpoint absent |
| `missing_requirement` | Active source requires absent target |
| `active_conflict` | Both names in a symmetric conflict are active |
| `load_order_violation` | Both active; source position is equal to or later than target |

A non-active conflict is not applicable, not satisfied. Each failing direct
evaluation adds `{rule_id, code}` to `findings`. These codes are observations
under authored assertions, not an automatically verified compatibility claim.

## Catalog cycles

Requirements and load-before edges form **separate** directed graphs over all
catalog endpoints, active or inactive. One object is returned per cyclic
strongly connected component (SCC), including self loops. An SCC is a set whose
names are mutually reachable, not a list of every possible simple cycle.

- `type`: `requires` or `load_before`.
- `members`: all component names, sorted by their normalized comparison keys.
- `active_members`: members present in the selected inventory, in member order.
- `rule_ids`: all edges internal to the component, sorted by literal rule ID.
- `witness`: `mods` forming one closed walk (first equals last) and `rule_ids`
  for each successive edge; the two arrays differ in length by one.

Component display spelling uses inventory spelling when present, otherwise the
first occurrence in the rule catalog. Witness choice is deterministic for the
same inputs. Components are ordered by type (`requires`, then `load_before`),
then their sorted comparison-key sequences. No all-pairs or all-cycles expansion
is performed. Iterative graph traversal avoids Python recursion-depth limits.

Catalog cycles request review even when none of their names are active. An
advisory requirement cycle can be a valid co-required set; an order cycle cannot
be satisfied when all its members must be ordered together. `active_members` is
a presence list only, not active-cycle analysis. A witness can include inactive
names; a partially active component can still contain a smaller active cycle.
The report does not certify global consistency of combined presence/conflict
assertions, solve alternatives or rewrite load order.

## Incomplete results and bounds

Failure clears both input inventories, all evaluations/findings/cycles and the
summary. `complete` is false; `review_required` is null. It exits 1. No partial
rule evaluation is labeled valid. Report/output failure falls back to small
incomplete JSON on stdout when possible. Error codes:

| Category | Codes |
|---|---|
| JSON/schema | `unsupported_encoding`, `invalid_json`, `invalid_json_number`, `duplicate_json_key`, `invalid_or_unknown_fields`, `unsupported_schema_version`, `invalid_load_order`, `invalid_rule_list` |
| Names/rules | `invalid_mod_name`, `duplicate_or_case_colliding_mod`, `invalid_rule_id`, `duplicate_rule_id`, `unsupported_rule_type`, `duplicate_rule_relation` |
| Resources/analysis | `file_byte_limit`, `json_depth_limit`, `mod_count_limit`, `rule_count_limit`, `graph_node_limit`, `metadata_byte_limit`, `report_byte_limit`, `graph_analysis_failed` |
| Paths/arguments | `invalid_arguments`, `invalid_local_path`, `local_path_limit`, `unsafe_local_name`, `linked_path`, `invalid_parent`, `unreadable_or_missing_path`, `not_a_regular_file` |
| Output/stability | `invalid_output_parent`, `output_overlaps_input`, `output_exists`, `unsafe_output`, `input_changed`, `output_write_failed`, `operation_failed` |

Hard ceilings: 2 MiB per input; JSON container nesting 8; 10,000 active names;
10,000 rules; 20,000 distinct endpoint names across the catalog; 32 MiB cumulative
serialized-metadata-plus-overhead accounting; 8 MiB final encoded report.
Accounting is not exact process resident memory. Rule, node and report bounds
can interact, and graph names may also be absent from the active inventory.
The JSON encoder checks its limit before output creation. SHA-256 identifies
input bytes without authenticating a publisher, rule accuracy or an installation.
