#!/usr/bin/env python3
"""Create a new external original toy source tree and its explicit MIT inventory."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

MODULE = Path(__file__).resolve().parents[1] / "source_release.py"
SPEC = importlib.util.spec_from_file_location("source_release", MODULE)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def main() -> int:
    parser = builder.Parser(description=__doc__)
    parser.add_argument("--destination", required=True, help="New local example folder with existing parent")
    try:
        args = parser.parse_args()
        destination = builder.absolute_local(args.destination)
        builder.checked_stat(destination.parent, "directory")
        builder.ensure_absent(destination)
        # Keep generated payloads out of the published source tree.
        collection = Path(__file__).resolve().parents[3]
        if destination.is_relative_to(collection):
            builder.fail("example_inside_collection")
        license_data = (collection / "LICENSE").read_bytes()
        destination.mkdir()
        source = destination / "source"
        source.mkdir()
        payload = {"LICENSE": license_data,
                   "hello.py": b"print('Hello from the original generated source example')\n",
                   "README.md": b"# Original toy source\n\nRun with Python 3.12 or later.\n"}
        rows = []
        for name, data in sorted(payload.items()):
            with (source / name).open("xb") as stream:
                stream.write(data)
            rows.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        manifest = {"schema_version": 1, "license": "MIT", "files": rows}
        with (source / builder.MANIFEST).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(manifest, indent=2) + "\n")
        # A harmless unlisted file demonstrates that only inventory entries are selected.
        (source / "unlisted.md").write_text("This original toy file is intentionally not listed.\n", encoding="utf-8")
        print(json.dumps({"status": "PASS", "listed_files": len(rows), "unlisted_files": 1}))
        return 0
    except (builder.BuildError, OSError, ValueError):
        print(json.dumps({"status": "FAIL", "code": "example_creation_failed", "partial_example_possible": True}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
