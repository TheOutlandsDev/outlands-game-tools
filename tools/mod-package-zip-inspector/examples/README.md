# Original toy ZIP examples

Run from the collection root with Python 3.12+. Use `python3` on Linux/macOS.
The new sibling destination avoids putting generated binary files in source.

```powershell
py -3.12 -B tools/mod-package-zip-inspector/examples/create_example.py --destination ../outlands-zip-demo
py -3.12 -B tools/mod-package-zip-inspector/zip_inspector.py --archive demo=../outlands-zip-demo/clean.zip
py -3.12 -B tools/mod-package-zip-inspector/zip_inspector.py --archive demo=../outlands-zip-demo/wrapper.zip
py -3.12 -B tools/mod-package-zip-inspector/zip_inspector.py --archive demo=../outlands-zip-demo/review.zip --output ../outlands-zip-demo/findings.json
```

| Archive | Expected exit | Expected observations |
|---|---|---|
| `clean.zip` | 0 | Two tiny root files, no configured findings |
| `wrapper.zip` | 2 | `common_top_level_folder: "ToyMod"`; review intended installation root |
| `review.zip` | 2 | `../outside.txt` has `unsafe_path`; `Textures/a.txt` and `textures/A.txt` collide under the portable comparison policy |

Selected excerpt of `review.zip` inventory (other fields omitted):

```json
{
  "complete": true,
  "archive": {
    "label": "demo",
    "entries": [
      {"name": "../outside.txt", "issues": ["unsafe_path"]},
      {"name": "Textures/a.txt", "issues": []},
      {"name": "textures/A.txt", "issues": ["case_or_normalization_collision"], "first_name_entry": 1}
    ]
  }
}
```

No extracted `outside.txt` is created. Reports contain names and declared
metadata, not member contents. The generator refuses an existing destination;
use a new folder for another run. A new `--output` path is also required for each
report. A finding is a request for human review, not automatic installation
advice. See the [tool guide](../README.md) and [report format](../REPORT-FORMAT.md).
