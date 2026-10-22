#!/usr/bin/env python3
"""Create one small synthetic log exclusively; no installed game is inspected. MIT."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

EXAMPLE = """Starting engine
Starting new game
GameNetworkingSockets synthetic transport marker
Client connected synthetic marker only
WARNING sound sample rate: synthetic_asset_a
WARNING sound sample rate: synthetic_asset_b
WARNING treasure item missing: synthetic_item
WARNING arbitrary generated condition
[SCRIPT ERROR] generated demonstration, no real stack trace
FATAL ERROR generated demonstration, no real crash
Engine shutdown
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="A new local file in an existing physical directory")
    args = parser.parse_args()
    # Reuse the input/output guards, not an alternate writer that follows links.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import xray_log_summary as tool
    try:
        target = tool._path(str(args.output))
        tool._prepare_output(target, target.parent)
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(EXAMPLE)
    except (tool.LogError, OSError, ValueError):
        print("example_creation_failed", file=sys.stderr)
        return 1
    print("synthetic_example_created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
