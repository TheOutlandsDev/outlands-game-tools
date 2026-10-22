"""Generate original toy saves/config in a new folder; never inspect games."""
import argparse
import importlib.util
from pathlib import Path
import sys

SPEC=importlib.util.spec_from_file_location('save_snapshot',Path(__file__).resolve().parents[1]/'save_snapshot.py')
TOOL=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',required=True)
    args=parser.parse_args()
    try:
        root=TOOL.absolute(args.destination)
        TOOL.fresh(root)
        root.mkdir()
        saves=root/'saves';saves.mkdir()
        TOOL.new_file(saves/'slot1.dat',b'Original synthetic save slot one.\n')
        TOOL.new_file(saves/'slot2.dat',b'Original synthetic save slot two.\n')
        TOOL.new_file(root/'profile.ini',b'[original_example]\ndifficulty=toy\n')
    except (TOOL.Failure,OSError,ValueError):
        print('Unable to create example; choose a new local folder with an existing parent.',file=sys.stderr)
        return 1
    print('Created two original toy saves and one profile.ini. No game files used.')
    return 0

if __name__=='__main__': raise SystemExit(main())
