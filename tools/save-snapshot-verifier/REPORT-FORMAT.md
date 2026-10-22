# Save Snapshot Verifier reports and manifest

Schema version 1. JSON is UTF-8. No absolute input roots or source contents are
included. All paths below are portable `/`-separated relative names, preserving
original letter case. Treat names, labels, metadata and hashes as potentially
private. Reports are local; no upload feature exists.

## CLI report

| Field | Meaning |
|---|---|
| `schema_version` | Integer `1`. |
| `tool` | Static tool name and version. |
| `mode` | `snapshot` or `verify`. |
| `summary.complete` | Whether the requested operation completed under its constraints. |
| `summary.files`, `summary.bytes` | Selected manifest file count and total expected data bytes when available. May remain zero on an early failure. |
| `summary.copies_verified` | Present and true after successful snapshot creation. |
| `summary.matched_files` | Present during verification; files whose length/hash matched. |
| `sources` | Snapshot mode: labels, source kinds (`file`/`directory`) and selected file counts. No absolute roots. Verification leaves this list empty rather than echoing untrusted manifest metadata. |
| `differences` | Verification findings with relative `path` and `code`: `changed_file`, `missing_file`, `unexpected_file`. |
| `errors` | Sanitized failure codes and optional validated relative paths. Raw OS exception text is omitted. |
| `limitations` | Static scope and interpretation notes. |

Exit 1 overrides findings if an operation is incomplete. Exit 2 means a complete
verification identified differences. Snapshot creation returns 0 only after all
selected copies were verified. Read the process exit as well as the report;
output errors can happen after the report was prepared.

Examples of failure categories: `destination_exists`, `confirm_closed_required`,
`overlapping_inputs`, `overlapping_destination`, `linked_path`,
`file_byte_limit`, `total_byte_limit`, `entry_count_limit`, `input_changed`,
`input_tree_changed`, `snapshot_tree_changed`, `copy_verification_failed`,
`invalid_manifest`, `invalid_manifest_path` and `operation_failed`.
Consumers should tolerate additional fields/codes in later versions.

## Snapshot layout

```text
snapshot-001/
  manifest.json
  data/
    saves/slot1.dat
    profile/profile.ini
```

`INCOMPLETE.json` remains in a partial failed snapshot. A complete snapshot has
exactly `manifest.json` and `data` at its root. An extra root entry makes
verification incomplete, so keep reports outside the snapshot.

The manifest contains integer `schema_version: 1`, static
`tool: save-snapshot-verifier`, tool `version`, UTC `created_utc`, `sources`
metadata and `files`. Each file entry has `path`, integer nonnegative `bytes`,
and lowercase hexadecimal `sha256`. A path begins with a declared source label.
Absolute/traversal/stream/device/duplicate casefolded paths are invalid.

Creation compares copied hashes with the original bytes read. Later verification
checks snapshot files against the manifest, **not against the original sources**.
The manifest is not signed or authenticated. Modifying both it and its data can
produce a different matching snapshot. Empty directory structure, attributes,
ACLs, timestamps and alternate streams are not represented as independent data.

An original worked example and commands are in [README.md](README.md).
