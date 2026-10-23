# ZIP layout report format, schema 1

The report is UTF-8 JSON with ASCII escapes. Entry indices are zero-based central
directory order; physical local-header order may differ. Byte counts and offsets
are integers; ranges are half-open. Every size/CRC is an unverified declaration.

| Field | Meaning |
|---|---|
| `schema_version`, `kind`, `tool_version` | Schema 1, `mod-package-zip-layout-inspector`, 1.0.0 |
| `complete` | Entire selected supported metadata subset inspected successfully |
| `policy` | Supported format/methods; extraction and payload checks false; comparison NFC then casefold |
| `limits` | Fixed archive, entry, central, name, read, accounting and final-report byte ceilings |
| `archive` | Null on incomplete; otherwise the inventory below |
| `errors` | Stable code objects; native exception text and local filenames omitted |

Archive fields: alias `label`; actual archive `bytes`; `central_directory` with
`offset`, `bytes`, SHA-256 of raw central bytes; `archive_comment_bytes` (comment
text omitted); `metadata_bytes_read` including repeated reads and end search;
`declared_total_uncompressed_bytes`; `common_top_level_folder` string or null;
`issues`; and `entries`. No absolute input path, member comment text, file data or
output path is recorded. Member names can themselves be private or unsafe.

Entry fields: original decoded `name` (including terminal slash/NUL), `directory`
from terminal slash, numeric ZIP `method` and `flags`, `compressed_bytes`,
`uncompressed_bytes`, eight-character hex `declared_crc32`, `local_offset`, unique
numeric `extra_field_ids` from local/central headers, and `issues`. Duplicate or
case/normalization collisions add `first_name_entry`; file/directory prefix
conflicts add `ancestor_entry`. First-provider references bound report growth.
Comparison removes terminal slashes, normalizes NFC, then casefolds; it is a
portable review policy, not an exact model of every filesystem or game engine.

## Finding codes

| Scope/code | Meaning |
|---|---|
| Entry `unsafe_path` | Empty/dot/parent component, forbidden/control character, backslash, drive/stream/absolute name, reserved device, trailing space/dot, component over 255 characters, or more than 64 components |
| Entry `non_ascii_name` | Name outside conservative ASCII portability policy |
| Entry `duplicate_name` | Exact decoded name already present after terminal slash removal |
| Entry `case_or_normalization_collision` | NFC/casefold name already present with a different decoded name |
| Entry `file_directory_collision` | A file occupies an ancestor of this member |
| Entry `link_or_special_entry` | Unix creator attributes declare a symlink or special file type |
| Entry `directory_attribute_mismatch` | Slash/DOS directory attributes disagree, or Unix directory mode lacks slash |
| Entry `directory_has_declared_data` | Slash entry declares nonzero data |
| Entry `encrypted_entry` | Traditional entry encryption flag is set; encryption not validated |
| Entry `uninterpreted_extra_fields` | Extra fields structurally parsed but not interpreted |
| Entry `large_declared_entry` | Uncompressed entry declaration exceeds 1 GiB |
| Entry `high_declared_ratio` | Uncompressed declaration exceeds 1 MiB and exceeds `max(compressed,1)*1000` |
| Archive `large_declared_total` | Sum of uncompressed declarations exceeds 8 GiB |
| Archive `common_top_level_folder` | Every file uses the same portable top-level directory; review intended root |

Any finding gives exit 2 for a complete report. An empty supported ZIP gives exit
0 and zero entries; that does not establish a useful mod package. Thresholds are
strictly greater-than comparisons. Directory entries do not influence the
common-folder observation; all files must have portable ASCII paths.

## Incomplete results

Malformed/unsupported/resource failure discards the inventory (`archive: null`),
sets `complete: false`, adds an error and exits 1. Structural codes include
`missing_or_ambiguous_end_record`, `central_range_invalid`,
`invalid_central_signature`, `local_central_mismatch`, `local_range_invalid`,
`local_descriptor_mismatch`, `descriptor_mismatch`, `descriptor_range_invalid`,
`ambiguous_descriptor`, `stored_size_mismatch`, `malformed_extra_field`,
`invalid_name_encoding`, `truncated_central_entry`, `trailing_central_bytes`,
`noncontiguous_or_overlapping_layout`, `metadata_range_invalid`, `truncated_archive`.

Supported-subset refusals: `unsupported_archive_size`, `unsupported_multidisk`,
`unsupported_zip64`, `unsupported_zip64_or_unicode_override`,
`unsupported_version_method_or_flags`. Fixed resource errors: `entry_count_limit`,
`central_byte_limit`, `name_or_central_entry_limit`, `metadata_read_limit`,
`metadata_byte_limit`, `report_byte_limit`.

Selection/filesystem/output errors include `invalid_arguments`, `invalid_label`,
`invalid_local_path`, `linked_path`, `invalid_parent`,
`unreadable_or_missing_path`, `not_a_regular_file`, `input_changed`,
`invalid_output_parent`, `output_overlaps_input`, `output_exists`, `unsafe_output`,
`output_write_failed`, and generic `operation_failed`. On an output failure or a
report byte limit, a small incomplete report goes to stdout when possible. A
complete metadata inspection never proves extraction safety or payload integrity.
