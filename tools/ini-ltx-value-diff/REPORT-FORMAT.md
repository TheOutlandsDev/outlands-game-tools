# JSON report format

Schema version **1**, kind `ini-ltx-configuration-value-diff`, tool version
**1.0.0**. The report describes the supported parsed literal maps under the
recorded policies, not effective game settings. See the [guide](README.md).

| Field | Meaning |
|---|---|
| `schema_version`, `kind`, `tool_version` | Format and producer identifiers. |
| `complete` | Both files parsed and comparison/stability checks completed. Output failure still takes precedence via exit status. |
| `policy` | `dialect`, `case`, `duplicate_keys`, resolved `inline_comments`, `before_encoding`, `after_encoding`, `include_values`. |
| `limits` | Effective `max_file_bytes`, `max_lines`, `max_records`, `max_changes`. Fixed ceilings are additional. |
| `inputs` | `before`/`after` metadata or `null` where unavailable. |
| `summary` | Change and unchanged-key counts. |
| `section_changes` | Added/removed sections and changed ordered LTX parent lists. |
| `value_changes` | Added/removed/changed selected map entries. |
| `errors` | Controlled `{code}` records, with optional `side` and one-based `line` when known. |

## Inputs and summary

Each available input record contains `bytes`, `sha256`, `sections`, `keys` and
`duplicate_assignments`. The hash covers exact original bytes, including BOM,
comments and line endings. Section/key counts describe unique parsed entries;
globals are keys with no named section. Duplicate counts record assignments
discarded under the explicit `last` policy. No absolute paths or input filenames
are exported. Input hashes and duplicate counts are informational, not extra
change categories.

The summary contains `sections_added`, `sections_removed`, `parents_changed`,
`keys_added`, `keys_removed`, `keys_changed`, `keys_unchanged`. Keys in added or
removed sections produce their own key rows as well as a section row. An empty
added section therefore changes `sections_added` even with zero key changes.
Unchanged key counts cover common entries whose parsed literal strings match;
they do not include unmaterialized inherited/default values.

## Section changes

Each row is `{kind, section, before, after}`. `kind` is `added`, `removed` or
`parents_changed`. Each non-null side contains `{line, parents}`; `parents` is
an ordered list, empty for ordinary INI or parentless LTX sections. Absent sides
are `null`. Parent order and spelling under the selected case policy matter;
parent existence, cycles and effective values are never evaluated.

## Value changes

Each row is `{kind, section, key, before, after}`. `kind` is `added`, `removed`
or `changed`. `section: null` identifies INI global assignments and cannot collide
with a section literally named `null`. Section and key are separate identifiers,
not one flattened dotted locator. Insensitive mode reports their lowercase forms.

Each non-null side contains:

```json
{"line": 2, "characters": 3, "sha256": "cba06b5736faf67e54b07b561eae94395e774c517a7d910a54369e1263ccfbd4"}
```

That example fingerprints the parsed literal `old`. `characters` counts Python
Unicode code points; `sha256` hashes the UTF-8 encoding of the parsed literal,
after the documented edge/comment policy. It does not hash the original RHS byte
slice or coerce/unquote values. A present empty string has length zero and the
SHA-256 of empty bytes; it differs from a `null` side (absent key).

Only `--include-values` adds a `value` string to each non-null value descriptor.
It includes literal quote spelling and preserved whitespace. Unchanged values
are counted but not emitted. Source locations refer to original physical lines;
the final assignment's line is used with duplicate policy `last`.

## Ordering, errors and sharing

Section changes are sorted by normalized section name. Value changes sort globals
first, then by section and key. Order of source declarations and line-only changes
do not create difference rows. Empty supported files are valid comparisons.

Exit `0` means complete/no differences; `2` means complete/differences; `1` means
incomplete/invalid/output failure. Unsupported syntax or a limit clears all diff
arrays and summary counts. `complete: false` with zero differences does not prove
equality. A failed output may instead emit a small incomplete JSON report to
stdout; inspect the exit status and both streams. CLI errors can precede input
metadata. Error records contain no source text or native exception messages.

Examples of controlled codes include `duplicate_key`, `duplicate_section`,
`unsupported_directive`, `unsupported_assignment`, `unsupported_header`,
`global_assignment_not_supported`, `unsupported_identifier`,
`unbalanced_double_quote`, `unsupported_control_character`,
`unsupported_encoding`, `utf16_bom_required`, `input_byte_limit`,
`line_count_limit`, `line_character_limit`, `record_count_limit`,
`parent_count_limit`, `metadata_byte_limit`, `change_count_limit`,
`report_byte_limit`, `input_changed`, `output_exists` and `output_write_failed`.
Other path/argument failures use controlled codes too; consumers must tolerate
unknown error codes and optional location fields.

Metadata and fingerprints can reveal private content even when values are hidden.
Review reports before sharing. Hashes do not anonymize small values, authenticate
sources, establish authorship or grant redistribution rights over inspected files.
