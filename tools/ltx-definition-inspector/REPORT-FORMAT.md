# LTX Definition Inspector report format

Schema version `1` is JSON. Paths use `/` and are relative to the selected
root. Line numbers are one-based. Identifiers are lowercase ASCII. Arrays of
parents preserve declaration order; no inherited values are calculated.

| Field | Meaning |
| --- | --- |
| `schema_version`, `tool`, `version` | Format version, tool identifier, release version. |
| `complete` | Whether the selected supported inspection finished without an incomplete condition. |
| `encoding` | Explicit decoding choice: `utf-8` or `cp1251`; a UTF-8 BOM is recognized. |
| `limits` | Applied `max_file_bytes`, `max_total_bytes`, `max_files`, `max_depth`, `max_records`, `max_report_bytes`, and fixed `directory_entries_per_lookup` budgets. |
| `entries` | Validated root-relative entry filenames. Empty if initial validation failed. |
| `files` | Successfully read/decoded files, each with `file` and raw `bytes`. A partially parsed file can still appear here. |
| `includes` | Supported directives encountered before a file's first unsupported line: `file`, `line`, normalized relative `target`. The target need not have loaded successfully. |
| `definitions` | Explicit declarations: `file`, `line`, `section`, and ordered `parents`. |
| `findings` | Review items described below. Their presence does not override incomplete status. |
| `errors` | Incomplete conditions: stable `code`, and relative `file`/`line` where available. No raw exception text. |
| `summary` | Counts: `files_read`, `bytes_read`, `definitions`, `unique_sections`, `includes`, `findings`, `errors`. |
| `exit_code` | `0` complete/clean, `2` complete/findings, or `1` incomplete. |

`files_read` counts files accepted for decoding/parsing, not failed attempts;
`bytes_read` counts their bytes. Limits can reject a file before reading it.
There are no timestamps, input hashes, values, comments, or absolute roots.

## Findings

| Code | Fields and interpretation |
| --- | --- |
| `MISSING_PARENT` | `section`, `parent`, `file`, `line`: no declaration of that parent in the selected graph. It may exist in omitted context. |
| `DUPLICATE_SECTION` | `section`, `locations` (`file`, `line`): multiple explicit declarations; no effective winner is chosen. |
| `REPEATED_INCLUDE` | `file`, `references`: that target has more than one recorded incoming include occurrence. Each file is still parsed once. |
| `INHERITANCE_CYCLE` | `sections`: example closed path in the union of declared parent edges, including duplicate declarations. |
| `INCLUDE_CYCLE` | `files`: example closed include path. Also emits `INCLUDE_GRAPH_INCOMPLETE` in errors and forces exit `1`. |

The cycle arrays repeat the starting node at the end. They show DFS back-edge
cycles, not an exhaustive enumeration. Missing includes appear in `errors` as
`MISSING_FILE`, with the safe normalized target in `file`.

## Incomplete/error codes

- Input/path checks: `UNSAFE_PATH`, `UNSUPPORTED_FILE_TYPE`, `DUPLICATE_ENTRY`,
  `LINK_OR_REPARSE_POINT`, `CASE_AMBIGUITY`, `CASE_MISMATCH`, `MISSING_FILE`,
  `NOT_A_DIRECTORY`, `NOT_A_REGULAR_FILE`, `INPUT_UNAVAILABLE`, `READ_ERROR`,
  `SOURCE_CHANGED`.
- Language/encoding: `ENCODING_ERROR`, `UNSUPPORTED_CONTROL_CHARACTER`,
  `UNSUPPORTED_DIRECTIVE`, `UNSUPPORTED_SECTION_SYNTAX`, `UNSUPPORTED_CONTENT`,
  `UNSUPPORTED_QUOTING`, `UNSUPPORTED_MULTILINE_OR_QUOTING`.
- Scope/limits: `NO_DEFINITIONS`, `INCLUDE_GRAPH_INCOMPLETE`, `FILE_BYTE_LIMIT`,
  `TOTAL_BYTE_LIMIT`, `FILE_COUNT_LIMIT`, `INCLUDE_DEPTH_LIMIT`.
  Structural/cycle expansion is also bounded by `RECORD_COUNT_LIMIT` and
  `CYCLE_REPORT_LIMIT`.
  A streamed directory case lookup exceeding 100,000 entries produces
  `DIRECTORY_ENTRY_LIMIT`, including for an output-parent lookup.

If serialized graph JSON exceeds `max_report_bytes`, a small incomplete
report replaces it with empty result arrays and `REPORT_BYTE_LIMIT`. Its
summary counts describe those empty arrays; no partial graph survives this
fallback. The small fallback may exceed an extremely tiny user-selected byte
limit. Cycle witnesses also share a fixed estimated JSON character budget of
4 MiB per graph so long repeated identifiers cannot expand without bound.

The first unsupported line stops further parsing of that file. Already
recorded declarations and supported includes remain partial evidence. Other
files can still be inspected; their findings must be interpreted alongside
`complete: false`.

Destination failures print a short code to stderr and return exit `1` without
writing/overwriting the report: `OUTPUT_INSIDE_INPUT_ROOT`, `OUTPUT_EXISTS`,
`OUTPUT_UNAVAILABLE`, or a shared path-check code. A general I/O failure can
print `IO_ERROR`. Invalid CLI arguments print usage and `INVALID_ARGUMENTS`,
then exit `1` with no JSON.
Consumers should require valid JSON and check `complete`/`exit_code`.

## Small example

For an original file `main.ltx` containing only `[child]: absent`, the relevant
portion of the report is:

```json
{
  "schema_version": 1,
  "complete": true,
  "definitions": [
    {"file": "main.ltx", "line": 1, "section": "child", "parents": ["absent"]}
  ],
  "findings": [
    {"code": "MISSING_PARENT", "section": "child", "parent": "absent", "file": "main.ltx", "line": 1}
  ],
  "errors": [],
  "exit_code": 2
}
```

This excerpt omits other top-level fields for readability. A real report
includes every field in the first table. Relative paths and identifiers may
still be sensitive; review reports before sharing them.
