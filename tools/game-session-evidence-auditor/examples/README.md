# Fictional session evidence examples

From the collection root on Windows (use `python3` on Linux/macOS):

```powershell
py -3.12 -B tools/game-session-evidence-auditor/examples/create_example.py --destination ../outlands-session-demo
py -3.12 -B tools/game-session-evidence-auditor/session_auditor.py --root ../outlands-session-demo/clean --manifest ../outlands-session-demo/clean/manifest.json
py -3.12 -B tools/game-session-evidence-auditor/session_auditor.py --root ../outlands-session-demo/changed-capture --manifest ../outlands-session-demo/changed-capture/manifest.json
py -3.12 -B tools/game-session-evidence-auditor/session_auditor.py --root ../outlands-session-demo/missing-exit --manifest ../outlands-session-demo/missing-exit/manifest.json
py -3.12 -B tools/game-session-evidence-auditor/session_auditor.py --root ../outlands-session-demo/inconsistent --manifest ../outlands-session-demo/inconsistent/manifest.json --output ../outlands-session-demo/inconsistent-report.json
```

The new destination contains four original toy sessions. Each has a fictional
capture and a manifest; receipt files vary as described below. No game/process
was launched or observed. Example timestamps/PIDs are invented data assertions.

| Folder | Exit | Expected observations |
|---|---|---|
| `clean` | 0 | Three verified files, matching receipt pair, 120 declared seconds, exit code 0 |
| `changed-capture` | 2 | Capture size/hash mismatches against its original manifest; receipts still match |
| `missing-exit` | 2 | Null exit reference gives `missing_receipt`; pair consistency and exit code unknown |
| `inconsistent` | 2 | Files all match their declarations; exit PID differs, exit time is earlier, and exit code is 7 |

The last example is deliberately important: matching hashes do not mean the
receipt assertions are consistent, and exit-code 7 alone is not a crash diagnosis.
Its expected direct findings are `nonzero_exit_code`, `process_id_mismatch` and
`exit_before_launch`. The inconsistent pair is false and the declared duration
is -60 seconds. Raw receipt PIDs, executable labels and absolute timestamps are
omitted from the report.

The generator refuses an existing destination. Audits require fresh report paths
outside the selected session folder; stdout is the default. Source evidence is
left unchanged. See [manifest/receipt format](../EVIDENCE-FORMAT.md),
[report format](../REPORT-FORMAT.md) and [the guide](../README.md).
