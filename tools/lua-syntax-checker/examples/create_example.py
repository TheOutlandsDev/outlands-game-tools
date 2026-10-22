#!/usr/bin/env python3
"""Create original toy Lua inputs in a new directory. MIT; see repository LICENSE."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


FILES = {
    "source/valid.lua": "local values = { 2, 3, 5 }\nreturn values[1] + values[2] + values[3]\n",
    "source/noexecute.lua": (
        '-- This is valid syntax. The checker must never run this chunk.\n'
        'error("The fixture was executed instead of compiled")\n'
        'while true do end\n'
    ),
    "source/broken.script": "local value =\nreturn value\n",
    "source/ignored.txt": "This is not Lua and must not be parsed.\n",
    "mo2/profile/modlist.txt": (
        "# Original synthetic example; highest priority first.\n"
        "+Example Override\n+Example Base\n-Disabled Example\n"
    ),
    "mo2/mods/Example Base/scripts/shared.script": 'return { source = "base mod" }\n',
    "mo2/mods/Example Base/scripts/masked.script": "local = broken\n",
    "mo2/mods/Example Base/scripts/base_only.lua": 'return "base-only file"\n',
    "mo2/mods/Example Override/scripts/shared.script": 'return { source = "override mod" }\n',
    "mo2/mods/Example Override/scripts/masked.script": "return true\n",
    "mo2/mods/Disabled Example/scripts/disabled.lua": "local = also_broken\n",
    "mo2/base-data/scripts/engine.script": 'return "base data example"\n',
    "mo2/base-data/scripts/shared.script": 'return { source = "base data" }\n',
    "mo2/overwrite/scripts/shared.script": 'return { source = "overwrite" }\n',
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path,
                        help="New local directory whose parent already exists; never a game/MO2 directory.")
    args = parser.parse_args(argv)
    destination = args.destination.expanduser().absolute()
    if str(destination).startswith(("\\\\", "//")):
        parser.error("Use a local destination, not a UNC/network path.")
    for component in (destination, *destination.parents):
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            parser.error("Linked destinations or ancestors are not supported.")
        if component.exists() and getattr(component.stat(), "st_file_attributes", 0) & 0x400:
            parser.error("Reparse points are not supported.")
    if destination.exists() or not destination.parent.is_dir():
        parser.error("Destination must not exist, and its parent must be an existing directory.")
    try:
        destination.mkdir()
        for relative, content in FILES.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
    except OSError as exc:
        print(f"Could not finish the example ({type(exc).__name__}). No existing files were replaced.",
              file=sys.stderr)
        return 1
    print(f"Created original example inputs in {destination}")
    print("source: 2 valid scripts, 1 intentional syntax error, 1 ignored .txt file")
    print("mo2: original loose files showing priority, disabled entries, and a masked syntax error")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
