# MO2 Baseline Profile Builder report, schema 1

JSON is UTF-8, indented, and ends with a newline. Read the process exit code and
`status` together. Reports intentionally omit absolute roots and profile file
contents. Filenames, mod names, byte counts, and SHA-256 hashes remain potentially
sensitive. Review a report before sharing it.

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`. |
| `tool`, `tool_version` | `mo2-profile-builder` and semantic tool version. |
| `mode` | `preview` or `apply` for the current invocation. |
| `status` | `PREVIEW`, `APPLIED`, or `ERROR`. |
| `complete` | `true` only for a complete preview or verified apply. |
| `changes.enabled_before`, `enabled_after` | Counts of `+` entries excluding exact `_separator` suffixes. |
| `changes.disabled_mods` | Exact requested names, in request order. |
| `changes.priority_order_preserved` | `true`; native row order is retained. |
| `files` | Allowlisted source files present in this run, in documented allowlist order. |
| `files[].path` | One relative filename, never an absolute input root. |
| `files[].bytes_before`, `bytes_after` | Source and planned destination lengths. |
| `files[].source_sha256`, `destination_sha256` | SHA-256 of original and planned bytes. In preview the latter is a plan, not proof a destination exists. |
| `files[].changed` | Whether planned bytes differ from original bytes. |
| `source_verified_unchanged` | Source identity/bytes/inventory were verified after planning; successful apply checks them again after creation. |
| `destination_verified` | `true` only after successful apply and byte verification. Always `false` in preview. |
| `limitations` | Stable prose explaining scope and privacy limitations. |
| `error` | Sanitized machine-readable code on an error report. Change/file lists and verification fields are omitted on errors. |

An abbreviated successful preview might contain:

```json
{
  "schema_version": 1,
  "tool": "mo2-profile-builder",
  "tool_version": "1.0.0",
  "mode": "preview",
  "status": "PREVIEW",
  "complete": true,
  "changes": {
    "enabled_before": 3,
    "enabled_after": 2,
    "disabled_mods": ["Example Content Mod"],
    "priority_order_preserved": true
  },
  "source_verified_unchanged": true,
  "destination_verified": false
}
```

This excerpt omits `files` and `limitations` for readability. Run the generated
example to obtain a complete report with real hashes for the synthetic files.

## Error groups

| Examples | Interpretation |
| --- | --- |
| `invalid_arguments` | Command-line parsing failed. Supplied argument values are not echoed; mode remains the default `preview`. |
| `requested_mod_missing`, `requested_mod_case_mismatch`, `requested_mod_already_disabled` | Request did not identify exactly one currently enabled row. |
| `duplicate_disable_request`, `duplicate_modlist_entry`, `unsafe_mod_request` | Ambiguous or unsupported request/modlist. |
| `unsupported_modlist_entry`, `unsupported_modlist_encoding`, `invalid_modlist_text` | Modlist cannot be safely edited within this tool's supported text format. |
| `missing_modlist`, `ambiguous_profile_filename`, `profile_file_size_limit` | Required file missing, filename unsupported/ambiguous, or bounded read exceeded. |
| `linked_path`, `nonregular_profile_file`, `directory_entry_limit` | Input cannot be inspected within the safe local-file scope. |
| `destination_exists`, `source_destination_overlap`, `output_overlaps_inputs` | Destination or report refused before apply. |
| `closed_attestation_required`, `closed_attestation_requires_apply` | The close-programs attestation and apply flags were not used together. |
| `source_changed` | A source changed during planning/verification before apply. |
| `apply_failed_rolled_back` | Apply failed; newly created identity-matching files and private stage were removed. The original was never written by this tool. |
| `rollback_incomplete` | At least one owned-directory cleanup failed or encountered an unexpected/changed object. Inspect manually. |
| `filesystem_operation_failed` | A sanitized filesystem failure outside the more specific categories. |

`apply_failed_rolled_back` does not state that an external source modification
was reverted. The utility never writes the source. `rollback_incomplete` can
leave a partial destination or staging directory; no recursive deletion is
attempted. Do not use an incomplete destination or assume a retry can overwrite
it. On forced termination or final report-writing failure, JSON may be absent or
incomplete even though a destination exists. See the [README](README.md) before
retrying.
