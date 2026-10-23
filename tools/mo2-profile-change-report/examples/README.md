# Fictional MO2 profile example

From the repository root on Windows (use `python3` on Linux/macOS):

```powershell
py -3.12 -B tools/mo2-profile-change-report/examples/create_example.py --destination ../outlands-profile-demo
py -3.12 -B tools/mo2-profile-change-report/profile_change_report.py --before ../outlands-profile-demo/before/modlist.txt --after ../outlands-profile-demo/after/modlist.txt --output ../outlands-profile-demo/changes.json
```

Expected exit: **2**. The input files contain only original fictional names.
The generator refuses an existing destination. Use a new output for each report.

Before:

```text
# Original fictional profile
-Visuals_separator
+Texture One
+Audio Two
-Optional Three
+Legacy Four
*Base Content
```

After:

```text
# Original fictional comparison
+Optional Three
+Audio Two
-Texture One
-Visuals_separator
+New Five
*Base Content
```

| Observation | Expected result |
|---|---|
| Added | New Five |
| Removed | Legacy Four |
| Enabled | Optional Three |
| Disabled | Texture One |
| Reordered regular mods | Optional Three, Audio Two, Texture One (after-file order) |
| Separator relocated | Visuals_separator crosses shared regular mods |
| Foreign entries | Base Content unchanged; no enable/disable claim |

Shared regular order changes from `Texture One, Audio Two, Optional Three` to
`Optional Three, Audio Two, Texture One`. Audio Two keeps common rank 2, but its
relative order with both other mods reverses. All three are order-change
participants; the report does not claim all three were dragged manually.

For a no-change check:

```powershell
py -3.12 -B tools/mo2-profile-change-report/profile_change_report.py --before ../outlands-profile-demo/before/modlist.txt --after ../outlands-profile-demo/before/modlist.txt
```

Expected exit: **0**, complete with empty change lists. Input files remain
unchanged in both examples. The report uses saved physical order, not GUI sort
order or game plugin load order. See [the guide](../README.md) and
[report format](../REPORT-FORMAT.md).
