# Reproducible original examples

`create_example.py` creates original toy Lua and MO2-shaped inputs in a new
directory. It copies no game or third-party mod files. It refuses an existing
destination and linked/reparse destinations or ancestors. Run it in a temporary
or scratch location outside any game/MO2 inputs. The generator writes files;
the checker only reads them and creates a report when requested.

Install the pinned dependency using the [main quickstart](../README.md) first.
The following PowerShell commands run from `tools\lua-syntax-checker` and use
its local virtual environment.

## One source tree, including an intentional error

```powershell
$demo = Join-Path $env:TEMP ('outlands-lua-demo-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B examples\create_example.py --destination $demo
.\.venv\Scripts\python.exe -B lua_syntax.py `
  --source-dir (Join-Path $demo 'source') `
  --runtime luajit21 `
  --output (Join-Path $demo 'source-report.json')
$LASTEXITCODE
$sourceReport = Get-Content -LiteralPath (Join-Path $demo 'source-report.json') -Raw | ConvertFrom-Json
$sourceReport.summary
$sourceReport.scripts | Select-Object path, status, code, line
```

Expected result: exit code **2**, complete scan, **3** effective checked scripts,
**2** passes and **1** syntax error.

| Input | Expected result |
|---|---|
| `source/valid.lua` | `PASS`: a small valid chunk. |
| `source/noexecute.lua` | `PASS`: valid syntax containing a top-level `error()` followed by an infinite loop. Neither runs because the checker never invokes the compiled chunk. |
| `source/broken.script` | `SYNTAX_ERROR`: an intentionally unfinished assignment before `return`. |
| `source/ignored.txt` | Ignored: suffix is neither `.lua` nor `.script`. |

Never run `noexecute.lua` directly to test the checker; its job is to demonstrate
that compilation and execution are different operations. Exact parser line
metadata can differ between VMs. Raw error text and source tokens are not
included in the report.

## Effective scripts from a saved MO2-style profile

The same demo directory also contains a synthetic saved modlist, mod folders,
base loose data, and Overwrite. They are an example file layout, not a real MO2
instance or a mod to install.

```powershell
.\.venv\Scripts\python.exe -B lua_syntax.py `
  --mods-dir (Join-Path $demo 'mo2\mods') `
  --modlist (Join-Path $demo 'mo2\profile\modlist.txt') `
  --base-dir (Join-Path $demo 'mo2\base-data') `
  --overwrite-dir (Join-Path $demo 'mo2\overwrite') `
  --runtime luajit21 `
  --output (Join-Path $demo 'mo2-report.json')
$LASTEXITCODE
$mo2Report = Get-Content -LiteralPath (Join-Path $demo 'mo2-report.json') -Raw | ConvertFrom-Json
$mo2Report.providers_priority_highest_first
$mo2Report.summary
$mo2Report.scripts | Select-Object path, provider, status
```

Expected result: exit code **0**, complete scan, **4** effective checked scripts,
all passing. The native saved modlist places `Example Override` above `Example
Base`. `<overwrite>` ranks above both; `<base>` ranks below both.

| Effective path | Selected provider | Why |
|---|---|---|
| `scripts/shared.script` | `<overwrite>` | Wins over matching files in both enabled mods and base data. |
| `scripts/masked.script` | `Example Override` | Valid override masks the intentionally broken lower-priority copy in `Example Base`. |
| `scripts/base_only.lua` | `Example Base` | Only that mod supplies it. |
| `scripts/engine.script` | `<base>` | Only base loose data supplies it. |

`Disabled Example` contains a broken script but is disabled in the modlist, so
it is not scanned. The candidate-copy and shadowed totals show that a report
about effective scripts is different from compiling every installed mod file.

To inspect all copies under an individual mod instead, run a new source-tree
scan of that mod with a fresh output filename. The lower-priority broken
`masked.script` will then be visible to that scan.

## Linux/macOS equivalent

Use an existing scratch parent and a **new** child name. Replace the demo root
with your own path; the generator refuses an existing directory.

```bash
.venv/bin/python -B examples/create_example.py --destination /tmp/outlands-lua-demo-example
.venv/bin/python -B lua_syntax.py --source-dir /tmp/outlands-lua-demo-example/source --output /tmp/outlands-lua-demo-example/source-report.json
echo $?
```

The source example intentionally returns `2`. That is a successful detection,
not an install failure. Refer to the [report reference](../REPORT-FORMAT.md) to
interpret the generated JSON. Use a new report name on repeated runs; no report
is overwritten. No sample runtime binaries or game assets are distributed.
