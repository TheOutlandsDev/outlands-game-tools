# Audio Integrity Checker

Inspect loose audio files for decoder failures, empty audio, non-finite samples,
and decoded-frame inconsistencies before investigating a game sound problem.
Check one source folder, or select effective loose files from a saved Mod
Organizer 2 profile and see which providers overlap.

The checker reads audio through the separately installed SoundFile/libsndfile
decoder and processes samples in blocks. **It never plays, repairs, converts,
deletes, or uploads inspected audio.** It does not start a game or change MO2's
profile. This independent utility grew out of local game-mod troubleshooting;
it is not an official game or MO2 project.

Python **3.12 or newer** is required. The supported dependency set is
**SoundFile 0.13.1** and **NumPy 2.2.6**, pinned in `requirements.txt`. No game,
modpack, administrator rights, or MO2 plugin installation is required.
The checker rejects other SoundFile/NumPy versions rather than silently using
an untested dependency set.

**A successful decode is limited evidence.** It does not establish that every
byte is valid, that all corruption is absent, or that a game/OpenAL version will
accept or correctly play the file. The tool does not inspect audio inside
archives or diagnose scripts that request a missing sound. Read the
[scope and limits](#what-a-pass-does-and-does-not-mean) before interpreting a
report.

## Install in a local environment

Download this repository using **Code → Download ZIP** and extract it outside
your game, Mods, and Overwrite folders. Keep the repository's root `LICENSE`
when redistributing the tool. Open PowerShell in `tools\audio-integrity-checker`:

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
.\.venv\Scripts\python.exe -B audio_integrity.py --help
.\.venv\Scripts\python.exe -B audio_integrity.py --version
```

The install command downloads the pinned packages and their dependencies from
the package index configured for your Python environment. `--only-binary=:all:`
requires compatible wheels and avoids an unexpected native source build. If
there is no matching wheel, use a supported CPython version/architecture and
check the official [SoundFile installation guide](https://python-soundfile.readthedocs.io/en/0.13.1/#installation)
and [NumPy installation guide](https://numpy.org/install/). The pinned releases
are [SoundFile 0.13.1](https://pypi.org/project/soundfile/0.13.1/) and
[NumPy 2.2.6](https://pypi.org/project/numpy/2.2.6/).

Use the virtual environment's Python directly; activation and PowerShell
execution-policy changes are unnecessary. If you use `python` instead of the
`py` launcher, first confirm that it is Python 3.12 or newer. `-B` prevents
Python bytecode caches beside the tool source.

On Linux or macOS, from the same extracted tool directory:

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python -B audio_integrity.py --help
```

Once dependencies are installed, scanning local files needs no network
connection. The checker does not download codecs or other runtimes during a
scan. SoundFile wheels may supply libsndfile; native codec support can differ
between platforms/installations, so inspect the report's runtime metadata when
comparing results.

## Try the original example first

The [example walkthrough](examples/README.md) generates tiny original test
files in a **new** local folder. No game audio is included or required. From
PowerShell in the tool directory:

```powershell
$demo = Join-Path $env:TEMP ('outlands-audio-demo-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B examples\create_example.py --destination $demo
.\.venv\Scripts\python.exe -B audio_integrity.py `
  --source-dir (Join-Path $demo 'source') `
  --output (Join-Path $demo 'source-report.json')
$LASTEXITCODE
```

Expect exit **2**: the valid WAV passes, an intentionally invalid OGG fails to
decode, and a valid WAV header with zero frames is reported as empty audio. A
`.txt` file is ignored. These are deliberate findings, not installation
failures. The example also demonstrates MO2 priority, including a masked broken
copy that does not affect the selected winning audio.

```powershell
$report = Get-Content -LiteralPath (Join-Path $demo 'source-report.json') -Raw | ConvertFrom-Json
$report.summary
$report.files | Select-Object path, provider, status, code, issues
```

Use a new demo directory or report filename when repeating the commands. The
generator refuses existing destination paths; the checker refuses existing
report files.

## Check a source folder

Replace these example paths with your own. The output's parent directory must
already exist, and its filename must be new and outside the input directory.

```powershell
.\.venv\Scripts\python.exe -B audio_integrity.py `
  --source-dir 'D:\MyMod\audio' `
  --sha256 `
  --output 'D:\Reports\audio-check-001.json'
$LASTEXITCODE
```

The recursive scan selects case-insensitive `.wav`, `.ogg`, `.flac`, `.aif`,
and `.aiff` suffixes. A suffix selects a candidate; it is not proof of its
actual container or encoding. Successful decoding depends on the installed
libsndfile's support. Unsupported files do not become passes.

`--sha256` additionally records hashes of selected file bytes for comparing
observations; it is off by default. Hashing does not establish authorship,
licensing, codec validity, or that differently named providers have equal
content. Without `--output`, JSON goes to standard output. Prefer `--output`
when saving: shell redirection such as `> report.json` can overwrite a file
**before** the checker runs. Never redirect into an input file or input folder.

## Check an MO2 profile

Find the intended MO2 instance's configured **Mods**, **Profiles**, and
**Overwrite** paths in settings. The saved profile's `modlist.txt` is inside
its Profiles subfolder. These paths need not be beside MO2; see
[MO2's Paths documentation](https://github.com/ModOrganizer2/modorganizer/wiki/Settings-window#paths).

```powershell
.\.venv\Scripts\python.exe -B audio_integrity.py `
  --mods-dir 'D:\MO2\mods' `
  --modlist 'D:\MO2\profiles\My Profile\modlist.txt' `
  --base-dir 'D:\Game' `
  --overwrite-dir 'D:\MO2\overwrite' `
  --output 'D:\Reports\audio-profile-001.json'
$LASTEXITCODE
```

`--mods-dir` and `--modlist` must be supplied together. They cannot be combined
with `--source-dir`. Base and Overwrite are optional inputs in MO2 mode; omitting
a provider can change both the selected file and the findings.

All supplied roots must describe the **same virtual data root**. For example,
if a mod contains `gamedata\sounds\example.ogg`, the base folder must contain
`gamedata` too: choose `D:\Game`, rather than `D:\Game\gamedata`. If a mod
deploys `sounds\example.ogg` directly, select the base folder containing
`sounds`. The checker cannot infer or fix misaligned folder layouts.

Priority is highest first:

1. Supplied Overwrite directory.
2. Enabled `+` entries in native saved `modlist.txt` order, first entry highest.
3. Supplied base loose-data directory.

Only the winning copy of a relative audio path is decoded. The report lists
overlapping providers and the winner; an overlap is **not** by itself an error
or proof that their contents differ. A masked broken copy is not decoded in
this effective-file report. Use source-folder mode on that mod separately if
you want to inspect its losing copies too.

Disabled `-` entries and separator rows are not enabled mod providers. MO2's
hidden `.mohidden` paths are excluded. Native saved order differs from the
common ascending Priority display in MO2: do not alphabetically sort or reverse
the modlist. See the [MO2 profile writer](https://github.com/ModOrganizer2/modorganizer/blob/master/src/profile.cpp)
and [Overwrite documentation](https://github.com/ModOrganizer2/modorganizer/wiki/Troubleshooting#there-are-files-in-your-overwrite-mod-directory).

Keep the saved profile and input files stable while checking. Close MO2 or stop
changing them. The tool detects certain file/modlist changes; it does not make
an atomic snapshot. Symlinks, junctions/reparse points, network/device paths,
unsafe mod names, ambiguous case matches, unreadable inputs, and unsupported
entries are refused or make the scan incomplete. Input roots must be separate
and non-overlapping, with the modlist outside them. An empty effective audio
selection is incomplete. Relative-path matching uses Python's Unicode casefold
approximation, rather than exact NTFS/Win32 filename collation; verify unusual
Unicode filename cases in MO2.

## Options and exit codes

| Option | Purpose |
|---|---|
| `--source-dir PATH` | Inspect one loose source tree. Exclusive with MO2 mode. |
| `--mods-dir PATH` | Directory containing installed mod folders; requires `--modlist`. |
| `--modlist PATH` | Native saved MO2 profile file; requires `--mods-dir`. |
| `--base-dir PATH` | Optional lowest-priority loose data folder in MO2 mode. |
| `--overwrite-dir PATH` | Optional highest-priority loose folder in MO2 mode. |
| `--output PATH` | Exclusively create a new JSON report outside all inputs. Parent must exist; linked output ancestors and replacement are refused. Default: stdout. |
| `--sha256` | Include SHA-256 of selected audio-file bytes. Off by default. |
| `--max-file-bytes N` | Per-file byte limit. Default `268435456` (256 MiB). |
| `--max-frames N` | Per-file audio-frame limit. Default `20000000`; a frame includes one sample per channel. |
| `--max-channels N` | Per-file channel limit. Default `32`; accepted range `1` through `256`. |
| `--help`, `--version` | Show usage or tool version without scanning. |

Limits must be positive integers below Python's platform `sys.maxsize`, with
the additional channel maximum shown above. A limit refusal makes the scan incomplete;
it is not a decoder finding. Increase a limit only when you intend to inspect
that larger input. Block processing limits ordinary sample-buffer allocation,
but native decoding and metadata parsing are not a malicious-input sandbox or
a hard wall-clock/memory limit.

| Exit | Meaning | Next step |
|---|---|---|
| `0` | Complete scan with no reported decoding/integrity findings. | Read the scope limits before drawing game conclusions. |
| `2` | Complete scan with at least one decoder error or integrity anomaly. | Inspect the reported local files and reproduce with permitted toy inputs. |
| `1` | Invalid/incomplete scan, dependency failure, limit/unsafe input, changed file, or output failure. | Resolve the reported problem and rerun to a new output file. |

Exit `1` takes precedence over `2` if a scan finds both a decoder problem and
an incomplete input. Check the process exit code and `summary.complete`; a
failure can occur before any report can be written.

## Read a report

See [REPORT-FORMAT.md](REPORT-FORMAT.md) for field definitions and status
meanings. A useful first view is:

```powershell
$report = Get-Content -LiteralPath 'D:\Reports\audio-check-001.json' -Raw | ConvertFrom-Json
$report.runtime
$report.summary
$report.files | Where-Object status -ne 'DECODE_PASS' | Select-Object path, provider, status, code, issues
$report.file_conflicts
$report.errors
$report.warnings
```

Reports omit absolute roots, embedded audio tags, sample data, source/audio
copies, and raw native decoder error text. **Relative filenames, mod names,
optional hashes, metadata and counts can still disclose private information.**
Review before posting a report. Share the original generated example or a
small reproduction you own/have permission to publish, rather than game audio,
commercial assets, full modpacks, saves, or raw logs.

## What a pass does and does not mean

The checker opens the selected file, records decoder-reported metadata, and
decodes sample blocks to check for reported errors, non-finite sample values,
empty audio and disagreement with reported frame counts. A pass describes
these checks against that decoder and those observed bytes.

It does not promise strict validation of every container byte, detect every
truncation or corruption, require every trailing byte to be consumed, validate
tags/loop points/game-specific metadata, detect clipping or audible glitches,
or prove an audio format is appropriate for the game. Some codecs may tolerate
damage or conceal it. Sample rates and stereo/multichannel audio are recorded;
they are not automatically classified as bad. A game can impose requirements
that this generic decoder does not know.

The MO2 model covers selected **loose** paths only. It does not mount MO2's
live VFS, unpack `.db`/`.ba2`/`.bsa` or other archives, parse sound-reference
scripts, or prove an asset is missing when archived data is unknown. It cannot
diagnose device drivers, speaker configuration, OpenAL setup, or actual
gameplay. An independent game/runtime test is still needed for those claims.

SoundFile/libsndfile are native parsers. Resource caps and path checks reduce
ordinary mistakes; they do not make untrusted, intentionally hostile media safe
to decode. Keep decoder dependencies current when evaluating such inputs.

## Troubleshooting and removal

- **Missing dependencies:** run the pinned install command with the same
  environment Python used for the checker. Installing into another Python
  environment will not satisfy this one.
- **No compatible wheel:** confirm Python version/architecture, use the
  official package links above, and keep `--only-binary=:all:` if you want to
  avoid a native build. Do not install a similarly named substitute.
- **A decoder error:** confirm the selected provider and format metadata.
  Compare the original with a known good copy using your own permitted files.
  A decoder failure alone does not identify the game's root cause.
- **No audio selected:** verify the input root, enabled profile, relative
  layout and suffixes. An archive-only collection is outside this scan.
- **Skipped files/incomplete report:** inspect `errors`, `warnings` and the
  file status/code. Check caps, path restrictions, permissions and input
  stability. Do not interpret the checked subset as a full pass.
- **Existing/unsafe output refused:** choose a new report filename in an
  existing local folder outside all inputs. Do not delete an input to make
  room for a report, and avoid shell redirection into scanned folders.

To uninstall, close terminals using the tool and remove its extracted folder
and `.venv` using your normal file manager. Delete only the reports/example
folder you created if you no longer need them. The checker installs no game
files, service, scheduled task, or MO2 plugin to remove.

## Suggestions, bug reports and contributions

[Open a suggestion or bug report](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new/choose).
Name **Audio Integrity Checker** in the affected module/area field. Ideas
for clearer reports, additional checks, supported formats and documentation are
welcome; you do not need finished code to suggest an improvement. Explain what
you expected and how the tool could help your workflow.

For a bug, include the tool/Python/SoundFile/libsndfile versions, operating
system, relevant command with private paths replaced, exit code, and a minimal
reproduction you may publish. State whether the issue occurred in source or
MO2 mode. Review any report before attaching it. See the repository's
[contribution guide](../../CONTRIBUTING.md) for pull requests and conduct.

To run the automated checks locally, from this tool directory after installing
the pinned dependencies:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

The tests generate their own original audio in temporary folders. They cover
actual supported codec decoding, metadata/anomaly findings, provider priority,
read-only input preservation, resource limits, report refusal and dependency
failures. Some link-specific checks depend on operating-system support; read
the test output for skips. Passing tests establish these tested behaviors,
rather than gameplay compatibility or exhaustive codec security.

## License and third-party components

The original checker, documentation, tests and example-generator source are
MIT licensed under the repository's [LICENSE](../../LICENSE). The example
generator synthesizes original toy audio locally; no game audio is distributed
here. Running the tool does not grant redistribution rights to scanned files.

SoundFile and NumPy are separately installed third-party dependencies under
their own BSD-style licenses; libsndfile has its own LGPL license. Their
copyrights and applicable terms remain in effect. No native decoder payload or
third-party audio is vendored in this tool. See
[THIRD-PARTY.md](../../THIRD-PARTY.md) for notices and upstream links.
