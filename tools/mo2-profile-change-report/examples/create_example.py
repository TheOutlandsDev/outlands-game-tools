#!/usr/bin/env python3
"""Create fictional saved-profile modlists for the MIT change reporter."""
import argparse
from pathlib import Path

BEFORE = '# Original fictional profile\n-Visuals_separator\n+Texture One\n+Audio Two\n-Optional Three\n+Legacy Four\n*Base Content\n'
AFTER = '# Original fictional comparison\n+Optional Three\n+Audio Two\n-Texture One\n-Visuals_separator\n+New Five\n*Base Content\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    destination = Path(args.destination)
    destination.mkdir(parents=False, exist_ok=False)
    for name, text in (('before', BEFORE), ('after', AFTER)):
        folder = destination / name
        folder.mkdir()
        with (folder / 'modlist.txt').open('xb') as stream:
            stream.write(text.encode('utf-8'))
    print('Created fictional before/modlist.txt and after/modlist.txt.')


if __name__ == '__main__':
    main()
