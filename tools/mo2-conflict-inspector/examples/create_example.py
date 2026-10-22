#!/usr/bin/env python3
"""Create an original synthetic MO2 profile in a new directory, without a game.

MIT; see the repository root LICENSE. This is a fixture generator, not a mod
installer. It refuses an existing destination and never deletes or replaces it.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import stat
import sys


FILES = {
    "profiles/Example/modlist.txt": (
        "# Original synthetic example; native MO2 order is highest first.\n"
        "+Hotfix\n-Disabled\n+Base\n"
    ),
    "mods/Base/gamedata/configs/toy.ltx": "[toy]\nspeed = 1\n",
    "mods/Hotfix/gamedata/configs/toy.ltx": "[toy]\nspeed = 2\nspeed = 3\n",
    "mods/Base/gamedata/textures/toy.asset": (
        "Original synthetic placeholder, not a game asset.\n"
    ),
    "overwrite/gamedata/textures/toy.asset": (
        "Original synthetic overwrite placeholder, not a game asset.\n"
    ),
    "mods/Base/gamedata/scripts/menu.script": (
        "function ui.refresh_menu()\n    return 1\nend\n"
    ),
    "mods/Hotfix/gamedata/scripts/settings.script": (
        "function ui.refresh_menu()\n    return 2\nend\n"
    ),
    "mods/Base/gamedata/configs/unlocalizers/base.ltx": "[ui]\nrefresh_menu\n",
    "mods/Hotfix/gamedata/configs/unlocalizers/hotfix.ltx": "[ui]\nrefresh_menu\n",
    "mods/Disabled/not-in-report.md": "This disabled mod must not be scanned.\n",
}


def is_link_or_reparse(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def create_example(destination: Path) -> None:
    """Make only a new fixture; all paths in FILES are fixed relative names."""
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination already exists; choose a new directory")
    if not destination.parent.is_dir():
        raise ValueError("destination parent must be an existing directory")
    for ancestor in (destination.parent, *destination.parent.parents):
        if is_link_or_reparse(ancestor):
            raise ValueError("destination parent must not use links or reparse points")
    destination.mkdir(exist_ok=False)
    for relative, contents in FILES.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also prevents accidental replacement during a rerun.
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(contents)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="new directory to create")
    args = parser.parse_args()
    try:
        create_example(args.destination)
    except (OSError, ValueError) as exc:
        print(f"Example not created: {exc}", file=sys.stderr)
        return 1
    print("Created original synthetic example. Run the README's inspector command next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
