# SPDX-License-Identifier: MIT
"""Verify a small, flat SHA-256 evidence manifest without writing to the target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path


MAX_MANIFEST_BYTES = 64 * 1024
MAX_FILES = 100
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
CHUNK_BYTES = 64 * 1024

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z", re.ASCII)
SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


class ManifestError(ValueError):
    """The manifest, target directory, or platform is unsuitable for verification."""


def _platform_supported() -> bool:
    """Check the descriptor-relative, no-follow APIs used by this example."""
    return (
        os.name == "posix"
        and all(hasattr(os, name) for name in (
            "O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC", "O_NONBLOCK"
        ))
        and os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
    )


def _require_supported_platform() -> None:
    if not _platform_supported():
        raise ManifestError(
            "requires POSIX no-follow, descriptor-relative file APIs; Windows is unsupported"
        )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError("duplicate JSON key")
        result[key] = value
    return result


def _exact_keys(value: object, keys: set[str], label: str) -> None:
    if type(value) is not dict or set(value) != keys:
        raise ManifestError(f"{label} must have exactly: {', '.join(sorted(keys))}")


def _file_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def load_manifest(path: Path) -> list[dict[str, object]]:
    """Load and strictly validate a bounded v1 manifest."""
    _require_supported_platform()
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ManifestError("manifest must be a regular file")
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise ManifestError(f"cannot read manifest: {exc.strerror}") from exc

    if len(raw) > MAX_MANIFEST_BYTES:
        raise ManifestError("manifest exceeds 64 KiB")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except ManifestError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ManifestError("manifest cannot be parsed as bounded UTF-8 JSON") from exc

    _exact_keys(document, {"version", "files"}, "manifest")
    if type(document["version"]) is not int or document["version"] != 1:
        raise ManifestError("unsupported manifest version")
    entries = document["files"]
    if type(entries) is not list or not 1 <= len(entries) <= MAX_FILES:
        raise ManifestError("files must contain 1 to 100 entries")

    names: set[str] = set()
    total = 0
    for index, entry in enumerate(entries):
        _exact_keys(entry, {"name", "size", "sha256"}, f"file #{index + 1}")
        name, size, digest = entry["name"], entry["size"], entry["sha256"]
        if type(name) is not str or not NAME.fullmatch(name):
            raise ManifestError(f"file #{index + 1} has an invalid flat filename")
        if name in names:
            raise ManifestError("duplicate filename")
        names.add(name)
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            raise ManifestError(f"file #{index + 1} has an invalid size")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ManifestError("declared total exceeds 64 MiB")
        if type(digest) is not str or not SHA256.fullmatch(digest):
            raise ManifestError(f"file #{index + 1} has an invalid SHA-256 digest")
    return entries


def verify_manifest(manifest_path: Path, directory: Path) -> list[str]:
    """Return a reason for each rejected entry; an empty list means all matched."""
    _require_supported_platform()
    entries = load_manifest(manifest_path)
    try:
        root_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise ManifestError(f"cannot open target directory: {exc.strerror}") from exc

    failures: list[str] = []
    try:
        for entry in entries:
            name = entry["name"]
            expected_size = entry["size"]
            try:
                # Reject special files before opening them. O_NOFOLLOW also protects
                # against a symlink substituted between this check and os.open.
                first = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                if not stat.S_ISREG(first.st_mode):
                    failures.append(f"{name}: not a regular file")
                    continue
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=root_fd)
                with os.fdopen(fd, "rb", buffering=0) as stream:
                    before = os.fstat(stream.fileno())
                    if not stat.S_ISREG(before.st_mode):
                        failures.append(f"{name}: not a regular file")
                        continue
                    if (first.st_dev, first.st_ino) != (before.st_dev, before.st_ino):
                        failures.append(f"{name}: file replaced before open")
                        continue
                    if before.st_size != expected_size or before.st_size > MAX_FILE_BYTES:
                        failures.append(f"{name}: size mismatch or limit exceeded")
                        continue
                    digest = hashlib.sha256()
                    count = 0
                    while count <= expected_size:
                        chunk = stream.read(min(CHUNK_BYTES, expected_size + 1 - count))
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > expected_size:
                            break
                        digest.update(chunk)
                    after = os.fstat(stream.fileno())
                if count != expected_size or _file_identity(before) != _file_identity(after):
                    failures.append(f"{name}: size changed during verification")
                elif digest.hexdigest() != entry["sha256"]:
                    failures.append(f"{name}: SHA-256 mismatch")
            except OSError as exc:
                failures.append(f"{name}: cannot verify ({exc.strerror})")
    finally:
        os.close(root_fd)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="v1 JSON manifest")
    parser.add_argument("directory", type=Path, help="directory containing flat files")
    args = parser.parse_args()
    try:
        failures = verify_manifest(args.manifest, args.directory)
    except ManifestError as exc:
        print(f"INVALID: {exc}")
        return 2
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: all manifest entries matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
