"""Create original toy trees for the MIT Mod Content Manifest & Diff tool."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat


def ordinary_parent(path: Path) -> bool:
    """Reject linked/reparse parents rather than following a surprising location."""
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return False
    return path.is_dir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path,
                        help="New directory with an existing ordinary local parent.")
    args = parser.parse_args()
    destination = Path(os.path.abspath(args.destination))
    if (str(destination).startswith(("\\\\", "//")) or
            destination.name.rstrip(". ") != destination.name or
            ":" in destination.name):
        parser.error("Choose a new ordinary local destination.")
    try:
        if not ordinary_parent(destination.parent):
            raise ValueError("unsafe parent")
        destination.mkdir()
    except (OSError, ValueError):
        parser.error("Destination must be new with an existing ordinary local parent.")

    files = {
        "baseline/gamedata/configs/shared.ltx": "[toy]\nvalue = original\n",
        "baseline/gamedata/configs/removed.ltx": "[old_toy]\nvalue = 1\n",
        "baseline/gamedata/scripts/common.script": "return { example = true }\n",
        "candidate/gamedata/configs/shared.ltx": "[toy]\nvalue = changed\n",
        "candidate/gamedata/configs/added.ltx": "[new_toy]\nvalue = 2\n",
        "candidate/gamedata/scripts/common.script": "return { example = true }\n",
        "mo2/modlist.txt": "# Generated original example: highest enabled first.\n+High Toy\n+Low Toy\n-Disabled Toy\n",
        "mo2/mods/High Toy/gamedata/configs/shared.ltx": "[toy]\nvalue = high\n",
        "mo2/mods/Low Toy/gamedata/configs/shared.ltx": "[toy]\nvalue = low\n",
        "mo2/mods/Low Toy/gamedata/configs/low_only.ltx": "[low_toy]\nvalue = 1\n",
        "mo2/mods/Disabled Toy/gamedata/configs/disabled.ltx": "[disabled_toy]\nvalue = 1\n",
        "mo2/base/gamedata/configs/base_only.ltx": "[base_toy]\nvalue = 1\n",
        "mo2/base/gamedata/configs/shared.ltx": "[toy]\nvalue = base\n",
        "mo2/overwrite/gamedata/configs/shared.ltx": "[toy]\nvalue = overwrite\n",
    }
    try:
        for relative, content in files.items():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
    except OSError:
        parser.exit(1, "Example generation stopped; a partial new toy directory may remain.\n")
    print("Created original baseline/, candidate/, and mo2/ toy trees; no game files used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
