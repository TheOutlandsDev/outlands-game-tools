"""Generate original XML configuration pairs; no game data or downloads. MIT."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat


INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
RESERVED_COMPONENT = re.compile(
    r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)


def portable_name(value: str) -> bool:
    return (0 < len(value) <= 255 and value not in ('.', '..')
            and not value.endswith((' ', '.')) and not INVALID_COMPONENT.search(value)
            and not RESERVED_COMPONENT.match(value))


BASELINE = """<?xml version="1.0" encoding="UTF-8"?>
<settings>
  <item id="shared" slots="4">original</item>
  <item id="removed" enabled="true">old toy setting</item>
  <item id="unchanged" enabled="true">same toy setting</item>
</settings>
"""

CANDIDATE = """<?xml version="1.0" encoding="UTF-8"?>
<settings>
  <item id="shared" slots="8">changed</item>
  <item id="added" enabled="true">new toy setting</item>
  <item id="unchanged" enabled="true">same toy setting</item>
</settings>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path,
                        help="New local folder outside the downloaded source tree.")
    args = parser.parse_args()
    raw = str(args.destination)
    destination = Path(os.path.abspath(args.destination))
    source_root = Path(__file__).resolve().parents[3]
    try:
        if (raw.startswith(("\\\\", "//")) or re.match(r'^[A-Za-z]:(?:$|[^\\/])', raw)
                or str(destination).startswith(("\\\\", "//"))
                or destination.is_relative_to(source_root)):
            raise ValueError("unsafe destination")
        if any(not portable_name(part) for part in destination.parts if part != destination.anchor):
            raise ValueError("unsafe destination name")
        for parent in (destination.parent, *destination.parent.parents):
            info = parent.lstat()
            if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & 0x400):
                raise ValueError("unsafe destination parent")
        destination.mkdir()
    except (OSError, ValueError):
        parser.error("Choose a new ordinary local folder with an existing parent, outside this source tree.")
    try:
        for name, content in (("baseline.xml", BASELINE), ("candidate.xml", CANDIDATE)):
            with (destination / name).open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
    except OSError:
        parser.exit(1, "Generation stopped; inspect the partial new toy folder before reusing it.\n")
    print("Created original baseline.xml and candidate.xml; no game files used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
