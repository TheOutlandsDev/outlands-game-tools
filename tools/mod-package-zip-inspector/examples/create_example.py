#!/usr/bin/env python3
"""Generate original tiny ZIP examples outside the checkout; no downloaded assets. MIT."""
import argparse
import io
from pathlib import Path
import zipfile


def build_zip(entries, compression=zipfile.ZIP_STORED, comment=b''):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=compression, allowZip64=False) as archive:
        for name, content in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = compression
            info.create_system = 3
            info.external_attr = ((0o40755 << 16) | 0x10) if name.endswith('/') else (0o100644 << 16)
            archive.writestr(info, content)
        archive.comment = comment
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    destination = Path(args.destination)
    # The generator is for a caller-selected scratch folder, never a mod installer.
    destination.mkdir(parents=False, exist_ok=False)
    fixtures = {
        'clean.zip': [('notes.txt', b'Original fictional mod notes.\n'), ('settings.ini', b'[toy]\nvolume=1\n')],
        'wrapper.zip': [('ToyMod/settings.ini', b'[toy]\nvolume=1\n')],
        'review.zip': [('../outside.txt', b'Fictional traversal example.\n'),
                       ('Textures/a.txt', b'First toy file.\n'), ('textures/A.txt', b'Second toy file.\n')],
    }
    for name, entries in fixtures.items():
        with (destination / name).open('xb') as stream:
            stream.write(build_zip(entries))
    print('Created clean.zip, wrapper.zip and review.zip in the new destination.')


if __name__ == '__main__':
    main()
