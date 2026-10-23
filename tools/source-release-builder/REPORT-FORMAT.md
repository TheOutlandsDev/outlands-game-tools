# Manifest, ZIP and result formats

Version 1.0.0 accepts manifest schema 1 and emits result schema 1. All hashes are
lowercase SHA-256 hexadecimal. This tool accepts an explicitly reviewed list;
it does not generate a publication inventory or validate ownership/privacy.

## Canonical input manifest

`--source-root` must contain an ordinary local `SOURCE-MANIFEST.json`. An
explicit `--manifest` must identify that same file. UTF-8 with an optional BOM
is accepted; exact original bytes, including whitespace/BOM, are included in
the ZIP. Do not list the manifest within itself.

```json
{
  "schema_version": 1,
  "license": "MIT",
  "files": [
    {
      "path": "LICENSE",
      "bytes": 1104,
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  ]
}
```

The above digest/length are illustrative, not a valid license inventory. The
[example generator](examples/create_example.py) computes actual values for
original toy files. Unknown top-level or record fields and duplicate keys at
any object depth are refused. `files` contains 1–100,000 records. Each record
has exactly `path`, `bytes` and `sha256`; `bytes` is an integer from 0 to 2 MiB,
with a total of at most 256 MiB. JSON booleans, floats, NaN and infinities are
not accepted as integer lengths/schema values.

Paths have at most 1,024 portable ASCII characters and 128 components including
the filename. Paths are unique without regard to case; directory component casing must also
be consistent. A path cannot be another file's ancestor. The root entry must
be named exactly `LICENSE`, match its hash and contain standard MIT text. See
the [README allowlist and guards](README.md#what-can-be-included) for all file
and path rules. Unlisted content is excluded, even when it would pass those
rules. Listing a file with valid source text and a license declaration does
not prove that you have permission to publish it.

## Archive and checksum

The ZIP contains exactly all listed source members plus `SOURCE-MANIFEST.json`.
Names sort by Unicode code-point order (only portable ASCII is accepted).
An optional portable prefix is prepended consistently to every member. Source
members retain their exact bytes; no line-ending normalization occurs.

All members use `ZIP_STORED`, Unix regular-file `0644` metadata and the fixed
ZIP timestamp `1980-01-01 00:00:00`. No directory/link entries are emitted.
Within the supported ZIP format, these choices avoid time/path/zlib variation.
The adjacent checksum is `OUTPUT.zip.sha256`, with ASCII bytes:

```text
<64 lowercase SHA-256 characters>  OUTPUT.zip
```

There is one final LF. The filename contains no directories. It is a checksum,
not a signed attestation or provenance claim.

## Successful stdout

```json
{
  "schema_version": 1,
  "tool_version": "1.0.0",
  "status": "PASS",
  "source_files": 3,
  "archive_members": 4,
  "source_bytes": 1200,
  "archive_bytes": 2200,
  "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "archive_name": "demo-source.zip",
  "checksum_name": "demo-source.zip.sha256",
  "all_archive_bytes_match": true
}
```

Counts/sizes/hash above are illustrative. `source_files` excludes the manifest;
`archive_members` includes it. `source_bytes` is the sum of listed source
lengths, and `archive_bytes` includes the manifest and ZIP headers. `PASS` and
exit 0 mean source and archived byte hashes matched, all member names/metadata
matched and an adjacent checksum was written. Archive basenames remain visible.
No absolute input roots or per-file source content are printed.

## Failed stdout

```json
{
  "schema_version": 1,
  "tool_version": "1.0.0",
  "status": "FAIL",
  "code": "source_manifest_mismatch",
  "created_outputs": 0,
  "removed_outputs": 0,
  "partial_outputs_possible": false
}
```

Failure exits 1. Fields are bounded scalars with controlled codes; raw argument
values and exception strings are omitted. `created_outputs` counts outputs
successfully reserved by this invocation (0–2). `removed_outputs` counts owned
outputs removed during failure cleanup. If these differ, partial or replaced
outputs may remain. Inspect them locally and never publish failed output.

| Code | Meaning / next step |
|---|---|
| `arguments_invalid` | Check `--help` and required arguments. |
| `input_path_invalid`, `manifest_path_invalid` | Use ordinary local portable paths; inspect the reviewed inventory. |
| `canonical_manifest_required` | Use the root `SOURCE-MANIFEST.json`. |
| `manifest_json_invalid`, `manifest_duplicate_key` | Repair JSON encoding, syntax or duplicate object keys. |
| `manifest_schema_invalid`, `manifest_record_invalid` | Check exact fields, MIT declaration, integer lengths and lowercase hashes. |
| `manifest_self_listed` | Remove the manifest's own record. |
| `manifest_path_collision` | Resolve duplicate/case/ancestor collisions. |
| `root_license_required`, `root_license_not_mit` | Review and provide an appropriate root MIT notice; do not relabel unrelated code. |
| `manifest_limit_exceeded`, `file_count_limit`, `total_byte_limit` | Use a smaller reviewed source release. Per-file excess is `manifest_record_invalid`. |
| `source_type_rejected`, `source_path_excluded`, `source_text_required` | Remove unsupported/binary/runtime material from the reviewed selection. |
| `linked_path_rejected`, `directory_required`, `regular_file_required` | Use ordinary files/directories without linked ancestors. |
| `source_manifest_mismatch`, `source_changed` | Stop writers and review changed/missing inputs before rebuilding. |
| `output_exists`, `output_inside_source`, `zip_output_required`, `prefix_invalid` | Choose two new external destinations and a valid prefix/name. |
| `archive_members_mismatch`, `archive_metadata_mismatch`, `archive_bytes_mismatch`, `output_changed` | Archive verification failed; do not publish the outputs. |
| `io_or_archive_failure` | A file was absent/unreadable, permissions/storage failed or ZIP I/O failed. Check locally; raw private details are not printed. |

The builder cannot distinguish every I/O cause while keeping public reports
small and private. It does not automatically retry, change permissions or
regenerate inventories. `--help` and `--version` are human-readable exceptions
to the one-JSON-object output contract.
