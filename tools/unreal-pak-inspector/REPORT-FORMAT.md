# JSON report format

Schema **1**, kind `unreal-pak-index-conflict-inspector`, tool **1.0.0**.
The [module guide](README.md) defines the supported standard-v3 subset and limits.

| Field | Meaning |
|---|---|
| `schema_version`, `kind`, `tool_version` | Format and producer identifiers. |
| `complete` | All selected indexes, ranges and source-stability checks completed. Output failure takes precedence via exit status. |
| `policy` | Version `3`, `ascii_case_insensitive` path matching, and explicit false flags for payload reads, local-header validation and load-order inference. |
| `limits` | Effective six CLI resource caps; fixed ceilings are additional. |
| `paks` | Complete per-archive index observations, sorted by user alias. |
| `conflicts` | Path-overlap and file/directory groups, without a predicted winner. |
| `summary` | `paks`, `entries`, `unique_paths`, `index_bytes`, `path_overlaps`, `file_directory_conflicts`. |
| `errors` | Controlled `{code}` with optional supplied `pak` alias and zero-based `entry`. |

## Per-archive and entry records

Each PAK contains `label`, original file `bytes`, `version`, `mount`, `index` and
`entries`. No actual local filename or absolute input path is added. Aliases and
archive names in the data itself are not redacted.

`index` contains `offset`, `bytes`, footer-declared `sha1`, calculated `sha256`
and `hash_verified: true`. SHA-1 equality is required on exact index bytes;
neither hash is a signature or whole-archive/payload fingerprint.

Entries remain in original index order and contain:

- `path`: original relative entry spelling.
- `virtual_path`: original mount suffix plus entry, without the supported
  `../../../` virtual-namespace prefix.
- `offset`, `header_bytes`, `stored_bytes`, `uncompressed_bytes`: declared sizes
  and the calculated v3 header length used for bounds checks.
- `compression_method`, `block_count`, `block_size`: raw metadata, not a decoder result.
- `declared_sha1`: the unverified entry digest from the index.

The checked interval is `[offset, offset + header_bytes + stored_bytes)` before
the index. Bounds/overlap checks validate assertions, without reading the local
header or stored bytes. Payload changes alone can leave this report unchanged.

## Conflict records

An exact normalized path overlap uses:

```json
{
  "kind": "path_overlap",
  "path": "toy/content/shared.uasset",
  "providers": [{"pak": "base", "entry": 0}, {"pak": "mod", "entry": 0}]
}
```

A provider's `pak` resolves to a PAK label and `entry` indexes that PAK's `entries`
array. It does not refer to the PAK-list position or priority. Each file name
occurs at most once per archive under the fixed case policy.

A prefix conflict uses `kind: file_directory`, `path` (ancestor file key),
`descendant` (child key), `file_providers` and `descendant_providers`. One group
is emitted per observed ancestor/descendant relation. Both keys are lowercase.
Groups follow path-component lexical order; an overlap precedes prefix groups
for the same descendant. No mount order or byte-equality classification is inferred.

## Completion and privacy

Exit **0** means complete/no conflicts; **2** means complete/with conflicts;
**1** means unsupported, invalid, incomplete, limit or output failure. Incomplete
reports have no PAKs/conflicts and zero summary counts; they do not prove absence
of conflicts. An error late in one archive invalidates the combined inspection.
Consumers should tolerate unknown controlled error codes and optional locations.

Common codes include `unsupported_footer`, `unsupported_pak_version`,
`index_range_invalid`, `index_hash_mismatch`, `truncated_index`,
`unsupported_string_length`, `unsupported_string_encoding`, `unterminated_string`,
`embedded_string_nul`, `unsupported_mount`, `unsafe_virtual_path`,
`duplicate_or_case_colliding_entry`, `internal_file_directory_collision`,
`entry_range_invalid`, `overlapping_entry_ranges`, `stored_size_mismatch`,
`unsupported_encryption_or_flags`, `compression_block_limit`,
`compression_range_invalid`, `compression_metadata_invalid`, `repeated_archive`,
`metadata_byte_limit`, `report_byte_limit` and the named CLI count/byte limit codes.

Visible metadata and hashes can identify private material. Review reports before
sharing. A matching index hash, a digest listed in an index, or no selected overlap
does not establish valid payloads, engine compatibility, authorship or permission
to redistribute inspected files.
