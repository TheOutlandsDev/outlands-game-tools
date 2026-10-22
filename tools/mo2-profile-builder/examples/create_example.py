#!/usr/bin/env python3
"""Generate original synthetic MO2 profile text in a NEW directory. MIT license."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import sys

REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="New example directory, outside the downloaded source tree")
    args = parser.parse_args()
    created = []
    root = Path(os.path.abspath(args.destination))
    source_root = Path(__file__).resolve().parents[3]
    try:
        raw = args.destination
        if raw.startswith(("\\\\", "//")) or "\x00" in raw:
            raise ValueError
        if root == source_root or source_root in root.parents:
            raise ValueError
        for component in (*reversed(root.parent.parents), root.parent):
            info = component.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & REPARSE:
                raise ValueError
        root.mkdir()
        created.append(root)
        profile = root / "Original Profile"
        profile.mkdir()
        created.append(profile)
        content = {
            "modlist.txt": b"\xef\xbb\xbf# Generated example: native saved order\r\n+Example Compatibility Fix\r\n+Example Content Mod\r\n+Example Balance Mod\r\n-Example Optional Mod\r\n",
            "settings.ini": b"[General]\r\n# Synthetic settings only; isolation is not configured here.\r\n",
            "archives.txt": b"# Generated synthetic archive notes\r\n",
            "plugins.txt": b"# Deliberately excluded from the copied profile\r\n",
        }
        for name, data in content.items():
            with (profile / name).open("xb") as stream:
                stream.write(data)
            created.append(profile / name)
        print("Created synthetic profiles example. See examples/README.md for preview/apply commands.")
        return 0
    except (OSError, ValueError):
        # Exclusive new directory only; no recursive cleanup or existing file removal.
        for path in reversed(created):
            try:
                path.rmdir() if path.is_dir() else path.unlink()
            except OSError:
                pass
        sys.stderr.write("Example generation refused or failed. Use a new local directory with an existing unlinked parent, outside the source tree.\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
