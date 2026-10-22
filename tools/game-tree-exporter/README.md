# Game Folder Inventory

Python 3.12+; standard library only. Lists folder/file metadata without reading
file contents, starting or changing the game, or following symlinks/junctions.
Adapted from the locally authored `export_spt_tree.py`. MIT; see the root license.

```powershell
python -B export_game_tree.py "X:\Games\MyGame" --output "X:\Reports\MyGameInventory"
python -B -m unittest discover -s tests -v
```

The output directory is required. The tool creates `game_tree.txt`,
`game_files.csv`, and `game_files.json`; existing report files require
`--overwrite`. An output subdirectory inside the selected root is not expanded.
An output path containing a symlink or junction is refused.

Default filters skip runtime profiles, saves, logs, backups, BepInEx, common
dependency/cache folders, archives, binaries, images, videos, and common secret
file extensions. `--include-skipped` lists filtered names but does not expand
filtered directories or linked targets. `--max-size N` filters large files.

Reports contain relative filenames, sizes and modification times. Absolute root
paths are omitted, but names can still reveal installed mods or personal data.
CSV text cells that could be interpreted as spreadsheet formulas receive an
apostrophe prefix; JSON and TXT preserve the original names.
Filters are not a secret scanner: review reports before sharing. BepInEx is
excluded by default; select its `plugins` directory as the root if needed.

Exit codes: 0 complete, 1 invalid input/write failure, 2 partial inventory due to
read errors. Deep recursion can fail rather than follow an unlimited tree.
There is no guarantee of a consistent snapshot while another process changes
the tree. Output may be partial if a write fails; no source files are altered.
