#!/usr/bin/env python3
"""Export a filtered game-folder inventory without reading file contents. MIT."""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", "logs", "log", "temp", "tmp",
    "cache", ".idea", ".vscode", "bepinex", "user", "profiles", "save",
    "saves", "backups", ".secrets",
})
SKIP_EXTS = frozenset({
    ".log", ".tmp", ".bak", ".zip", ".7z", ".rar", ".exe", ".dll",
    ".pdb", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mkv", ".avi",
    ".key", ".pem", ".pfx", ".p12",
})
OUTPUT_NAMES = ("game_tree.txt", "game_files.csv", "game_files.json")
FIELDS = ("type", "rel_path", "name", "ext", "size", "mtime_utc", "skipped")


def csv_safe(value):
    """Prevent file names from becoming spreadsheet formulas in CSV readers."""
    if isinstance(value, str) and value and (
        value[0] in "\t\r\n" or value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@"))
    ):
        return "'" + value
    return value


def is_link(path: Path) -> bool:
    """Treat Windows junctions as links; never recurse through them."""
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def build_tree(root: Path, output: Path, include_skipped: bool = False,
               max_size: int | None = None) -> tuple[list[dict], list[str], list[str]]:
    rows: list[dict] = []
    lines = ["GAME FOLDER INVENTORY", "Root: <selected folder>", "", root.name + "/"]
    errors: list[str] = []

    def visit(directory: Path, prefix: str) -> None:
        relative_dir = directory.relative_to(root).as_posix()
        try:
            entries = list(directory.iterdir())
        except OSError as exc:
            errors.append(f"{relative_dir}: {type(exc).__name__}")
            return
        selected: list[tuple[Path, str, bool, os.stat_result]] = []
        for path in entries:
            relative = path.relative_to(root).as_posix()
            try:
                info = path.lstat()
                linked = is_link(path)
                kind = "link" if linked else "dir" if path.is_dir() else "file"
                skipped = (
                    linked or path == output or path.name.lower() == ".env"
                    or path.name.lower().startswith(".env.")
                    or (kind == "dir" and path.name.lower() in SKIP_DIRS)
                    or (kind == "file" and path.suffix.lower() in SKIP_EXTS)
                    or (kind == "file" and max_size is not None and info.st_size > max_size)
                )
                if not skipped or include_skipped:
                    selected.append((path, kind, skipped, info))
            except OSError as exc:
                errors.append(f"{relative}: {type(exc).__name__}")
        selected.sort(key=lambda entry: (entry[1] != "dir", entry[0].name.casefold()))
        for index, (path, kind, skipped, info) in enumerate(selected):
            last = index == len(selected) - 1
            connector = "└── " if last else "├── "
            child_prefix = prefix + ("    " if last else "│   ")
            suffix = "/" if kind == "dir" else ""
            lines.append(prefix + connector + path.name + suffix + (" [SKIPPED]" if skipped else ""))
            rows.append({
                "type": kind, "rel_path": path.relative_to(root).as_posix(),
                "name": path.name, "ext": path.suffix.lower() if kind == "file" else "",
                "size": info.st_size if kind == "file" else None,
                "mtime_utc": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()
                if kind == "file" else None,
                "skipped": skipped,
            })
            if kind == "dir" and not skipped:
                visit(path, child_prefix)

    visit(root, "")
    return rows, lines, errors


def export(root: Path, output: Path, *, overwrite: bool = False,
           include_skipped: bool = False, max_size: int | None = None) -> dict:
    if is_link(root):
        raise ValueError("The selected root must not be a link or junction.")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("The selected root must be a directory.")
    # A linked output could redirect writes or cause traversal of private folders.
    output = output.absolute()
    if any(is_link(part) for part in (output, *output.parents)):
        raise ValueError("The output path must not contain links or junctions.")
    output = output.resolve()
    if output == root:
        raise ValueError("Choose a separate output directory.")
    if max_size is not None and max_size < 0:
        raise ValueError("Maximum size must not be negative.")
    for name in OUTPUT_NAMES:
        target = output / name
        if is_link(target) or (target.exists() and (not overwrite or not target.is_file())):
            raise ValueError("Output already exists or is unsafe: " + name)
    rows, lines, errors = build_tree(root, output, include_skipped, max_size)
    payload = {
        "root": "<selected folder>",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {kind: sum(row["type"] == kind for row in rows) for kind in ("file", "dir", "link")},
        "errors": errors, "items": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidental replacement unless explicitly enabled.
    mode = "w" if overwrite else "x"
    with (output / OUTPUT_NAMES[0]).open(mode, encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    with (output / OUTPUT_NAMES[1]).open(mode, encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({key: csv_safe(value) for key, value in row.items()} for row in rows)
    with (output / OUTPUT_NAMES[2]).open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Game or mod folder to inventory")
    parser.add_argument("--output", required=True, type=Path, help="Separate directory for TXT, CSV and JSON")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing report files")
    parser.add_argument("--include-skipped", action="store_true", help="List skipped entries without expanding directories or links")
    parser.add_argument("--max-size", type=int, help="Skip files larger than this many bytes")
    args = parser.parse_args()
    try:
        payload = export(args.root, args.output, overwrite=args.overwrite,
                         include_skipped=args.include_skipped, max_size=args.max_size)
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(1, f"Inventory failed: {exc}\n")
    print(json.dumps({"counts": payload["counts"], "read_errors": len(payload["errors"])}))
    return 2 if payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
