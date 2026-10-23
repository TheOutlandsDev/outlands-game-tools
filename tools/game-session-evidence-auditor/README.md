# Game Session Evidence Auditor

Verify captured-file sizes and SHA-256 hashes against an explicit manifest, then
check generic launch/exit receipts for missing or inconsistent session evidence.
The auditor reads only selected files. It never launches or monitors a game,
queries processes, repairs evidence or changes an installation.

Original source, tests, receipt/manifest formats and fictional examples use the
root [MIT license](../../LICENSE). Python **3.12+**, standard library only. No
game, account, mod manager, service or extra Python package is required.

## Quick start

Download current **main** with GitHub **Code → Download ZIP**, or clone the
[collection](https://github.com/TheOutlandsDev/outlands-game-tools). This module
was added after the historical v0.1.0 release assets. From the repository root
on Windows:

```powershell
py -3.12 -B tools/game-session-evidence-auditor/examples/create_example.py --destination ../outlands-session-demo
py -3.12 -B tools/game-session-evidence-auditor/session_auditor.py --root ../outlands-session-demo/clean --manifest ../outlands-session-demo/clean/manifest.json
py -3.12 -B tools/game-session-evidence-auditor/session_auditor.py --root ../outlands-session-demo/inconsistent --manifest ../outlands-session-demo/inconsistent/manifest.json --output ../outlands-session-demo/inconsistent-report.json
$LASTEXITCODE
```

On Linux/macOS replace `py -3.12` with `python3`. The generator requires a new
destination with an existing parent. It creates four tiny fictional session
folders. Expected exits: **0** for `clean`, **2** for `changed-capture`,
`missing-exit` and `inconsistent`. No real game was launched to create them.
The [worked examples](examples/README.md) explain each result.

## Audit your own captured evidence

Use an inactive, stable local evidence folder and a manifest preserved from a
trusted capture process. Close any writers first. Select the folder and manifest
explicitly; keep the new report **outside the evidence root**:

```powershell
py -3.12 -B tools/game-session-evidence-auditor/session_auditor.py --root 'D:/SessionEvidence/session-001' --manifest 'D:/SessionEvidence/session-001/manifest.json' --output 'D:/Reports/new-session-audit.json'
```

The manifest lists relative capture-file paths, expected byte counts and SHA-256
hashes, plus references for one launch receipt and one exit receipt. It may live
inside the evidence root or separately. Receipt references may be null to record
that a receipt was not provided. Neither receipts nor unlisted files are discovered
automatically. No folders are recursively inventoried.

The output parent must already exist. Existing reports, either input and the
evidence folder are never overwritten. Omit `--output` for JSON on standard
output. Rejected output paths create no file. An incomplete result may be written
to a valid external report destination; report/output errors fall back to small
incomplete JSON on stdout when possible.

See [manifest and receipt format](EVIDENCE-FORMAT.md) for exact fields and an
explicit manifest-authoring recipe. The program audits the original generic
schema here; it does not directly import the separate AGPL launcher, Process Exit
Observer snapshots, arbitrary game logs or other collectors' receipt formats.
Keep original collector output and document any conversion separately.

## What is checked

- Every listed capture/receipt file is streamed through SHA-256 and compared with
  both the declared size and digest. Missing files and ordinary mismatches are
  findings. Empty files can match their declared hash; their usefulness is not
  inferred. No capture contents are interpreted or exported.
- Receipts are interpreted **only after size and hash verification**. Changed
  receipts remain unverified. A verified file whose JSON/schema is malformed
  becomes an invalid-receipt finding.
- Valid launch/exit receipts are checked against the manifest session ID and
  against each other's process ID, executable label and UTC ordering. Duration
  is calculated from their declared timestamps; no live process is consulted.
- A nonzero exit code requests review. It is not automatically labeled a crash
  or assigned a cause. Signed and unsigned 32-bit-style exit codes are retained
  as declared. Zero does not prove that a game was playable or completed a test.
- Missing launch/exit references or files, and an empty capture selection, are
  explicit coverage findings. The tool does not guess that a missing exit means
  a crash; collection may have stopped, failed or omitted it.

`receipt_pair_consistent` describes matching receipt fields and ordered times.
A nonzero exit can have a consistent pair. Missing, unverified or invalid
receipts leave pair consistency unknown, rather than turning missing evidence
into an affirmative result. Valid-but-wrong session/identity fields make it false.
The [report format](REPORT-FORMAT.md) defines each field and finding code.

## Exits and trust limits

| Exit | Meaning |
|---|---|
| 0 | Complete supported audit; all selected files match and the receipt checks have no findings |
| 2 | Complete supported audit with missing, changed, invalid or inconsistent evidence to review |
| 1 | Incomplete: invalid manifest, unsupported path/object, read/stability failure or resource limit |

`--help` and `--version` are successful informational exits with plain text.
Check both the exit code and `complete` when scripting. An incomplete result
discards file inventory, session analysis and findings; partial hashes are not
presented as a finished audit. A complete result means the supported verification
ran to completion, including any evidence failures it found.

**Hashes compare selected bytes to the supplied manifest.** They do not
authenticate its author, a collector or the asserted session. Someone who can
replace both files and manifest can make new bytes agree. Receipts are unsigned
data assertions; matching PIDs, labels and times do not prove a real process was
observed, prevent PID reuse, identify an executable binary or attest gameplay,
multiplayer, causality or save safety. Clock accuracy is not verified.
Preserve a trusted original manifest and collector records; do not regenerate
expected hashes merely to make changed evidence pass.

No unlisted files, archive contents, screenshots, log messages or save formats
are inspected. The tool does not certify a whole session folder or installation.
If you need backups, see [Save Snapshot Verifier](../save-snapshot-verifier/README.md).
For process observation see [Process Exit Observer](../process-exit-observer/README.md),
whose separate format requires deliberate conversion before use here.

## Privacy and resource boundaries

Reports include the manifest session alias, relative filenames, expected/actual
sizes and hashes, receipt statuses, consistency booleans, declared elapsed
seconds and exit code. They omit raw captured content, selected absolute paths,
receipt PIDs, executable labels and absolute timestamps. Names, hashes, duration,
exit codes and even a chosen alias may still be private. Review before sharing.
The auditor makes no network requests, uploads or telemetry calls.

Only ordinary local files/folders are supported. Symlink/reparse ancestors, UNC,
device/stream paths and drive-relative paths are refused. Manifest paths use a
portable ASCII forward-slash subset, without parents or absolute paths.
References must be unique ignoring ASCII case and cannot have file/directory
prefix collisions. Different files with identical content or hardlinked names
can match; the auditor makes no independent-capture claim.

Hard limits: 2 MiB manifest JSON; 64 KiB per receipt; 256 MiB per capture;
1 GiB total declared evidence and separately 1 GiB actually read; 1,000 captures
plus up to two receipts; JSON container nesting depth 8; relative paths at most
1,024 characters and 32 components; 32 MiB cumulative serialized-metadata-plus-
overhead accounting; 8 MiB final JSON. Hash chunks are at most 1 MiB. Capture
payloads are streamed without retention; receipt JSON alone is buffered.
Accounting is not a guarantee of process resident memory. Limits can interact.

Identity, size and timestamp checks detect ordinary input changes, including a
missing selected file appearing during an audit. They do not provide an atomic
snapshot against a hostile concurrent writer. Use stable captured copies.

## Test and leave suggestions

```powershell
py -3.12 -B -m unittest discover -s tools/game-session-evidence-auditor/tests -v
```

Tests use original generated evidence, including binary hashing, missing and
changed captures, receipt trust/schema failures, identity/time/exit consistency,
privacy omissions, strict paths/JSON, resource ceilings, exclusive external
reports and source mutation. CI runs Windows/Linux on Python 3.12/3.13; native
link fixtures declare skips where unsupported. See [validation](../../VALIDATION.md).

[Suggest a feature](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_request.yml)
or [report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml).
Questions and suggestions are welcome without a code contribution. Select this
tool in the bug form; include OS/Python/tool versions, relevant finding/error
codes, expected versus actual behavior and a small fictional manifest/receipt
recipe. Replace private names and paths. Do not attach real logs, saves or game
assets. Useful requests include clearer receipt coverage and separately specified
collector adapters. See [contributing](../../CONTRIBUTING.md).

Original MIT collection filesystem/JSON/report guards informed this fresh generic
implementation. Standard behavior was checked against [Python hashing](https://docs.python.org/3.12/library/hashlib.html)
and [UTC datetime](https://docs.python.org/3.12/library/datetime.html) documentation.
No AGPL launcher/crash-audit implementation, third-party collector or game data
is copied or bundled.
