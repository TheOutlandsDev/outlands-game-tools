# X-Ray Log Summary report format

Schema version **1** is emitted by `xray_log_summary.py` version **1.0.0**. JSON is printed to stdout, and the same report is saved when a new `--output` destination succeeds. No original log text is copied into fields. Review numeric context before sharing.

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`; consumers should reject unknown schemas. |
| `tool` | Static program `name` and `version`. |
| `options` | Chosen `encoding`, byte/line-byte/line-count limits, and static line-number recording cap. Rejected arguments/API options show defaults. |
| `summary.complete` | `false` if validation, scanning, encoding, limits, stability checks, or output failed. Read this before interpreting counts. |
| `summary.bytes_read` | Bytes returned from the read-only stream, including a partial/rejected line or one extra byte/line used to detect a limit. An upfront file-size refusal reads zero bytes. |
| `summary.lines_read` | Successfully decoded and classified lines, including a final line without a newline. Rejected lines are excluded. |
| `summary.fatal_errors` | Lines matching `fatal_error`. |
| `summary.script_errors` | Lines matching `script_error`. A line can count as both script and fatal. |
| `summary.warnings` | Lines assigned exactly one warning category. Fatal/script lines are excluded from this total. |
| `summary.has_findings` | Whether any scanned line contributed to the three totals above. Incompleteness does not erase earlier findings. |
| `categories` | All ten static categories, including those with zero counts. Each has `code`, `count`, `line_numbers`, and `line_numbers_truncated`. |
| `markers` | Five booleans for the marker categories, indicating observed text only. |
| `errors` | Static error `code` with optional numeric `line`; no exception messages or source values. Empty for a complete successful scan. |
| `limitations` | Static explanations of scope, privacy, and interpretation. |

`line_numbers` are one-based positions in the input. Up to the first **1,000** matches per category are recorded. `line_numbers_truncated` becomes true at match 1,001, while `count` continues increasing. A capped line-number list does not itself make a scan incomplete. A category counts a line once even if its pattern appears repeatedly on that line.

Categories and their precedence are documented in the [README](README.md#what-gets-counted). Marker lines alone do not set `has_findings` or return exit 2. A complete warning-only scan does return 2. Neither a finding nor a marker is a diagnosis, root-cause statement, working connection, or proof of gameplay.

## Common incomplete codes

| Code | Meaning / next step |
| --- | --- |
| `invalid_arguments` | Required/unknown option, unrecognized encoding, or invalid numeric limit; check `--help`. Argument values are not echoed. |
| `unsupported_python` | Run with Python 3.12 or newer. |
| `invalid_encoding`, `invalid_limits` | The Python API received invalid options. |
| `unsupported_path` | A network, device, reserved, ambiguous drive-relative, or otherwise unsupported name was supplied. |
| `missing_path`, `unreadable_path`, `invalid_parent` | A physical input/output-parent component cannot be used. |
| `linked_path` | Input or output parent is a symlink, junction, or another reparse point. Choose a physical path. |
| `nonregular_input` | The selected input is a directory/device/pipe or other nonregular file. |
| `unreadable_input`, `input_error` | Reading/validation failed; the raw filesystem error is intentionally omitted. |
| `empty_log` | Zero-byte input; no log content was inspected. A nonempty blank line is a complete text scan. |
| `byte_limit` | File was too large before opening or bytes read exceeded the budget. |
| `line_byte_limit` | A line exceeded its byte cap, including its newline if present. No part of that line is classified. |
| `line_count_limit` | A further line exists beyond the chosen count cap; it is not classified. |
| `decoding_error` | Strict decoding failed at that line. Later lines were not checked. |
| `binary_log` | A decoded NUL character was detected; that line and later lines were not classified. |
| `input_changed` | File identity/stat metadata no longer matched the opening checks. Counts may describe an unstable view. |
| `resource_limit` | Python could not satisfy a read/allocation size. Use smaller limits and trusted inputs. |
| `output_is_input`, `output_exists`, `unreadable_output`, `invalid_output_parent` | A new report could not safely be prepared. Existing files are preserved. |
| `output_write_error` | Exclusive creation/writing failed after scanning. Stdout has the updated incomplete report; a newly created file can be partial. |

The tool may record more than one error, for example a decoding failure followed by a detected file change. It never recovers by guessing an encoding or silently truncating a result into a complete report.

## Exit status and sharing

`1` takes priority whenever `summary.complete` is false. Otherwise `2` means recognized fatal/script/warning findings and `0` means none of those patterns was observed. Successful JSON parsing alone does not establish a complete scan.

The report has no source excerpts, timestamps, log basename, roots, actor/item names, endpoints, or input hashes. Counts and line numbers still reveal session context; review before sharing. Omission of raw text is a limited design property, not a promise that raw logs are safe to publish or that all secrets anywhere on the system have been removed.
