#!/usr/bin/env python3
"""Generate original tiny LTX examples in a new folder outside this repository.

Copyright (c) 2026 TheOutlandsDev. MIT license.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ltx_inspector import CheckError, absolute, ancestry, case_matches  # noqa: E402

EXAMPLES = {
    "clean.ltx": '#include "parts/base.ltx"\n[demo_child]: demo_base, demo_secondary\nweight = 2\n',
    "parts/base.ltx": "; Original fictional fixture; no game data.\n[demo_base]\nweight = 1\n[demo_secondary]\n",
    "review.ltx": "[demo_child]: missing_parent\n[duplicate]\n[duplicate]\n[loop_a]: loop_b\n[loop_b]: loop_a\n",
    "unsupported.ltx": "; DLTX deliberately outside the supported subset.\n![demo_base]\nweight = 9\n",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destination", required=True, help="new directory outside the repository")
    args = parser.parse_args()
    try:
        destination = absolute(args.destination)
        repository = Path(__file__).resolve().parents[3]
        if destination == repository or repository in destination.parents:
            raise CheckError("DESTINATION_INSIDE_REPOSITORY")
        ancestry(destination.parent, directory=True)
        if case_matches(destination.parent, destination.name):
            raise CheckError("DESTINATION_EXISTS")
        destination.mkdir()
        configs = destination / "configs"
        configs.mkdir()
        (configs / "parts").mkdir()
        for name, text in EXAMPLES.items():
            with (configs / name).open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        print("Created original LTX examples. See examples/README.md for commands and expected exits.")
        return 0
    except (CheckError, OSError) as exc:
        print(f"example generator: {exc.code if isinstance(exc, CheckError) else 'IO_ERROR'}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
