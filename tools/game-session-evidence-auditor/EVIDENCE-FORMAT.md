# Evidence manifest and receipt formats, schema 1

Original generic formats, independent of any launcher or collector. All JSON is
UTF-8 with an optional initial BOM. Unknown/missing fields, duplicate keys,
non-finite constants, comments and trailing documents are refused. Schema version
must be the integer 1, not a boolean, float or string.

## Manifest

The following valid schema example declares one empty capture and two unprovided
receipts. If that empty file exists it can hash correctly; the absent receipts
still request review. The SHA-256 shown is the standard digest of zero bytes.

```json
{
  "schema_version": 1,
  "session_id": "session-001",
  "captures": [
    {"path": "captures/empty.log", "bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
  ],
  "receipts": {"launch": null, "exit": null}
}
```

`session_id` is a 1–64 character ASCII label using letters/digits/`_.-`, starting
with a letter/digit. Matching is literal and case-sensitive. Choose a shareable
alias rather than a private identifier.

`captures` is an array, possibly empty. `receipts` has exactly `launch` and `exit`;
each is null or a reference object with exactly `path`, `bytes`, `sha256`.
Paths are relative to the explicitly selected evidence root, not the manifest's
location. Each reference must name a file, not a directory or pattern.

- `path`: 1–1,024 ASCII characters, forward slashes, at most 32 components.
  Components use the collection's conservative Windows-compatible policy:
  no empty/dot/parent, reserved device name, forbidden/control character,
  slash/backslash within a component, trailing dot/space or component over 255
  characters. Absolute, drive and stream names are invalid.
- `bytes`: exact nonnegative integer size; booleans are invalid.
- `sha256`: exactly 64 lowercase hexadecimal characters from trusted captured bytes.

Paths must be unique ignoring ASCII case across captures and receipts. A file
reference cannot also be an ancestor of another reference. The manifest cannot
reference itself by the same path. Hardlink aliases are not detected; counts
describe selected references, not independent captures. Unlisted files remain
outside the audit selection.

## Generic receipts

Fictional launch example:

```json
{
  "schema_version": 1,
  "session_id": "session-001",
  "event": "launch",
  "process_id": 1234,
  "executable_id": "toy-game",
  "timestamp_utc": "2026-01-01T12:00:00Z"
}
```

Exit example:

```json
{
  "schema_version": 1,
  "session_id": "session-001",
  "event": "exit",
  "process_id": 1234,
  "executable_id": "toy-game",
  "timestamp_utc": "2026-01-01T12:02:00Z",
  "exit_code": 0
}
```

Exactly these fields are accepted. `event` must match the manifest reference's
role. `process_id` is an integer from 1 to 2,147,483,647. `executable_id` uses the
same label syntax as session IDs and is compared literally between receipts;
it is not a program path or binary hash. `timestamp_utc` is a valid Gregorian
date/time in the exact `YYYY-MM-DDTHH:MM:SSZ` form (years 0001–9999), with no
fractions, offsets or leap seconds. Exit timestamps may equal launch timestamps.
`exit_code` is an integer from -2,147,483,648 to 4,294,967,295. Booleans are invalid.

Receipt JSON is parsed only after its reference's size and hash match. A malformed
verified receipt is an audit finding, not a valid lifecycle record. The receipts
are unsigned assertions. The auditor does not collect them, consult a process
table or verify clock accuracy. Preserve original observations and explain any
conversion; do not rewrite receipts just to obtain a clean result.

## Author a manifest for an explicit stable selection

This Python recipe records expected bytes for files you already captured and
trust. It creates a new manifest exclusively. It does not validate, observe or
authenticate a session. Retain that original manifest separately; a later audit
compares against it instead of regenerating expected hashes after changes.
Replace the folder, session alias and explicitly selected filenames as needed.

```python
import hashlib
import json
from pathlib import Path

root = Path("D:/SessionEvidence/session-001")

def reference(relative):
    path = root / relative
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": relative, "bytes": path.stat().st_size, "sha256": digest}

manifest = {
    "schema_version": 1,
    "session_id": "session-001",
    "captures": [reference("captures/session.log")],
    "receipts": {
        "launch": reference("receipts/launch.json"),
        "exit": reference("receipts/exit.json"),
    },
}
with (root / "manifest.json").open("x", encoding="utf-8") as stream:
    json.dump(manifest, stream, indent=2)
    stream.write("\n")
```

Use this authoring recipe only on stable ordinary local files you selected. The
auditor's guarded path/read checks run during auditing, not as part of this short
authoring example. For absent receipts set the relevant reference to null rather
than inventing a record. No automatic import or adapter for an existing collector
is included in schema 1. See [report semantics and bounds](REPORT-FORMAT.md).
