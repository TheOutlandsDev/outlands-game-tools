# Lua Syntax Checker

Compile loose `.lua` and `.script` files to find syntax errors before starting
a game. Inspect a plain source directory, or select the effective loose scripts
from a saved Mod Organizer 2 profile. The inspector **does not execute scanned
Lua chunks** and does not change their files.

Python **3.12 or newer** and the separately installed **Lupa 2.8** binding are
required. Choose LuaJIT 2.1 (the default), Lua 5.1, or Lua 5.4 to match the
syntax you intend to check. No game, modpack, administrator rights, or MO2
plugin installation is required. This independent utility grew out of local
S.T.A.L.K.E.R. mod troubleshooting; it is not an official game or MO2 project.

**A syntax pass is not a compatibility or gameplay pass.** A script can compile
and still fail on missing functions, data, modules, engine extensions, or runtime
behavior. Read the [limits](#what-a-pass-does-and-does-not-mean) before treating a
report as evidence about a game.

## Install in a local environment

Download this repository using **Code → Download ZIP** and extract it outside
your game, mods, and Overwrite folders. Keep the repository's root `LICENSE`
when redistributing the tool. Open PowerShell in `tools\lua-syntax-checker`.

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
.\.venv\Scripts\python.exe -B lua_syntax.py --help
.\.venv\Scripts\python.exe -B lua_syntax.py --version
```

The install command downloads Lupa from the package index configured for your
Python environment. `requirements.txt` pins version 2.8; `--only-binary=:all:`
requires a matching wheel and avoids an unexpected source-build toolchain.
If no wheel matches your Python version or architecture, use a supported
CPython installation and consult [Lupa's installation documentation](https://github.com/scoder/lupa#installation).
Do not install an unrelated package with a similar name. The official release
is [Lupa 2.8 on PyPI](https://pypi.org/project/lupa/2.8/).

Activation is optional: the commands use the environment's Python directly,
so PowerShell execution policy does not need to be changed. If your machine
uses `python` rather than the `py` launcher, use that command to create the
environment after confirming it is Python 3.12 or newer. `-B` prevents Python
from writing bytecode caches beside the tool source.

On Linux or macOS, from the same extracted tool directory:

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python -B lua_syntax.py --help
```

Once dependencies are installed, checking local files needs no network
connection. The tool does not download runtimes, launch games, or enable mods.

## Try the original example first

The [example guide](examples/README.md) creates toy inputs in a **new** folder,
without requiring or copying game files. From PowerShell in the tool directory:

```powershell
$demo = Join-Path $env:TEMP ('outlands-lua-demo-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B examples\create_example.py --destination $demo
.\.venv\Scripts\python.exe -B lua_syntax.py `
  --source-dir (Join-Path $demo 'source') `
  --output (Join-Path $demo 'source-report.json')
$LASTEXITCODE
```

Expect exit code **2**: three scripts are checked, two pass, and
`broken.script` has one intentional syntax error. The valid `noexecute.lua`
contains a top-level runtime error and an infinite loop. Compiling it succeeds
because the checker never invokes the compiled chunk. The `.txt` file is
ignored. Use a new demo directory or output filename if you repeat the commands;
existing report files are deliberately refused.

```powershell
$report = Get-Content -LiteralPath (Join-Path $demo 'source-report.json') -Raw | ConvertFrom-Json
$report.summary
$report.scripts | Select-Object path, provider, status, line, code
```

## Check a source folder

Replace these sample paths with your own. The output's parent directory must
already exist, and the output file must be new and outside the input folder.

```powershell
.\.venv\Scripts\python.exe -B lua_syntax.py `
  --source-dir 'D:\MyMod\scripts' `
  --runtime luajit21 `
  --output 'D:\Reports\lua-check-001.json'
$LASTEXITCODE
```

The scan recursively considers loose files with case-insensitive `.lua` or
`.script` extensions. Other suffixes and archives are outside the scan. This is
a **byte-oriented** check: it reads source bytes rather than decoding the entire
file as UTF-8. One leading UTF-8 byte-order mark is removed before compilation;
the report retains the original byte count/hash and a separate parser-input
hash. Binary Lua bytecode and NUL-containing inputs are refused rather than
loaded. Files above the size limit are skipped and make the scan incomplete.

Without `--output`, the JSON report goes to standard output. Prefer the tool's
`--output` option when saving: shell redirection such as `> report.json` can
truncate an existing file **before** the tool checks anything. Never redirect
output into a source file, modlist, or any input directory.

## Check an MO2 profile

In the intended MO2 instance, find the configured **Mods**, **Profiles**, and
**Overwrite** paths in settings. The saved profile's `modlist.txt` is inside its
folder under Profiles. Do not assume those folders live beside MO2; see
[MO2's Paths documentation](https://github.com/ModOrganizer2/modorganizer/wiki/Settings-window#paths).

```powershell
.\.venv\Scripts\python.exe -B lua_syntax.py `
  --mods-dir 'D:\MO2\mods' `
  --modlist 'D:\MO2\profiles\My Profile\modlist.txt' `
  --base-dir 'D:\Game' `
  --overwrite-dir 'D:\MO2\overwrite' `
  --runtime luajit21 `
  --output 'D:\Reports\lua-profile-001.json'
$LASTEXITCODE
```

`--mods-dir` and `--modlist` must be supplied together. `--source-dir` selects
the other mode and cannot be combined with MO2 inputs. `--base-dir` and
`--overwrite-dir` are optional MO2 inputs. Include them when those loose files
are relevant to your game; omitting a provider can change both the effective
file and the result.

The relative paths must refer to the **same virtual data root**. In the command
above, mods and Overwrite are assumed to contain `gamedata\scripts\name.script`;
the base folder must contain `gamedata` too, so it is `D:\Game`, rather than
`D:\Game\gamedata`. If your mods instead deploy `scripts\name.script` directly,
select the base folder containing `scripts`. The tool cannot infer or repair a
misaligned layout.

The priority model, highest first, is:

1. Supplied Overwrite directory.
2. Enabled `+` entries in saved native `modlist.txt` order, first entry highest.
3. Supplied base loose-data directory.

Only the winning loose copy of a relative script path is compiled. A masked
broken copy does not cause a syntax error in this effective-file report.
Disabled `-` entries and separator rows are not enabled providers. MO2's hidden
`.mohidden` paths are excluded. This uses the native saved file order, which
differs from the common ascending Priority display in MO2; do not reverse or
alphabetically sort the modlist. See the
[MO2 profile writer](https://github.com/ModOrganizer2/modorganizer/blob/master/src/profile.cpp)
and [Overwrite documentation](https://github.com/ModOrganizer2/modorganizer/wiki/Troubleshooting#there-are-files-in-your-overwrite-mod-directory).

Use a saved, stable profile. Close MO2 or stop changing its profile and inputs
while scanning. The checker rereads effective files and the modlist to detect
changes; it does not obtain an atomic filesystem snapshot. Symlinks, junctions,
other reparse points, UNC/network/device paths, unsafe mod names, ambiguous
case matches, unsupported entries, and unreadable inputs are rejected or make
the scan incomplete. It does not silently follow them to another location.
Source roots must be separate and non-overlapping, and the modlist must be
outside those roots. A scan with no effective scripts is incomplete. Relative
path matching uses Python's Unicode casefold approximation rather than exact
NTFS/Win32 collation; confirm unusual Unicode filename cases in MO2.

## Options and exit codes

| Option | Purpose |
|---|---|
| `--source-dir PATH` | Recursively inspect one loose source tree. Exclusive with MO2 mode. |
| `--mods-dir PATH` | MO2 folder containing one directory per installed mod; requires `--modlist`. |
| `--modlist PATH` | Saved native MO2 profile `modlist.txt`; requires `--mods-dir`. |
| `--base-dir PATH` | Optional lowest-priority loose data folder in MO2 mode. |
| `--overwrite-dir PATH` | Optional highest-priority loose folder in MO2 mode. |
| `--runtime luajit21\|lua51\|lua54` | Select Lupa's VM module. Default: `luajit21`. |
| `--output PATH` | Exclusively create a new JSON file, outside all inputs. Parent must exist; no linked output ancestors or replacement. Default: stdout. |
| `--max-script-bytes N` | Maximum bytes per effective script. Default `2097152` (2 MiB); must be positive and below the platform's `sys.maxsize`. Oversize scripts make the scan incomplete. |
| `--version` | Show the tool version. |
| `--help` | Show command help. |

| Exit code | Meaning |
|---|---|
| `0` | Complete scan; every checked effective script compiled. |
| `2` | Complete scan with at least one syntax error. |
| `1` | Invalid input, missing/unsupported dependency, incomplete scan, or report-write error. A partial report may contain both syntax errors and skipped files. |

Read `$LASTEXITCODE` immediately after the checker in PowerShell, or `$?` in a
POSIX shell. A report with `summary.complete: false` is incomplete regardless of
how many scripts passed. Errors before report construction may produce only a
terminal message. The [report reference](REPORT-FORMAT.md) explains every field.

## What a pass does and does not mean

Lupa exposes multiple upstream Lua implementations. `luajit21` is LuaJIT 2.1's
Lua 5.1 family; `lua51` is Lua 5.1; `lua54` is Lua 5.4. Their accepted syntax
differs. Choose the intended runtime explicitly when sharing results. A pass
under Lua 5.4 does not establish that a LuaJIT-based game accepts the script.
Runtime metadata in the report identifies the selected installed VM.

The checker calls a trusted compile helper inside that VM and discards the
resulting function. The helper itself runs; inspected chunks do not. Parsing
happens in-process in a native library. **This is not a sandbox or a resource
isolation service for hostile inputs.** The file-size limit bounds each source
input but does not promise a parser time or memory limit. Use trusted local
inputs.

It cannot establish any of the following:

- That engine globals, APIs, modules, assets, or required data exist.
- That a chunk runs, terminates, or behaves correctly in a game.
- That X-Ray engine forks, preprocessing, includes, unlocalizers, DLTX, or other
  source transformations accept or produce the same code.
- That archive contents, managed/unmanaged game assets, MO2's live virtual
  filesystem, plugins, deployment tools, or other game loading rules match the
  loose-file priority model.
- That two compiling mods are compatible, or that a game launches or plays.

A syntax error means the selected VM rejected the bytes it received. Review
the reported relative path and line locally, confirm the intended runtime,
and check whether the game transforms that source before parsing it. The tool
does not rewrite or repair source.

## Reports and privacy

The JSON omits absolute input roots, source excerpts, and raw parser messages.
Errors are represented by categories and, when safely available, numeric line
numbers. This avoids copying a parser's unexpected-token text into a report.

Relative paths, enabled mod names, sizes, hashes, runtime versions, and counts
can still reveal private projects or identify known files. Terminal input or
write errors can also expose local paths. Review and redact reports and
screenshots before sharing. Prefer the original generated fixture to a game
report when reporting a bug. No reports are uploaded automatically.

## Troubleshooting and removal

| Symptom | What to check |
|---|---|
| Lupa or the requested VM is unavailable | Run the pinned install command using the same environment Python used for the checker. Confirm Python version/architecture and available official wheels. |
| A familiar script fails syntax | Select the game's intended Lua family; check engine preprocessing and locally inspect the indicated line. A VM parser is not an engine replacement. |
| No scripts or fewer scripts than expected | Check roots and suffixes, enabled entries, hidden paths, archive use, and whether a higher-priority copy masks the file. Read warnings/errors. |
| Scan incomplete | Read `errors`, `warnings`, and per-script `SKIPPED` records. Resolve missing/unsafe/unreadable/changing inputs or consciously raise the size limit for trusted files. |
| Output refused | Choose a fresh filename under an existing, unlinked reports directory outside all inputs. The checker never overwrites a report. |

There is no installed service, registry entry, game hook, or MO2 plugin to
remove. Delete the extracted tool and its local `.venv` when finished; remove
your own reports and demo directory separately if no longer needed. This does
not change game files or remove the separately managed Python installation.

## Tests, suggestions, and contributions

With the pinned dependency installed, run from this tool directory:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

The synthetic example is reproducible with the commands above. Automated tests
and CI validate tool behavior; they do not validate a particular game/modpack.

[Suggest a feature or report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new/choose).
Ideas, documentation improvements, and questions are welcome; you do not need
a finished code change. Include the tool version, Python/OS, chosen runtime,
redacted command, expected/actual result, exit code, and a small original
reproduction if possible. Do not attach proprietary game/mod source, saves,
tokens, raw logs, or unreviewed reports. See the collection's
[contribution guide](../../CONTRIBUTING.md).

## License

The original checker, tests, documentation, and generated toy examples are
covered by the repository's [MIT license](../../LICENSE). Retain its copyright
and permission notice when redistributing them. Lupa and its Lua/LuaJIT
components are separate dependencies with their own copyright and license
notices; installing or redistributing them does not relicense them under this
repository's notice. See [Lupa's license file](https://github.com/scoder/lupa/blob/master/LICENSE.txt)
and the notices in your installed dependency distribution. Game and third-party
mod content is neither bundled nor licensed by this project.
