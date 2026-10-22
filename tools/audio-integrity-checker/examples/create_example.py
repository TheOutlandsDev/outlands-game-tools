#!/usr/bin/env python3
"""Create original toy audio in a new directory; never read or copy game data."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import stat
import struct
import sys
import wave


def new_destination(value: str) -> Path:
    """Reject linked ancestors and require one new child of an existing parent."""
    candidate = Path(value)
    if ".." in candidate.parts or str(candidate).startswith(("\\\\", "//")):
        raise ValueError("use a local path without parent traversal")
    destination = Path(os.path.abspath(candidate))
    for ancestor in (destination.parent, *destination.parent.parents):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError("linked or reparse-point destination ancestors are refused")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("the destination parent must be an existing directory")
    # mkdir is exclusive: no existing directory or file can be reused.
    destination.mkdir()
    return destination


def put_bytes(destination: Path, relative: str, content: bytes) -> None:
    path = destination / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)


def put_wav(destination: Path, relative: str, *, empty: bool = False) -> None:
    path = destination / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"" if empty else b"".join(
        struct.pack("<h", round(8192 * math.sin(2 * math.pi * 440 * index / 8000)))
        for index in range(80)
    )
    with path.open("xb") as stream:
        with wave.open(stream, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(frames)


def create(destination: Path) -> None:
    put_wav(destination, "source/valid.wav")
    put_wav(destination, "source/empty.wav", empty=True)
    put_bytes(destination, "source/broken.ogg", b"Original example: deliberately not an Ogg stream.\n")
    put_bytes(destination, "source/ignored.txt", b"The audio scan ignores this suffix.\n")

    put_bytes(destination, "mo2/mods/AudioLow/shared.wav", b"Original masked invalid WAV example.\n")
    put_wav(destination, "mo2/mods/AudioHigh/shared.wav")
    put_wav(destination, "mo2/base/base.wav")
    put_wav(destination, "mo2/overwrite/shared.wav")
    put_bytes(
        destination,
        "mo2/profile/modlist.txt",
        b"# Native saved order: first enabled entry has highest mod priority.\n+AudioHigh\n+AudioLow\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination", required=True,
        help="new local directory; parent must exist and no ancestors may be links",
    )
    args = parser.parse_args(argv)
    try:
        destination = new_destination(args.destination)
        create(destination)
    except (OSError, ValueError) as exc:
        print(f"Example creation failed: {exc}", file=sys.stderr)
        print("A newly created directory may contain a partial example; use a new destination for a retry.", file=sys.stderr)
        return 1
    print(f"Created original example inputs in {destination}")
    print("Source scan: expected exit 2 (one pass, one decode error, one empty-audio finding).")
    print("MO2 scan with base and Overwrite: expected exit 0 (two effective passing audio files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
