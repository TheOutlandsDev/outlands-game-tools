# Original generated references

`create_example.py` writes a tiny original config, one plain-text `.ogf`
placeholder, and a JSON name index into a new external folder. No game data,
third-party mod settings or usable binary game assets are bundled or downloaded.
The placeholder is deliberately **not a valid mesh**: it demonstrates presence
checking rather than format or engine validation.

The generated layout is:

```text
gamedata/configs/toy.ltx
gamedata/meshes/toy/present.ogf
index.json
```

`toy.ltx` declares four sections. It has two direct `visual` references and one
`ammo_class` reference. The latter targets a declared toy section. Only one
visual has a loose file. Follow the [main README commands](../README.md):

- Without an index, expect exit **2**: one `found_loose`, one
  `unresolved_coverage`, one `declared_in_selection`.
- With `index.json`, expect exit **0**: the unresolved path becomes
  `listed_in_index`, without verifying any packed payload.

Reports belong beside `gamedata`, outside both selected roots. Existing report
or demo paths are refused. Delete only your generated demo folder with your
normal file manager when finished. No automatic cleanup occurs.
