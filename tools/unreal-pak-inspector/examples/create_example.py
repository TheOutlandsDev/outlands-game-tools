"""Generate original toy version-3 PAKs for metadata tests; no game data. MIT."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import zlib


def string(value, wide=False):
    if wide:
        raw = value.encode('utf-16-le') + b'\0\0'
        return struct.pack('<i', -len(raw) // 2) + raw
    raw = value.encode('ascii') + b'\0'
    return struct.pack('<i', len(raw)) + raw


def build_pak(files, mount='../../../', wide=False, compressed=False):
    """Independent byte fixture builder; intentionally not a production packer."""
    data, rows = bytearray(), []
    for path, payload in files:
        method = 1 if compressed and payload else 0
        chunks = [zlib.compress(payload[n:n+65536]) for n in range(0, len(payload), 65536)] if method else []
        stored = b''.join(chunks) if method else payload
        start = len(data)
        header_size = 57 + 16 * len(chunks) if method else 53
        blocks = bytearray()
        cursor = start + header_size
        for chunk in chunks:
            blocks += struct.pack('<qq', cursor, cursor + len(chunk))
            cursor += len(chunk)
        tail = ((struct.pack('<i', len(chunks)) + blocks) if method else b'') + struct.pack('<BI', 0, 65536 if method else 0)
        fields = struct.pack('<qqI', len(stored), len(payload), method) + hashlib.sha1(stored).digest() + tail
        data += struct.pack('<q', 0) + fields + stored
        rows.append(string(path, wide) + struct.pack('<q', start) + fields)
    index = string(mount, wide) + struct.pack('<i', len(rows)) + b''.join(rows)
    footer = struct.pack('<Iiqq20s', 0x5A6F12E1, 3, len(data), len(index), hashlib.sha1(index).digest())
    return bytes(data) + index + footer


def destination(raw):
    if (not raw or raw.startswith(('\\\\', '//')) or re.match(r'^[A-Za-z]:(?:$|[^\\/])', raw)):
        raise ValueError('unsafe destination')
    path = Path(os.path.abspath(raw))
    source = Path(__file__).resolve().parents[3]
    if (path.is_relative_to(source) or len(str(path)) > 1024
            or str(path).startswith(('\\\\', '//'))):
        raise ValueError('unsafe destination')
    bad = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
    device = re.compile(r'^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', re.I)
    if any(not part or part.endswith((' ', '.')) or bad.search(part) or device.match(part)
           for part in path.parts if part != path.anchor):
        raise ValueError('unsafe destination')
    for parent in (path.parent, *path.parent.parents):
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError('unsafe parent')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, help='New local toy folder outside this source tree; existing parent required')
    args = parser.parse_args()
    try:
        root = destination(args.destination)
        root.mkdir()
    except (OSError, ValueError):
        parser.error('Choose a new ordinary local folder outside the source tree, with an existing parent.')
    examples = {
        'base.pak': build_pak([('Toy/Content/shared.uasset', b'Original toy base placeholder\n'),
                               ('Toy/Content/base_only.txt', b'Original toy text\n')]),
        'mod.pak': build_pak([('shared.uasset', b'Different original toy mod placeholder\n'),
                              ('mod_only.txt', b'Original toy mod text\n')], mount='../../../Toy/Content/'),
        'clean.pak': build_pak([('Toy/Content/separate.txt', b'Original compressed toy text\n')], wide=True, compressed=True),
    }
    try:
        for name, content in examples.items():
            with (root/name).open('xb') as stream:
                stream.write(content)
    except OSError:
        parser.exit(1, 'Generation stopped; inspect the partial new toy folder.\n')
    print('Created base.pak, mod.pak and clean.pak with original toy payloads; not game assets or a production packer.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
