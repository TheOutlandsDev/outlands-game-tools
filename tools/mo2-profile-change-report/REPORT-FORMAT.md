# Profile change report format, schema 1

UTF-8 JSON with ASCII escapes. Fixed input roles are `before` and `after`; local
filenames and raw comment text are omitted. Names remain visible. Exit 0 means
complete/no semantic differences, 2 complete/changes, 1 incomplete/failure.

| Field | Meaning |
|---|---|
| `schema_version`, `kind`, `tool_version` | 1, `mo2-profile-change-report`, 1.0.0 |
| `complete` | Both supported files fully parsed and compared within limits |
| `policy` | UTF-8/BOM, casefold without normalization, physical file order, common inversion participants, separator relocation policy, no load-order inference |
| `limits` | Fixed per-file, per-line, line-count, entry, accounting and report ceilings |
| `before`, `after` | Parsed input inventories; null on incomplete |
| `input_bytes_equal` | Raw SHA-256 equality; null on incomplete |
| `semantic_changes` | Whether any change list is nonempty; null on incomplete |
| `changes` | Three groups of change lists, detailed below |
| `summary` | Per-group/per-list counts; empty object on incomplete |
| `errors` | Sanitized error code objects, optionally input role and 1-based line |

Each inventory contains actual `bytes`, raw-file `sha256`, initial UTF-8 `bom`
boolean, `entries` in physical file order, and `counts` for the three groups.
An entry contains `name`, `group`, literal `marker`, `enabled` (boolean only for
regular mods, otherwise null), physical `line` and entry-only `position`.
Both positions are 1-based. Comments/blank lines count toward `line` only.

## Changes and order

Groups are `mods`, `separators`, `foreign`. Each has:

- `added`, `removed`: entry objects from the relevant input, in that input's order.
- `name_spelling_changed`: `{before, after}` entry pairs sharing a casefold key
  but a different literal name. No broader rename inference.
- `reordered`: entry pairs plus `before_common_rank`, `after_common_rank` and
  `crossed_with` (the after-side name of one shared entry whose relative order
  reverses). Only entries shared within that group are ranked, starting at 1.

The `mods` group also has `enabled` and `disabled` entry pairs. New enabled mods
appear only in `added`; existing shared mods toggled from minus to plus appear
in `enabled`. The `separators` group additionally has `marker_changed` entry
pairs and `relocated` pairs with the same rank/witness fields as reordered, but
ranked across **all shared entries whose groups stayed the same**.

All inversion participants are reported, not a presumed minimum move set. Example:
`A,B,C` → `C,B,A` reports all three; B keeps rank 2 yet crosses A and C. If a new
entry is inserted into `A,B` → `New,A,B`, neither A nor B is reordered. Moving one
separator across A can relocate the separator without reordering A among mods.
`crossed_with` is a witness, not an exhaustive list of reversed pairs.

Removing/adding entries, changing enablement and changing spelling may overlap
with order observations. A group change is removal plus addition and is excluded
from common stable-entry order comparisons. Group/list counts are not a unique
total of changed names. Comments/encoding presentation differences may give
`input_bytes_equal: false` with `semantic_changes: false` and exit 0.

## Incomplete results and errors

On failure, inventories are null, all change lists are empty, `summary` is empty
and `complete` is false. No partial comparison is presented as valid. Error codes:

| Category | Codes |
|---|---|
| Parsing | `unsupported_encoding`, `invalid_modlist_text`, `unsupported_modlist_entry`, `unsafe_mod_name`, `duplicate_or_case_colliding_name`, `foreign_separator_ambiguous` |
| Resources | `file_byte_limit`, `line_length_limit`, `line_count_limit`, `entry_count_limit`, `metadata_byte_limit`, `report_byte_limit` |
| Arguments/paths | `invalid_arguments`, `invalid_local_path`, `local_path_limit`, `unsafe_local_name`, `linked_path`, `invalid_parent`, `unreadable_or_missing_path`, `not_a_regular_file` |
| Output/stability | `invalid_output_parent`, `output_overlaps_input`, `output_exists`, `unsafe_output`, `input_changed`, `output_write_failed`, `operation_failed` |

Limits: 2 MiB per file; 2,048 characters per line; 50,000 split lines; 10,000
entries per input; 32 MiB cumulative metadata accounting; 8 MiB final JSON.
Accounting charges serialized entries, keys and change records plus overhead,
not exact resident memory. The final encoder checks its byte ceiling before an
output is created. Report/output failure produces a small incomplete JSON report
on stdout when possible. Native operating-system exception text is not exported.
Hashes identify selected bytes, without authenticating files or installations.
