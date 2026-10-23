# JSON report and asset index

Schema version **1**, kind `mod-asset-reference-checker`, tool version **1.0.0**.
Reports record literal-reference observations within selected coverage. They do
not validate binary formats, archives, effective game configuration or ownership.
See the [README](README.md) for selection, rules and assumptions.

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | Integer format version, currently `1`. |
| `kind` | `mod-asset-reference-checker`. |
| `tool_version` | Producing tool version. |
| `complete` | Whether all parsing, scope, lookup, consistency and output checks completed. |
| `policy` | File/section rules, encoding and caller coverage assumptions. |
| `limits` | Six CLI resource caps. |
| `inputs` | Selected config metadata and optional index fingerprint. |
| `summary` | Counts described below. |
| `references` | Selected direct literal references and blank assignments. |
| `context` | Observed includes and section declarations, without arbitrary unselected values. |
| `errors` | Controlled `{code}` records with optional relative `file`, `line`, `key`. |

`policy.file_rules` contains `{key, subdir, extension}` mappings; the default is
`visual`, `meshes`, `.ogf`. `section_keys` defaults to `["ammo_class"]`.
`encoding` is `utf-8-sig` by default or explicit `cp1251`.
`assume_complete_assets` and `assume_complete_sections` are independent booleans.
They record caller attestations, not verified completeness.

`limits` records `max_files`, `max_file_bytes`, `max_total_bytes`, `max_depth`,
`max_references`, `max_directory_entries`. Fixed index/report/metadata ceilings are
additional. A partial report's counts are not evidence that all input was checked.

## Input fingerprints and context

`inputs.configs` contains `{path, bytes, sha256}` for selected config files.
Paths are relative to the config root. SHA-256 covers original file bytes,
including encoding/BOM/comments; it is not a semantic config signature.
`inputs.index` is `null` without a supplied/read index, or
`{bytes, sha256, paths}` with its original byte fingerprint and path count.
No absolute roots or filenames of the supplied index are exported.

`context.includes` contains `{file, line, target}` include occurrences, with
relative config paths and one-based source lines. `context.sections` contains
`{name, file, line, parents}` declarations. Parent names are recorded context;
the checker does not resolve inheritance or calculate effective values.

## Reference rows

Every row contains:

- `kind`: `file` or `section`.
- `file`, `line`, `section`, `key`: the direct assignment's config location.
- `target`: normalized mapped file path, section name, or `null` for blank.
- `status`: a controlled presence/coverage result.
- `found_case_mismatch`: boolean review flag.

File rows also contain `loose_file`, either `null` or `{path, bytes}` for the
observed ordinary loose file. Its `path` uses actual observed relative spelling;
the requested `target` retains the mapping's expected spelling. Neither asset
contents nor hashes are read. A zero-byte or invalid-format file can still be
`found_loose`.

| `status` | Meaning |
|---|---|
| `found_loose` | Ordinary loose file observed beneath the chosen asset root. |
| `listed_in_index` | Name appears in the supplied index; no payload validation. |
| `declared_in_selection` | Referenced section exists in the selected config graph. |
| `empty_reference` | Selected value is blank; target is `null`. |
| `unresolved_coverage` | Not resolved, with relevant completeness assumption disabled. |
| `missing_in_declared_coverage` | Not resolved within coverage explicitly attested by the caller. |

Case-insensitive loose/index matches with spelling differences retain their
normal status plus `found_case_mismatch: true`. This flag is review-worthy even
when a name resolves. Entry/include spelling mismatches also increment the
case-mismatch summary, so it need not equal the number of flagged reference
rows. Section matches are case-sensitive. Lists under selected
section keys produce separate rows; one file-rule value must be a single literal.

## Summary and completion

The summary contains `config_files`, `config_bytes`, `file_references`,
`section_references`, `empty_references`, `found_loose`, `listed_in_index`,
`declared_in_selection`, `unresolved_coverage`,
`missing_in_declared_coverage`, `case_mismatches`. Reference totals count rows,
not unique target paths or inferred inherited values. Blank selected assignments
are recorded explicitly; inspect `kind` to distinguish their selected rule type.

Exit **0** means a complete check with all selected references resolved/blank,
or no selected references. Exit **2** means a complete check with unresolved
coverage, a missing target under caller-attested coverage or a case mismatch.
Exit **1** means invalid/unsupported/incomplete processing or output failure,
even when partial references already have review findings. Check both status
and `complete`. A command-line failure can happen before JSON exists.

Zero references is a statement about configured keys in selected direct
assignments, not validation of an entire game/mod configuration. A complete
report does not establish that an index, asset root or selected graph covers
everything the game uses.

## Asset-path index schema

The optional UTF-8 JSON index must have exactly three fields:

```json
{"schema_version": 1, "kind": "asset-path-index", "paths": ["meshes/toy/absent.ogf"]}
```

`schema_version` must be integer `1`, not boolean. `kind` must match exactly;
`paths` is a list of portable relative paths beneath the virtual asset root.
Duplicate keys, unknown fields, invalid types, traversal, absolute paths and
ambiguous case duplicates are rejected. Names are assertions; there are no
archive IDs, payload lengths or hashes. Absence from this index alone does not
prove absence from game archives or another mod.

## Sharing

Relative paths, section/key names, line numbers, lengths and hashes may reveal
private material. Review
reports and index files before sharing. Omission of absolute roots and payloads
does not anonymize data, detect all secrets, authenticate an index or confer MIT
licensing rights over inspected material.
