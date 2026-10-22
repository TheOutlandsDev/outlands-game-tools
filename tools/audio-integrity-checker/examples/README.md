# Original generated audio example

`create_example.py` synthesizes tiny original PCM WAV files and deliberately
invalid test bytes. It uses only Python's standard library. No game or
third-party audio is stored in this example or copied from your installation.
Generated files are local runtime output, rather than checked-in audio assets.

Run commands from `tools\audio-integrity-checker` after completing the
[local environment setup](../README.md#install-in-a-local-environment).
The generator requires a **new** destination whose parent already exists; it
refuses parent traversal, network paths and linked/reparse ancestors. It does
not merge into or replace an existing folder. If creation fails partway, it
may leave a partial new folder: choose a new destination for a retry.

## PowerShell walkthrough

```powershell
$demo = Join-Path $env:TEMP ('outlands-audio-demo-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B examples\create_example.py --destination $demo
$LASTEXITCODE
```

Expect generator exit **0** and this layout:

```text
source/
  valid.wav                 original mono PCM16, 8000 Hz, 80 frames
  empty.wav                 original valid WAV header, zero frames
  broken.ogg                original bytes that are not a valid Ogg stream
  ignored.txt               ignored non-audio suffix
mo2/
  mods/
    AudioHigh/shared.wav    original valid WAV
    AudioLow/shared.wav     original invalid WAV bytes
  base/base.wav             original valid WAV
  overwrite/shared.wav      original valid WAV
  profile/modlist.txt       +AudioHigh before +AudioLow (first is highest)
```

The files are data for inspection; playback is unnecessary. The short WAV's
sample rate/channel count are merely example metadata, rather than an engine
compatibility recommendation.

### Source-folder findings

```powershell
.\.venv\Scripts\python.exe -B audio_integrity.py `
  --source-dir (Join-Path $demo 'source') `
  --sha256 `
  --output (Join-Path $demo 'source-report.json')
$LASTEXITCODE
```

Expect exit **2** for intentional findings, with `summary.complete` true:

| File | Expected status | Reason |
|---|---|---|
| `valid.wav` | `DECODE_PASS` | Positive, finite decoded frames match the decoder's reported total. |
| `empty.wav` | `DECODE_ANOMALY` | `issues` contains `empty_audio`. |
| `broken.ogg` | `DECODE_ERROR` | `code` is `decode_failed`. |
| `ignored.txt` | No file record | Its suffix is outside the selected audio extensions. |

The summary has `loose_audio_files: 3`, `effective_files: 3`, `checked_files: 3`,
`passes: 1`, `decode_errors: 1`, `anomalies: 1`, and `skipped_files: 0`.

```powershell
$sourceReport = Get-Content -LiteralPath (Join-Path $demo 'source-report.json') -Raw | ConvertFrom-Json
$sourceReport.summary
$sourceReport.files | Select-Object path, provider, status, code, issues
```

### MO2 winners and masked copies

```powershell
.\.venv\Scripts\python.exe -B audio_integrity.py `
  --mods-dir (Join-Path $demo 'mo2\mods') `
  --modlist (Join-Path $demo 'mo2\profile\modlist.txt') `
  --base-dir (Join-Path $demo 'mo2\base') `
  --overwrite-dir (Join-Path $demo 'mo2\overwrite') `
  --output (Join-Path $demo 'mo2-report.json')
$LASTEXITCODE
```

Expect exit **0**, with `summary.complete` true, four loose copies, two
effective files, two passes and two shadowed copies. `base.wav` comes from
`<base>`. `shared.wav` comes from `<overwrite>`; its `file_conflicts` record
lists `<overwrite>`, `AudioHigh`, then `AudioLow` in priority order.

```powershell
$mo2Report = Get-Content -LiteralPath (Join-Path $demo 'mo2-report.json') -Raw | ConvertFrom-Json
$mo2Report.summary
$mo2Report.files | Select-Object path, provider, status
$mo2Report.file_conflicts | ConvertTo-Json -Depth 6
```

The invalid `AudioLow/shared.wav` is masked and therefore not decoded. To see
its own failure, inspect that provider as a source tree separately:

```powershell
.\.venv\Scripts\python.exe -B audio_integrity.py `
  --source-dir (Join-Path $demo 'mo2\mods\AudioLow') `
  --output (Join-Path $demo 'lower-provider-report.json')
$LASTEXITCODE
```

Expect exit **2**, one `DECODE_ERROR`. This demonstrates that an effective-file
pass is not a claim that every installed provider copy passed. The conflict
list itself compares providers, rather than file content or sound quality.

### Repeat without replacing a report

Rerunning a checker command with the same output filename returns **1** and
leaves the original report intact. Choose a fresh name, such as
`source-report-002.json`, or omit `--output` to print JSON to stdout.
Rerunning the generator with the same destination also fails rather than
merging new inputs into it. Use a fresh `$demo` value for a fresh fixture.

## Linux/macOS shell equivalent

From the tool directory, use an existing local temporary parent with no linked
ancestors. If your OS's temporary path is a symlink, choose an ordinary local
folder instead.

```bash
demo_parent="$(mktemp -d)"
demo="$demo_parent/inputs"
.venv/bin/python -B examples/create_example.py --destination "$demo"
.venv/bin/python -B audio_integrity.py \
  --source-dir "$demo/source" \
  --sha256 \
  --output "$demo/source-report.json"
echo "$?"  # expected 2: deliberate findings
.venv/bin/python -B audio_integrity.py \
  --mods-dir "$demo/mo2/mods" \
  --modlist "$demo/mo2/profile/modlist.txt" \
  --base-dir "$demo/mo2/base" \
  --overwrite-dir "$demo/mo2/overwrite" \
  --output "$demo/mo2-report.json"
echo "$?"  # expected 0
```

These are bounded toy inputs, not a codec coverage test. The repository test
suite additionally exercises other formats, metadata/anomaly handling, caps,
path restrictions, changes, report handling and dependency failure behavior.
The [report reference](../REPORT-FORMAT.md) explains each field. A successful
example confirms this local workflow; it does not establish gameplay
compatibility or detect every possible media corruption.
