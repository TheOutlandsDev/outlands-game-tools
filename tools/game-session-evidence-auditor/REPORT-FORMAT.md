# Session audit report format, schema 1

UTF-8 JSON with ASCII escapes. Exits: 0 complete/no findings; 2 complete/findings;
1 incomplete/failure. Informational `--help`/`--version` use plain text.

| Field | Meaning |
|---|---|
| `schema_version`, `kind`, `tool_version` | 1, `game-session-evidence-auditor`, 1.0.0 |
| `complete` | Supported manifest selection, byte checks and receipt checks ran to completion |
| `review_required` | Whether findings exist; null when incomplete |
| `session_id` | Manifest's shareable alias; null when incomplete |
| `manifest` | Actual manifest `bytes` and raw-file `sha256`; null when incomplete |
| `policy`, `limits` | Explicit scope/privacy policy and fixed resource bounds |
| `files` | One result per selected capture, then non-null launch/exit reference |
| `session` | Redacted receipt analysis below; null when incomplete |
| `summary` | File/status counts, capture count, evidence bytes read, finding count |
| `findings` | Review observations; may overlap for the same file |
| `errors` | Fatal sanitized codes, optionally a 1-based selected `reference` index |

File fields: relative `path`; `role` (`capture`, `launch`, `exit`); `status`
(`verified`, `changed`, `missing`); `declared_bytes`, `expected_sha256`;
`actual_bytes`, `actual_sha256`; `size_matches`, `hash_matches`. Actual values and
comparison booleans are null for missing files. `verified` requires both size and
hash agreement. Changed files are still hashed within limits; receipt contents
are interpreted only if verified. The manifest itself is separately identified
and is not included in `selected_files` or `evidence_bytes_read`.

`session` fields:

- `launch_status`, `exit_status`: `missing`, `unverified`, `invalid` or `valid`.
- `launch_session_matches`, `exit_session_matches`: valid receipt's literal
  session ID matches the manifest; otherwise null.
- `same_process`, `same_executable`: both valid receipts' identity fields match;
  otherwise null. PIDs and executable labels themselves are omitted.
- `duration_seconds`: declared exit time minus launch time, possibly negative;
  null unless both receipts are valid. Absolute timestamps are omitted.
- `receipt_pair_consistent`: both valid, both session IDs match the manifest,
  identity fields match and duration is nonnegative; otherwise false for an
  inconsistent valid pair or null when a receipt is not valid.
- `exit_code`: integer from a valid exit receipt; otherwise null. Nonzero does
  not make an otherwise matching receipt pair inconsistent.

Receipt status `valid` refers to the supported schema after byte verification;
it does not authenticate the assertion or imply that all cross-record checks
passed. A manifest/session mismatch can accompany a valid status.

## Findings

| Code | Meaning |
|---|---|
| `no_captures` | Manifest selected no capture files |
| `missing_receipt` | Launch/exit reference is explicitly null; `receipt` identifies the role |
| `missing_file` | Listed path or a parent is absent; relative `path` and `role` supplied |
| `size_mismatch`, `hash_mismatch` | Actual selected bytes differ from a declaration; path/role supplied |
| `invalid_receipt` | Verified receipt fails supported JSON/schema checks; `receipt` and sanitized `reason` supplied |
| `session_id_mismatch` | Valid receipt's session ID differs from manifest; role supplied |
| `process_id_mismatch`, `executable_id_mismatch` | Valid pair's identity fields differ |
| `exit_before_launch` | Declared exit time precedes launch time |
| `nonzero_exit_code` | Valid exit receipt declares a nonzero code; no automatic crash diagnosis |

Order is deterministic: coverage findings, file/reference findings in manifest
order, exit-code observation, pair identity/time findings. Counts are not a unique
total of changed files. A missing receipt file gives `missing_file`; a null
reference gives `missing_receipt`. Both leave the receipt status missing.

## Incomplete results and error codes

Failure returns `complete: false`, null session/manifest/session ID, empty file
and finding arrays, empty summary and sanitized errors. Partial evidence checks
are discarded. A valid external report target may receive this incomplete JSON.
A rejected in-root output creates no file. If encoding/output fails, a small
incomplete report goes to stdout when possible.

| Category | Codes |
|---|---|
| JSON/schema | `unsupported_encoding`, `invalid_json`, `invalid_json_number`, `duplicate_json_key`, `invalid_or_unknown_fields`, `unsupported_schema_version`, `invalid_label`, `invalid_capture_list`, `invalid_declared_size`, `invalid_sha256` |
| Manifest paths | `unsafe_relative_path`, `duplicate_or_case_colliding_path`, `file_directory_path_collision`, `manifest_overlaps_evidence` |
| Resources | `file_byte_limit`, `json_depth_limit`, `capture_count_limit`, `declared_file_byte_limit`, `declared_total_byte_limit`, `receipt_byte_limit`, `evidence_file_byte_limit`, `evidence_total_byte_limit`, `evidence_byte_limit_during_read`, `metadata_byte_limit`, `report_byte_limit` |
| Paths/read/stability | `invalid_arguments`, `invalid_local_path`, `local_path_limit`, `unsafe_local_name`, `linked_path`, `invalid_parent`, `unreadable_or_missing_path`, `unreadable_evidence`, `not_a_regular_file`, `invalid_evidence_root`, `input_changed` |
| Output | `invalid_output_parent`, `output_overlaps_input`, `output_exists`, `unsafe_output`, `output_inside_evidence_root`, `output_write_failed`, `operation_failed` |

Receipt validation reasons can use JSON/schema codes above or
`unexpected_receipt_event`, `invalid_process_id`, `invalid_timestamp`,
`invalid_exit_code`. Receipt data failures are findings after hash verification;
invalid manifests, path/object refusals, I/O and resource failures make the audit
incomplete instead.

Limits: manifest 2 MiB; receipt 64 KiB; capture 256 MiB; declared total and actual
evidence reads each at most 1 GiB; 1,000 captures plus two receipts; paths at most
1,024 ASCII characters/32 components; JSON container depth 8; 32 MiB cumulative
serialized metadata plus overhead; 8 MiB final encoded report. Hash chunks are
at most 1 MiB; only bounded receipt data is retained for parsing. Accounting is
not exact resident memory. A report limit is checked before creating output.
Hashes prove agreement with supplied declarations, not publisher authenticity,
independent captures, a real process lifecycle or gameplay success.
