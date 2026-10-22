# Original LTX examples

These examples are generated from fictional text in `create_example.py`.
They contain no game/mod source. The generator creates a new directory outside
the repository and refuses an existing destination. Run from the parent tool
directory (`tools\ltx-definition-inspector`):

```powershell
$demo = Join-Path $env:TEMP ('outlands-ltx-demo-' + [guid]::NewGuid().ToString('N'))
py -3.12 -B examples\create_example.py --destination $demo

py -3.12 -B ltx_inspector.py --root (Join-Path $demo 'configs') --entry clean.ltx `
  --output (Join-Path $demo 'clean-report.json')
$LASTEXITCODE

py -3.12 -B ltx_inspector.py --root (Join-Path $demo 'configs') --entry review.ltx `
  --output (Join-Path $demo 'review-report.json')
$LASTEXITCODE

py -3.12 -B ltx_inspector.py --root (Join-Path $demo 'configs') --entry unsupported.ltx `
  --output (Join-Path $demo 'unsupported-report.json')
$LASTEXITCODE
```

Expected results:

| Entry | Exit | Reason |
| --- | ---: | --- |
| `clean.ltx` | `0` | Includes two base declarations and declares one child with those parents in order. |
| `review.ltx` | `2` | Missing parent, duplicate declaration, and an inheritance cycle require review. |
| `unsupported.ltx` | `1` | DLTX `![...]` syntax is intentionally unsupported; no patch semantics are guessed. |

On Linux/macOS, choose a new path whose parent exists, for example:

```bash
demo="/tmp/outlands-ltx-demo-$(date +%s)-$$"
python3 -B examples/create_example.py --destination "$demo"
python3 -B ltx_inspector.py --root "$demo/configs" --entry clean.ltx --output "$demo/clean-report.json"
echo $?
python3 -B ltx_inspector.py --root "$demo/configs" --entry review.ltx
echo $?
python3 -B ltx_inspector.py --root "$demo/configs" --entry unsupported.ltx
echo $?
```

Inspect each JSON report's `complete`, `findings`, `errors`, and `exit_code`.
Generated files stay where you chose; the tool does not remove them. Report
names must be new on subsequent runs. See the parent [README](../README.md)
and [report format](../REPORT-FORMAT.md) for scope and interpretation.
