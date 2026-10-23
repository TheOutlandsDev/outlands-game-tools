"""Generate original INI/LTX value-diff pairs, with no actual game data. MIT."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat

BAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE_NAME = re.compile(
    r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)


def portable_name(name: str) -> bool:
    return (0 < len(name) <= 255 and name not in ('.', '..')
            and not name.endswith((' ', '.')) and not BAD_NAME.search(name)
            and not DEVICE_NAME.match(name))


INI_BEFORE = '''; Original toy INI: DEFAULT is an ordinary section.
title = original global
[DEFAULT]
note = ordinary section value
[toy]
changed = one
remove_me = old toy value
blank =
unchanged = same
literal = "%TOY%;${toy}"
'''

INI_AFTER = '''; Original toy INI: values remain literal strings.
title = changed global
[DEFAULT]
note = ordinary section value
[toy]
changed = two
added = new toy value
unchanged = same
literal = "%TOY%;${toy}"
'''

LTX_BEFORE = '''; Original toy LTX: parents are context, never merged.
[base_a]
kind = original
[base_b]
kind = original
[toy]:base_a
changed = toy\\one ; old comment
blank =
unchanged = same
quoted = "toy;literal"
'''

LTX_AFTER = '''; Original toy LTX: parent and direct stored values differ.
[base_a]
kind = original
[base_b]
kind = original
[toy]:base_b
changed = toy\\two ; changed comment
added = new toy value
unchanged = same
quoted = "toy;literal"
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True,
                        help='New local directory outside this downloaded source tree.')
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
                raise ValueError('unsafe parent')
        destination.mkdir()
    except (OSError, ValueError):
        parser.error('Choose a new ordinary local directory with an existing parent, outside this source tree.')
    try:
        for name, text in (('before.ini', INI_BEFORE), ('after.ini', INI_AFTER),
                           ('before.ltx', LTX_BEFORE), ('after.ltx', LTX_AFTER)):
            with (destination / name).open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
    except OSError:
        parser.exit(1, 'Generation stopped; inspect the partial new toy directory before reusing it.\n')
    print('Created original before/after INI and LTX pairs; no actual game configuration used.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
