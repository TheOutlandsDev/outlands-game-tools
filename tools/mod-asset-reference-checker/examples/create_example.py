"""Create original toy LTX references and loose placeholders, not game assets. MIT."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat

INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
RESERVED_NAME = re.compile(
    r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)


def portable_name(name: str) -> bool:
    return (0 < len(name) <= 255 and name not in ('.', '..')
            and not name.endswith((' ', '.')) and not INVALID_NAME.search(name)
            and not RESERVED_NAME.match(name))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True,
                        help='New local folder outside this downloaded source tree.')
    args = parser.parse_args()
    raw = str(args.destination)
    destination = Path(os.path.abspath(args.destination))
    source_root = Path(__file__).resolve().parents[3]
    try:
        if (raw.startswith(('\\\\', '//')) or re.match(r'^[A-Za-z]:(?:$|[^\\/])', raw)
                or str(destination).startswith(('\\\\', '//'))
                or destination.is_relative_to(source_root)
                or any(not portable_name(part) for part in destination.parts if part != destination.anchor)):
            raise ValueError('unsafe destination')
        for parent in (destination.parent, *destination.parent.parents):
            info = parent.lstat()
            if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                    or getattr(info, 'st_file_attributes', 0) & 0x400):
                raise ValueError('unsafe destination parent')
        destination.mkdir()
    except (OSError, ValueError):
        parser.error('Choose a new ordinary local folder with an existing parent, outside this source tree.')
    config = '''; Original toy data for a presence checker, not an installed game config.
[toy_present]
visual = toy\\present

[toy_absent]
visual = toy\\absent

[toy_weapon]
ammo_class = ammo_toy

[ammo_toy]
description = original toy declaration
'''
    files = {
        'gamedata/configs/toy.ltx': config.encode('utf-8'),
        'gamedata/meshes/toy/present.ogf': b'Original toy placeholder; not a usable mesh.\n',
        'index.json': b'{"schema_version":1,"kind":"asset-path-index","paths":["meshes/toy/absent.ogf"]}\n',
    }
    try:
        for relative, content in files.items():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(content)
    except OSError:
        parser.exit(1, 'Generation stopped; inspect the partial new toy folder before reusing it.\n')
    print('Created original toy LTX and a loose placeholder; no game files or valid mesh payloads used.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
