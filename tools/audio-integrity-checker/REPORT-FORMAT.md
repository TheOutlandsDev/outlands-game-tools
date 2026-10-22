# JSON report reference

This reference describes schema version **1**. A report records the loose-file
selection and decoding checks observed during one scan, not a game audio
compatibility certificate. See the [README](README.md) for installation,
commands and limitations.

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | Integer format version, currently `1`. Consumers should explicitly handle an unfamiliar version. |
| `tool` | Checker `name` and `version`. |
| `mode` | `tree` for `--source-dir`, or `mo2` for the saved-profile overlay model. |
| `runtime` | Observed SoundFile, NumPy and libsndfile versions. |
| `options` | Whether hashes were requested, plus byte/frame/channel limits. |
| `summary` | Completion and candidate/check totals described below. |
| `providers_priority_highest_first` | Providers in the order used to select effective files. |
| `files` | Results for selected effective loose audio paths. Masked copies are not decoded. |
| `file_conflicts` | Relative paths with multiple observed providers, including the selected winner. |
| `modlist` | Initially read saved-modlist hash and stability result in MO2 mode; `null` in source mode. |
| `warnings` | Structured problems that make a scan incomplete. Review even if some files pass. |
| `errors` | Structured invalid-input/runtime problems. A partial report can still be useful. |
| `limitations` | Scope statements recorded with the report. |

Reports omit absolute roots, tags, sample data, audio/source copies, and raw
native decoder messages. **Mod names, relative paths, optional hashes, sizes,
audio metadata and counts can still identify private material.** Review before
sharing; omission of absolute paths is not a promise of anonymity.

## Runtime and options

`runtime.soundfile_version`, `runtime.numpy_version`, and
`runtime.libsndfile_version` record the loaded dependencies. The checker
requires exactly SoundFile **0.13.1** and NumPy **2.2.6**; unsupported versions
make the scan incomplete rather than silently changing the supported decoder
environment. Fields can be `null` when runtime loading fails. The libsndfile
build may vary by platform/package; its version alone does not list every
available codec or prove a game uses the same decoder.

`options.sha256` is a boolean, default `false`.
`options.max_file_bytes`, `options.max_frames`, and `options.max_channels`
record the chosen per-file caps. Defaults are `268435456` bytes, `20000000`
audio frames, and `32` channels. A frame contains one sample per channel,
so 20 million stereo frames contain 40 million samples. Invalid arbitrary API
limit values are not echoed into shareable reports.

The byte cap bounds the selected file's ordinary read size; declared **and**
actually decoded frame counts are capped. Decode blocks contain at most
262144 sample positions (or the smaller remaining frame allowance), rather
than loading the whole decoded file at once. These are tool-level caps, not
isolation of native parser CPU, memory, crashes or vulnerabilities.

## Summary and exit status

| Field | Meaning |
|---|---|
| `complete` | `true` when the scan completed under the tool's input/read checks. A skipped/problem input makes it `false`. |
| `enabled_mods` | Enabled named mod providers selected from the modlist, excluding base and Overwrite. Zero in source mode. |
| `scanned_providers` | Selected provider directories traversed. |
| `loose_audio_files` | Candidate copies found before overlay winners are selected. |
| `effective_files` | Selected relative audio paths after priority resolution. |
| `checked_files` | Sum of `passes`, `decode_errors` and `anomalies`. A decoder error is an attempted completed check, not a skip. |
| `passes` | `DECODE_PASS` records. |
| `decode_errors` | `DECODE_ERROR` records. |
| `anomalies` | `DECODE_ANOMALY` records; counts files, rather than individual issues. |
| `skipped_files` | Effective files not successfully checked under the scan's constraints. |
| `shadowed_files` | Lower-priority candidate copies masked by selected effective paths. These copies are not decoded. |

A complete scan without findings returns process exit `0`; a complete scan
with at least one decode error or anomaly returns `2`. An invalid/incomplete
scan or output failure returns `1`, even if other files pass or findings exist.
Check the process exit as well as `summary.complete`: a process may fail before
a report is available. Overlaps alone do not cause exit `2`.

## Providers and file conflicts

Each provider record has `name`, `kind` and numeric `priority`; lower numbers
are higher priority. Source mode uses `<source>` with kind `source`. MO2 mode
uses optional `<overwrite>` with kind `overwrite`, then enabled named providers
with kind `mod` in native saved modlist order (first highest), then optional
`<base>` with kind `base`.

Each `file_conflicts` record contains:

| Field | Meaning |
|---|---|
| `path` | Shared normalized relative audio path. |
| `winner` | Selected provider object with `name` and `kind`. |
| `providers_in_priority_order` | All observed providers of the path, highest first, each with `name` and `kind`. |

For example, the generated MO2 example has a `shared.wav` record with winner
`{"name": "<overwrite>", "kind": "overwrite"}` and provider order
`<overwrite>`, `AudioHigh`, `AudioLow`. Only Overwrite's copy is decoded.
The overlap record does not compare file contents, declare a harmful conflict,
or prove the lower copies are good/bad. No hashes of masked copies are computed.

All input roots must describe the same virtual directory level. Matching uses
Python's Unicode casefold approximation, rather than exact NTFS/Win32 collation.
Ambiguous paths are rejected rather than arbitrarily choosing a copy. Reported
paths are casefolded normalized keys and may not preserve the filename's original
letter casing. This is a loose-file model, not MO2's running VFS or an archive
extractor.

## File records

| Field | Meaning |
|---|---|
| `path` | Normalized relative path below the virtual data root; no absolute input root. |
| `provider` | Selected provider's name. |
| `kind` | `source`, `mod`, `overwrite` or `base`. |
| `status` | `DECODE_PASS`, `DECODE_ERROR`, `DECODE_ANOMALY` or `SKIPPED`; see below. |
| `bytes` | Selected file size observed before reading, when available. |
| `sha256` | SHA-256 of original file bytes when `--sha256` was requested and hashing finished; otherwise `null`. |
| `format` | Decoder-reported container identifier, such as `WAV`; not inferred from the extension. |
| `subtype` | Decoder-reported encoding/subtype identifier, such as `PCM_16`. |
| `sample_rate` | Decoder-reported samples per second per channel. |
| `channels` | Decoder-reported number of channels. |
| `declared_frames` | Total frames reported by the decoder when opening the file. This need not be a raw header field. |
| `decoded_frames` | Frames actually returned by the block decode loop, when available. |
| `finite_samples` | Whether observed float32 samples were all finite; `null` if unavailable. |
| `issues` | Anomaly categories, described below; may be empty even for a decode error or skip. |
| `code` | Optional sanitized decode-error/skip category, rather than native exception text. |

Unavailable fields remain `null`; `code` can be absent. A skipped file may
retain partial metadata/hashes gathered before the refusal or change detection.
Do not interpret that partial record as a pass. Extra fields/categories may be
introduced in future versions; consumers should allow unknown diagnostics.

| Status | Meaning |
|---|---|
| `DECODE_PASS` | Decoder completed; returned a positive frame count equal to its reported total; observed float32 samples were finite. |
| `DECODE_ERROR` | The decoder could not open/read/close the selected audio successfully. `code` is `decode_failed`; native error messages are omitted. |
| `DECODE_ANOMALY` | Decoding finished but one or more of the checks in `issues` failed. |
| `SKIPPED` | The file was not successfully checked under the supported input/dependency/resource/stability constraints; the scan is incomplete. |

`issues` can contain `empty_audio` (zero decoded frames),
`frame_count_mismatch` (returned frames differ from the decoder's initial total),
and `nonfinite_samples` (a NaN or infinite float32 sample was observed).
One file can have several issues. Frame counts and finite values do not establish
audible quality. Sample rate and channel count are metadata, not automatic
corruption classifications.

## Diagnostics and stability

Warnings/errors have a `code` and may have a relative `path`, `provider` or
numeric modlist `line`. Examples include:

- Selection/path problems: `missing_mod`, `linked_path`,
  `ambiguous_case_path`, `ambiguous_case_mod`, `overlapping_source_roots`,
  `unsupported_modlist_entry`, `unsupported_foreign_entry` and `no_audio_files`.
- File/resource problems: `file_size_limit`, `frame_limit`, `channel_limit`,
  `invalid_audio_metadata`, `decode_resource_limit`, `read_resource_limit`,
  `decoder_operation_failed`, `unreadable_file` and `input_changed`.
- Runtime problems: `decoder_unavailable`, `unsupported_soundfile_version`
  and `unsupported_numpy_version`.

This list is illustrative, not exhaustive. Diagnostic codes describe observed
categories rather than repair instructions or a diagnosis of a game crash.

MO2 `modlist.sha256` identifies the initially read profile bytes, independently
of the optional audio hashing flag. `modlist.unchanged` records whether reread
profile bytes still matched. Effective file identity, size and modification
time are checked against the opened file and path after decoding; changes cause
a skip. These checks cannot detect every race or directory-membership change,
and do not create an atomic snapshot. Keep inputs stable during a scan.

## Safe outputs and sharing

`--output` creates one **new** JSON file exclusively. It must have an existing
local parent, be outside all scanned source/mod/base/Overwrite roots, and not
replace the modlist. Linked ancestors are refused. No output option means
stdout. Shell redirection may replace a file before the checker can guard it;
use `--output` to save reports.

```powershell
$report = Get-Content -LiteralPath 'D:\Reports\audio-check-001.json' -Raw | ConvertFrom-Json
$report.runtime
$report.summary
$report.files | Where-Object status -ne 'DECODE_PASS' | Select-Object path, provider, status, code, issues
$report.file_conflicts
$report.errors
$report.warnings
```

For a reproducible report without game files, use the
[original generated example](examples/README.md). Review filenames, provider
names, hashes and metadata before attaching any report to a public issue. Do
not attach game audio or third-party material without redistribution rights.
