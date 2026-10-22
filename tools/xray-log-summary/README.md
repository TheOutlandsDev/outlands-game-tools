# X-Ray Log Summary

Summarize one stable local X-Ray engine log without printing the original log text. The report counts recognized fatal errors, script errors, audio warnings, missing treasure-item warnings, and other warnings. It also records a few startup, session, transport, connection, and shutdown text markers.

**This is a text-pattern inspector, not a diagnosis or a game test.** A transport marker does not establish a working server, connection, or co-op session. No recognized errors does not establish a healthy game. Categories can miss messages or match incidental text.

Original code, documentation, generated examples, and tests are covered by the collection's [MIT license](../../LICENSE). No game code, real logs, saves, assets, or third-party implementation is bundled. This independent implementation uses Python's standard library and has no pip dependencies.

## Requirements and installation

- Python **3.12 or 3.13**; use a supported Python release for your operating system.
- A stable local **physical file**, preferably a copy of an inactive log. Do not scan a log while the game is writing it.
- Windows or Linux. Network paths, devices, symlinks, Windows junctions/reparse points, and linked ancestors are refused.

Download or clone [the repository](https://github.com/TheOutlandsDev/outlands-game-tools), then open a terminal in `tools/xray-log-summary`. There is no installer or environment activation step.

Check Python on Windows:

```powershell
py -3.12 --version
```

Check Python on Linux:

```bash
python3 --version
```

## Try the generated example

The example generator writes a small synthetic text log to a **new file** in an existing directory. Keep generated files outside the source checkout when preparing a source-only release. Replace the example paths below with a local directory you control. Existing files are refused.

Windows PowerShell:

```powershell
py -3.12 -B .\examples\create_example.py --output "D:\ToolExamples\synthetic-xray.log"
py -3.12 -B .\xray_log_summary.py --log "D:\ToolExamples\synthetic-xray.log" --output "D:\ToolExamples\xray-summary.json"
$LASTEXITCODE
```

Linux:

```bash
python3 -B examples/create_example.py --output /tmp/synthetic-xray.log
python3 -B xray_log_summary.py --log /tmp/synthetic-xray.log --output /tmp/xray-summary.json
echo $?
```

The summary command returns **2**, because the generated example deliberately contains findings: one fatal-error line, one script-error line, and four warning lines. It has all five marker flags set. These are fabricated text observations, not an actual crash or connection. See [examples](examples/README.md).

## Inspect your log

```powershell
py -3.12 -B .\xray_log_summary.py --log "D:\LocalLogs\inactive-xray.log" --output "D:\LocalReports\xray-summary.json"
```

```bash
python3 -B xray_log_summary.py --log /mnt/games/local-logs/inactive-xray.log --output /tmp/new-xray-summary.json
```

The output parent directory must already exist and be physical. `--output` creates a **new UTF-8 JSON file**; it refuses existing destinations, the input itself, reserved/device names, and linked parents. The same JSON is printed to standard output. Omit `--output` to print JSON without creating a file. Prefer the explicit option to shell redirection, which can overwrite a file before Python starts. A failed output write can leave a partial new file; inspect or remove that file yourself before another attempt.

The input is opened read-only. The tool never edits logs, launches a game, watches processes, tails files, deletes files, contacts a network, or uploads reports.

### Encoding and limits

UTF-8 is the default; an initial UTF-8 BOM is accepted. For a log known to use Windows Cyrillic encoding:

```powershell
py -3.12 -B .\xray_log_summary.py --log "D:\LocalLogs\inactive-xray.log" --encoding cp1251
```

Choose the encoding from the file's provenance, not simply whichever avoids an error. CP1251 accepts many byte values that are invalid UTF-8, so the wrong choice may silently alter the meaning of text. Patterns remain English regardless of encoding; localized words are not translated.

| Option | Default | Meaning |
| --- | --- | --- |
| `--max-bytes` | `33554432` (32 MiB) | Refuse a larger file before scanning; stop if a file grows beyond the read budget. |
| `--max-line-bytes` | `65536` (64 KiB) | Maximum bytes in one line, including its newline if present. |
| `--max-lines` | `500000` | Maximum successfully decoded lines to classify. |
| `--encoding` | `utf-8` | Strict `utf-8` or `cp1251`; no replacement characters are inserted. |
| `--output` | none | Exclusively create a JSON report in an existing directory. |

Each numeric limit must be at least 1 and smaller than the platform's `sys.maxsize`. Raise a limit only for a trusted file when the extra resource use is acceptable. The tool reads lines incrementally, does not load the whole log, and retains at most 1,000 line numbers per category. Counts remain exact for the scanned portion when the line-number list is capped. Very large user-selected limits can still permit large memory or CPU use; this is not a sandbox for hostile inputs.

Oversized files, overlong lines, extra lines beyond the cap, invalid text, zero-byte logs, binary NUL characters, missing/unreadable inputs, linked paths, and detected input changes make the report **incomplete**. After a stopped scan, later lines have not been checked. A report with findings can also be incomplete; inspect `summary.complete` first.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Complete nonempty scan with no recognized fatal, script, or warning findings. Marker observations alone do not change this code. |
| `2` | Complete scan with at least one recognized fatal-error, script-error, or warning line. A warning is a text finding, not a claim of corruption. |
| `1` | Invalid arguments, incomplete scan, or report-write failure, even if earlier lines contained findings. |

## What gets counted

Patterns are case-insensitive. All matches on one line count once per category, rather than once per repeated word. A line can contain both fatal and script categories and any marker categories. Warning categories are mutually exclusive; fatal/script lines do not also count as warnings.

| Code | Recognition rule |
| --- | --- |
| `fatal_error` | Words `FATAL ERROR`, allowing whitespace between them. |
| `script_error` | Bracketed `[SCRIPT ERROR]` or words `SCRIPT RUNTIME ERROR`. |
| `audio_warning` | A warning line containing `sound`, `audio`, `OpenAL`, `sampling`, `sample rate`, or `frequency`. |
| `missing_treasure_item_warning` | A warning line containing `treasure`, `item`/`items`, and `missing`, `not found`, `does not exist`, or `unknown`; audio classification has priority. |
| `other_warning` | Another line containing the word `warning` or beginning with optional whitespace and `!`. |
| `startup_marker` | `starting engine`, `initializing engine`, or `engine startup`. |
| `session_marker` | `starting new game`, `load saved game`, or `game loaded`. |
| `transport_marker` | `GameNetworkingSockets` or `xrRazom`. |
| `connection_marker` | `connected to server` or `client connected`. |
| `shutdown_marker` | `engine shutdown` or `destroying engine`. |

The `!` warning convention is broad. An informational line starting with `!` may be classified as a warning. Fatal details on following lines, stack traces, asset identities, dates, and arbitrary error words are not parsed. This deliberate scope helps keep reports free of extracted source identifiers.

## Report privacy and limitations

Read the [report format](REPORT-FORMAT.md) for exact field meanings. Reports omit original text, source filenames/paths, timestamps, raw exceptions, player names, asset/item identifiers, network endpoints, and credentials because **no source strings are copied into the report at all**. They contain static codes and numeric observations rather than edited source excerpts.

This is not a general redactor. Counts, line positions, selected encoding, and marker context may still reveal information about a session. Review the JSON before posting it. Never attach a raw game log simply because this tool produced a safe-looking summary. Missing markers are not proof that a session feature was absent.

Input identity, size, and modification time are checked around the read. These checks catch some changes, not every race or same-size edit with restored metadata. Use a stable physical copy. Classification only covers the decoded portion and documented patterns; it establishes no root cause or gameplay result.

## Test the tool

From this directory:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

```bash
python3 -B -m unittest discover -s tests -v
```

Tests generate temporary text fixtures. They cover late/repeated findings, category precedence, all marker types, privacy with fabricated sensitive values, encodings, byte/line limits, exit precedence, input immutability, exclusive output, and native linked-path refusal. Native symlink and Windows junction tests explicitly skip where the account/sandbox cannot create those fixtures; the junction test is Windows-only and is skipped on Linux. Read the test results to distinguish executed linked-path checks from skips. Tests do not run the game or inspect installed logs.

## Bugs and suggestions

Use [Report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml) and select **X-Ray Log Summary**, or [Suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml).

Suggestions for clearer category definitions, additional synthetic fixtures, and portability are welcome. Include the tool version (`--version`), OS, Python version, expected behavior, and the summary's static error/category codes. For a new pattern, create a short fabricated example that reproduces it. Review everything you share; do not include real account/player names, paths, addresses, credentials, game assets, or unreviewed raw logs. This tool makes no claim of affiliation with game developers or mod projects.
