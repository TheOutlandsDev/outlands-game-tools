# JSON manifest and diff reference

Schema version **1**, tool version **1.0.0**. Consumers should reject unsupported
schemas rather than guess. Both document kinds are observations of selected
loose-file metadata, not signed attestations or game compatibility certificates.
See the [README](README.md) for commands and the scope of the MO2 model.

## Manifest document

| Field | Meaning |
|---|---|
| `schema_version` | Integer `1`; booleans are not accepted as integers. |
| `kind` | `mod-content-manifest`. |
| `tool_version` | Producing tool version. |
| `complete` | Whether the selected scan finished under all input, traversal, read and stability checks. |
| `hash_algorithm` | `sha256`. |
| `selection` | Comparable mode/filter policy described below. |
| `limits` | Positive `max_file_bytes`, `max_total_bytes`, `max_files`, `max_entries`. |
| `providers` | Ordered provider IDs, highest priority first. |
| `files` | Effective relative files, each with `path`, `provider`, `bytes`, `sha256`. |
| `file_conflicts` | Relative paths supplied by multiple observed providers, with `path`, `winner`, `providers`. |
| `summary` | `files`, `bytes`, `conflicts`, `excluded_entries` counts. |
| `errors` | Structured failures, with `code` and an optional relative `path`. |

`path` uses `/` separators and remains relative to the selected virtual root.
Names must be safe and portable, with at most 128 components; traversal, absolute/device paths, ambiguous
case duplicates and invalid components are rejected. A file's `bytes` is a
nonnegative integer; empty files have length zero and the normal SHA-256 empty
digest. `sha256` is 64 lowercase hexadecimal characters. File content, raw
filesystem errors, source absolute paths and original timestamps are omitted.

Directory mode uses provider `source`. MO2 mode may use `overwrite`, each
`mod:Name`, then `base`. Each file refers to a declared provider. Conflict
providers retain overall priority order; `winner` agrees with both the first
provider and the effective file's provider. Masked copies are neither hashed
nor included in `files`. A conflict alone does not imply different bytes.

`summary.files` and `summary.bytes` describe effective hashed files, rather than
all copies found. `summary.conflicts` counts overlapping effective paths.
`excluded_entries` counts encountered entries filtered by policy; excluded
subtrees are not opened to count descendants. It does not list excluded names.
Counts in an incomplete report are partial observations and must not be used
as evidence of a complete installation inventory.

## Selection and fixed exclusions

`selection` contains exactly these fields:

- `mode`: `directory` or `mo2`.
- `extensions`: sorted lowercase dot-prefixed suffixes; `[]` means all eligible
  ordinary file extensions.
- `excluded_directories`, `excluded_files`, `excluded_suffixes`: canonical fixed
  lists defining this version's name-based exclusions.

Comparisons require equivalent selection values. This prevents a narrow `.ltx`
scan being reported as a content loss against an unrestricted scan. Per-scan
limits are recorded separately and may differ if both scans completed.

Fixed directory names, matched without regard to case beneath each selected
root, are:

```text
.agents .aws .cache .codex .git .ssh .venv __pycache__
backup backups cache caches crash_reports crashlogs dumps logs
node_modules profiles saved games savedgames savegames saves
screenshots temp tmp
```

The space in `saved games` is part of one directory name. Fixed file names are
`.env`, the `.env.*` prefix policy, `.git-credentials`, `.netrc`, `authorized_keys`,
`credentials`, `credentials.json`, `id_dsa`, `id_ecdsa`, `id_ed25519`, `id_rsa`,
`known_hosts`, and `secrets.json`. Fixed excluded suffixes are `.key`, `.p12`,
`.pem`, and `.pfx`. These filters always apply, even with `--extensions`.

In MO2 mode, provider-root `meta.ini` and any file or directory ending `.mohidden` are
also ignored as MO2 metadata/hidden content. Directory mode does not apply
these MO2-only rules. These rules do not inspect file content or determine
whether an eligible file is safe to disclose. The explicit selected root's
own name is not an implicit exclusion; choose inputs carefully.

## Diff document

| Field | Meaning |
|---|---|
| `schema_version` | Integer `1`. |
| `kind` | `mod-content-diff`. |
| `tool_version` | Producing tool version. |
| `complete` | Both imported manifests passed strict validation and selection compatibility checks, and comparison completed. |
| `selection` | Shared selection policy, or `null` when unavailable after a failure. |
| `added` | Candidate-only file records. |
| `removed` | Baseline-only file records. |
| `changed` | Shared paths whose bytes/length differ, with both metadata records. |
| `provider_changes` | Shared byte-identical paths whose effective provider differs. |
| `summary` | `baseline_files`, `candidate_files`, `identical_files`, `added`, `removed`, `changed`, `provider_changes`. |
| `errors` | Structured comparison/import/output failures. |

Rows in `added` and `removed` have the manifest file fields `path`, `provider`,
`bytes` and `sha256`. Rows in `changed` and `provider_changes` contain `path`,
`baseline` and `candidate`; each side has `provider`, `bytes` and `sha256`.
The candidate is always compared against the baseline, so reversing arguments
reverses additions/removals and the sides of each change.

A path with different bytes and a different provider appears in `changed`.
It is not double-counted under `provider_changes`. Equal size is insufficient
for a content match: SHA-256 must also match. A diff compares stored observations
only and does not open either source tree or authenticate either manifest.
Paths match without regard to case. Case-only spelling changes between valid
manifests are ignored, while collisions within a manifest are rejected.
`identical_files` counts byte-identical paths, including any provider changes.

## Completion, validation and exits

Manifest import currently requires tool version `1.0.0` and accepts only supported complete manifests with exact expected
fields, valid types/paths/hashes, declared providers, coherent conflict winners
and consistent summaries. Malformed/duplicate-key JSON and invalid policy
values are refused; failure reports do not echo untrusted input strings or raw
exceptions. Partial source scans are useful for diagnosis but are deliberately
ineligible as diff inputs.

A complete scan returns **0**. A complete diff returns **0** when effective
content and providers match, or **2** when any of the four change lists is
nonempty. An incomplete/invalid operation or report-output failure returns
**1**. Output files are exclusive new files outside selected scan roots and
cannot replace either manifest input. A command-line failure may occur before
JSON exists. Check both exit status and `complete`.

Relative paths, mod names, sizes and hashes remain potentially private. Review
every report before sharing it. These documents have no signature or trusted
chain of custody; matching metadata does not establish licensing, authorship,
runtime compatibility, saved-profile correctness or that a game loaded a file.
