# Outlands File Audit

A read-only desktop app and CLI for one explicitly selected folder. Inventory
files, calculate SHA-256 checksums, and review duplicate-content candidates.
There is no deletion, quarantine, malware/cheat verdict, scheduled scan, account,
telemetry, network request or automatic upload. Original code, tests and examples
are [MIT licensed](LICENSE).

Use it to review a project folder before moving machines, identify identical
copies for **manual** investigation, or export a relative-path/hash inventory.
It is not a backup, restore tool, security detector or filesystem sandbox. It
does not compare two reports or restore missing files. For comparison workflows,
see the collection's separate [Mod Content Manifest](../mod-content-manifest/README.md).

## Requirements and quick start

Install a **JDK 17 or newer**, not just an old Java runtime. No Maven, Gradle,
Gson, Python or third-party Java dependency is needed. A display is needed only
for the Swing desktop window. Java 17 and 21 are the release's CI targets.
The JDK is obtained separately under its provider's terms; none is bundled.

Use the current repository main branch or its [source ZIP](https://github.com/TheOutlandsDev/outlands-game-tools/archive/refs/heads/main.zip).
Older collection release archives predate this app. Open a terminal in
`tools/file-audit`. You can copy this folder separately with its LICENSE,
documentation, tests and examples.

Check that these refer to the intended JDK:

```text
java -version
javac -version
```

If `javac` is missing or `java` reports an older version, follow your chosen JDK
vendor's installation/PATH instructions. The app does not install or reconfigure
Java. With JDK 17+, the simplest launch compiles the single source file in memory:

```text
java -Dfile.encoding=UTF-8 FileAudit.java
```

Or compile explicitly, then run:

```text
javac -encoding UTF-8 --release 17 -d bin FileAudit.java
java -cp bin FileAudit
```

The explicit UTF-8 option matters on older Windows JDKs with a different default
source encoding. `bin` is a local build directory excluded from source packaging.
No compiled class, executable, runtime or installer is distributed here.

## Desktop workflow

1. Click **Try demo (no file access)** to inspect a fictional three-file report
   with one duplicate candidate group. It reads no folder and is marked DEMO.
2. Click **Choose folder**, or enter a local folder. Nothing is scanned on launch.
3. Leave **SHA-256 and duplicate candidates** checked to read file contents for
   hashes. Uncheck it for a metadata-only inventory with no content-read calls.
4. Optionally supply final-extension filters, such as `.txt,.json`. Matching is
   case-insensitive; blank includes all names. Wildcards and multipart suffix
   matching are not supported: `.gz` matches the final extension of `file.tar.gz`.
   There are no automatic hidden/build/private-folder exclusions.
5. Review the visible limits, then click **Start audit**. Scanning runs off the
   Swing event thread. **Stop** requests cancellation and interrupts the worker;
   controls stay disabled until it returns. Closing the window also requests Stop.
6. Inspect **Files**, **Duplicate candidates**, and **Issues / exclusions**.
   Click column headings to sort. Scroll horizontally or resize columns to see
   full hashes/paths. The Files tab's text filter affects displayed rows only,
   not the scan, duplicate groups or exported report. Untrusted labels are rendered
   as plain text rather than Swing HTML.
7. **Save JSON report** creates one new local file outside the scanned folder.
   Its parent must already exist and pass the link checks. Existing reports are
   never replaced. Nothing is saved or shared automatically.

The previous result remains in memory if a new input cannot be audited. A new
successful/partial/cancelled scan replaces the displayed report; the app is not
a persistent report-history database. The demo and example inputs are fictional.

## Command line

The following commands assume the compiled `bin` version. The same options work
after `java -Dfile.encoding=UTF-8 FileAudit.java`.

```text
java -cp bin FileAudit --help
java -cp bin FileAudit --demo
java -cp bin FileAudit --root ../my-project --output ../project-audit.json
java -cp bin FileAudit --root ../my-project --ext .txt,.json --max-files 5000
java -cp bin FileAudit --root ../my-project --metadata-only
java -cp bin FileAudit --root ../my-project --max-file-mib 64 --max-hash-mib 512 --seconds 60
```

Choose your own existing input folder and a **new** output filename. Without
`--output`, JSON is written to standard output only. Prefer an explicit outside
output path; shell redirection into the input tree is outside the app's control
and can make the scan include that redirected file. Reports use UTF-8 JSON;
older shells may transcode redirected output, another reason to use `--output`.

| Option | Default | Supported bound |
| --- | ---: | --- |
| `--max-files` | 10,000 selected files | 1–20,000 |
| `--max-entries` | 20,000 directory/file entries | 1–100,000, including the root |
| `--max-file-mib` | 256 MiB | 1–10,240 MiB; hash reads only |
| `--max-hash-mib` | 2,048 MiB | 1–102,400 MiB total read budget |
| `--max-depth` | 64 | 1–128; root's children are depth 1 |
| `--seconds` | 300 | 1–3,600; cooperative elapsed-time limit |

Other bounds: at most 32 extensions, 2,048 characters per discovered relative
path, 2,000,000 accumulated discovered path characters, 1,000 detailed issues,
and a 16 MiB exported JSON report. Extra issues are counted in `issues_omitted`.
Entry/text/time limits can stop discovery; a truncated traversal is partial.
At a limit, which subset was reached can depend on filesystem enumeration order.

Per-file/total hash limits retain the file's observed metadata without a digest
and mark the report partial. A metadata-only scan ignores hash-byte limits but
still respects discovery/time limits. The time limit and cancellation are checked
between filesystem operations and read chunks: **they cannot forcibly interrupt
every blocked filesystem call**. Avoid network/mapped drives and concurrently
changing trees. UNC paths are rejected; mapped network drives are not reliably
identified. The UI stays responsive to Stop/close while its scan worker waits.

Exit codes: **0** complete within the stated scope, **2** partial, **130** a
returned cancellation, **1** input/access/report error. Ctrl+C usually terminates
the JVM and may not produce a report. Duplicate candidates alone are not errors.

## Interpret results and safety limits

- Candidate groups require matching **nonempty file length and SHA-256** among
  successfully hashed paths. This is useful evidence, not deletion advice.
  Same-name or same-size files alone do not form a group. Empty files are listed
  and may be hashed but do not form duplicate groups.
- When the provider supplies file identities, hard-link aliases are omitted from
  candidate groups and counted separately. When identities are unavailable,
  aliases can appear as different paths and the group's identity-availability
  flag is false. No physical-space saving is calculated or promised. Reflinks,
  compression, deduplication and copy-on-write storage are not analyzed.
- Existing symbolic links, junctions/reparse-like paths and special files are
  rejected/skipped using no-follow attributes and resolved-path comparisons.
  Skips and unreadable entries make the scan partial. A linked root is an input
  error. This is **best-effort checking on a quiet, trusted local tree**, not an
  atomic race-resistant security boundary. The app does not use a native sandbox
  or guarantee that an adversarial concurrent path swap can never escape scope.
- Before/after size, modification time, available file identity and channel-size
  checks discard detected changed-file digests. Preserving those metadata values
  can hide some mutations. There is no atomic snapshot across the folder, content
  authenticity check or filesystem freeze.
- File-level failures retain bounded relative-path reason codes, not raw exception
  strings. `complete` does not mean malware-free, backed up, fully recoverable or
  entitled to publish. Source content/names are not intentionally modified, though
  the OS may update access metadata when files are read.
- Export validates a new `.json` destination outside the input and uses exclusive
  creation. It does not create missing parent directories. A disk error or abrupt
  exit can leave an incomplete newly created report; saving is not an atomic
  all-or-nothing operation. The app does not delete that partial file for you.

Reports omit the absolute root, host/user identity, file contents and raw errors.
**Relative filenames, timestamps and hashes can still reveal private information.**
They are local by default. Review before sharing; there is no general-purpose
secret scanner or automatic redaction of filenames. Audit only folders you are
authorized to inspect. There is no consent bypass or administrator-mode workflow.

## Examples, tests, and suggestions

Follow the [worked fictional examples](examples/README.md) to create four new
input files and independently audit them. The file-free `--demo` report is also
included as [demo-report.json](examples/demo-report.json).

From this folder:

```text
javac -encoding UTF-8 --release 17 -Xlint:all -Werror -d bin FileAudit.java tests/FileAuditTests.java examples/CreateExample.java
java -cp bin FileAuditTests
java -cp bin FileAuditTests --gui
```

Tests create and clean only their own generated temporary fixtures. GUI tests
require a display; on Linux CI uses `xvfb-run -a java -cp bin FileAuditTests --gui`.
Native link fixtures skip if creation is unavailable, rather than pretending the
platform-specific check ran. See [validation details](VALIDATION.md) and
[source/dependency provenance](PROVENANCE.md).

[Suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
or [report a File Audit problem](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=file_audit.yml).
Ideas, accessibility feedback, documentation fixes and reproducible generated
examples are welcome; no code contribution is required. Include OS/JDK version,
scan limits, expected/actual behavior and a small fictional input layout. Do not
post private inventories, real filenames/paths, document contents or credentials.
