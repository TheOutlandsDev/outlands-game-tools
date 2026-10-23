#!/usr/bin/env python3
"""Build and verify a new source-only ZIP from an explicit SHA-256 inventory. MIT."""
from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from zipfile import BadZipFile, LargeZipFile, ZIP_STORED, ZipFile, ZipInfo

VERSION = "1.0.0"
MANIFEST = "SOURCE-MANIFEST.json"
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_FILES = 100_000
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_PATH_COMPONENTS = 128
BLOCK_BYTES = 64 * 1024
SUFFIXES = {".md", ".py", ".cs", ".csproj", ".ps1", ".json", ".yml", ".yaml",
            ".config", ".html", ".js", ".css", ".cfg", ".gsc", ".csv"}
SPECIAL = {"LICENSE", ".gitignore", ".gitattributes"}
SPECIAL_PATHS = {"tools/lua-syntax-checker/requirements.txt",
                 "tools/audio-integrity-checker/requirements.txt"}
EXCLUDED_PARTS = {".git", ".audit", ".validation", ".venv", "bin", "obj", "__pycache__",
                  ".pytest_cache", ".vs", "node_modules", "artifacts"}
DEVICE = re.compile(r"(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9]|LPT[1-9]) *(?:\..*)?\Z", re.I)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PREFIX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
MIT_REQUIRED = ("Permission is hereby granted, free of charge, to any person obtaining a copy",
                "The above copyright notice and this permission notice shall be included in all",
                'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND',
                "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE")


class BuildError(Exception):
    """A controlled, path-free failure code for public JSON reports."""


def fail(code: str) -> None:
    raise BuildError(code)


def fingerprint(value: os.stat_result) -> tuple:
    # CPython 3.12 Windows stat/fstat can disagree about ctime during updates.
    # File identity, mtime, length and byte hashes remain checked on both APIs.
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns if os.name != "nt" else 0)


def object_id(value: os.stat_result) -> tuple:
    return value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode)


def linked(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(getattr(value, "st_file_attributes", 0) & 0x400)


def portable_component(value: str) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= 255 and value not in {".", ".."}
            and not value.endswith((".", " ")) and not DEVICE.fullmatch(value)
            and all(32 <= ord(char) <= 126 and char not in '<>:"/\\|?*' for char in value))


def relative_name(value: str) -> str:
    if not isinstance(value, str) or len(value) > 1024 or "\\" in value:
        fail("manifest_path_invalid")
    parts = value.split("/")
    if not parts or len(parts) > MAX_PATH_COMPONENTS or any(not portable_component(part) for part in parts):
        fail("manifest_path_invalid")
    if any(part.casefold() in EXCLUDED_PARTS for part in parts[:-1]):
        fail("source_path_excluded")
    return value


def absolute_local(value: str | Path) -> Path:
    raw = os.fspath(value)
    if not raw or raw.startswith(("\\\\", "//")) or any(ord(char) < 32 for char in raw):
        fail("input_path_invalid")
    if re.match(r"^[A-Za-z]:(?:$|[^\\/])", raw):
        fail("input_path_invalid")
    result = Path(os.path.abspath(raw))
    if str(result).startswith(("\\\\", "//")):
        fail("input_path_invalid")
    # Windows ADS/device paths are rejected; the ordinary drive separator is allowed.
    tail = str(result)[len(result.anchor):]
    if ":" in tail:
        fail("input_path_invalid")
    if any(not portable_component(part) for part in result.parts[1:]):
        fail("input_path_invalid")
    return result


def checked_stat(path: Path, kind: str) -> os.stat_result:
    current = Path(path.anchor)
    sequence = [current]
    for part in path.parts[1:]:
        current = current / part
        sequence.append(current)
    last = None
    for index, candidate in enumerate(sequence):
        last = candidate.lstat()
        if linked(last):
            fail("linked_path_rejected")
        wanted = kind if index == len(sequence) - 1 else "directory"
        if wanted == "directory" and not stat.S_ISDIR(last.st_mode):
            fail("directory_required")
        if wanted == "file" and not stat.S_ISREG(last.st_mode):
            fail("regular_file_required")
    assert last is not None
    return last


def readonly(path: Path):
    before = checked_stat(path, "file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    stream = os.fdopen(fd, "rb")
    if fingerprint(os.fstat(stream.fileno())) != fingerprint(before):
        stream.close()
        fail("source_changed")
    return stream, before


def stable(path: Path, stream, before: os.stat_result) -> None:
    if (fingerprint(os.fstat(stream.fileno())) != fingerprint(before)
            or fingerprint(checked_stat(path, "file")) != fingerprint(before)):
        fail("source_changed")


def read_manifest(path: Path) -> tuple[bytes, os.stat_result]:
    stream, before = readonly(path)
    with stream:
        if before.st_size > MAX_MANIFEST_BYTES:
            fail("manifest_limit_exceeded")
        data = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(data) > MAX_MANIFEST_BYTES:
            fail("manifest_limit_exceeded")
        stable(path, stream, before)
    return data, before


def strict_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            fail("manifest_duplicate_key")
        result[key] = value
    return result


def parse_manifest(data: bytes) -> list[dict]:
    try:
        value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=strict_object,
                           parse_constant=lambda unused: fail("manifest_schema_invalid"))
    except (UnicodeError, ValueError, RecursionError):
        fail("manifest_json_invalid")
    if (not isinstance(value, dict) or set(value) != {"schema_version", "license", "files"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["license"] != "MIT" or not isinstance(value["files"], list)):
        fail("manifest_schema_invalid")
    records = value["files"]
    if not 1 <= len(records) <= MAX_FILES:
        fail("file_count_limit")
    # One trie node per component avoids retaining every joined ancestor string.
    # The explicit depth budget also bounds traversal work and nested structures.
    trie = {"children": {}, "file": False}
    has_root_license = False
    total = 0
    for record in records:
        if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
            fail("manifest_record_invalid")
        name = relative_name(record["path"])
        pieces = name.split("/")
        node = trie
        for piece in pieces:
            if node["file"]:
                fail("manifest_path_collision")
            children = node["children"]
            folded_piece = piece.casefold()
            if folded_piece not in children:
                children[folded_piece] = {"spelling": piece, "children": {}, "file": False}
            node = children[folded_piece]
            if node["spelling"] != piece:
                fail("manifest_path_collision")
        if node["file"] or node["children"]:
            fail("manifest_path_collision")
        node["file"] = True
        if name.casefold() == MANIFEST.casefold():
            fail("manifest_self_listed")
        has_root_license = has_root_license or name == "LICENSE"
        if (type(record["bytes"]) is not int or not 0 <= record["bytes"] <= MAX_FILE_BYTES
                or not isinstance(record["sha256"], str) or not SHA256.fullmatch(record["sha256"])):
            fail("manifest_record_invalid")
        source = PurePosixPath(name)
        if source.name not in SPECIAL and name not in SPECIAL_PATHS and source.suffix.lower() not in SUFFIXES:
            fail("source_type_rejected")
        total += record["bytes"]
        if total > MAX_TOTAL_BYTES:
            fail("total_byte_limit")
    if not has_root_license:
        fail("root_license_required")
    return sorted(records, key=lambda row: row["path"])


def source_bytes(root: Path, record: dict, destination=None) -> os.stat_result:
    """Hash and validate one bounded UTF-8 source, optionally streaming it into a ZIP."""
    path = root.joinpath(*record["path"].split("/"))
    stream, before = readonly(path)
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
    total = 0
    license_text = [] if record["path"] == "LICENSE" else None
    with stream:
        if before.st_size != record["bytes"]:
            fail("source_manifest_mismatch")
        while block := stream.read(BLOCK_BYTES):
            total += len(block)
            if total > record["bytes"] or total > MAX_FILE_BYTES:
                fail("source_manifest_mismatch")
            if b"\0" in block:
                fail("source_text_required")
            try:
                decoded = decoder.decode(block)
            except UnicodeError:
                fail("source_text_required")
            if license_text is not None:
                license_text.append(decoded)
            digest.update(block)
            if destination is not None:
                destination.write(block)
        try:
            tail = decoder.decode(b"", final=True)
        except UnicodeError:
            fail("source_text_required")
        if license_text is not None:
            license_text.append(tail)
        stable(path, stream, before)
    if total != record["bytes"] or digest.hexdigest() != record["sha256"]:
        fail("source_manifest_mismatch")
    if license_text is not None:
        text = " ".join("".join(license_text).split())
        if not text.startswith("MIT License ") or any(" ".join(part.split()) not in text for part in MIT_REQUIRED):
            fail("root_license_not_mit")
    return before


def new_output(path: Path):
    checked_stat(path.parent, "directory")
    stream = path.open("xb")
    return stream, os.fstat(stream.fileno())


def ensure_absent(path: Path) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    fail("output_exists")


def remove_owned(path: Path, identity: os.stat_result) -> bool:
    try:
        if object_id(path.lstat()) != object_id(identity):
            return False
        path.unlink()
        return True
    except OSError:
        return False


def zip_info(name: str, size: int) -> ZipInfo:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = ZIP_STORED
    info.file_size = size
    return info


def verify_archive(stream, expected: dict[str, tuple[int, str]]) -> None:
    stream.seek(0)
    with ZipFile(stream, "r") as archive:
        infos = archive.infolist()
        if [entry.filename for entry in infos] != sorted(expected):
            fail("archive_members_mismatch")
        for info in infos:
            size, wanted = expected[info.filename]
            if (info.file_size != size or info.compress_type != ZIP_STORED
                    or info.date_time != (1980, 1, 1, 0, 0, 0)
                    or info.external_attr != 0o100644 << 16 or info.is_dir()):
                fail("archive_metadata_mismatch")
            digest, count = hashlib.sha256(), 0
            with archive.open(info, "r") as member:
                while block := member.read(BLOCK_BYTES):
                    count += len(block)
                    if count > size:
                        fail("archive_bytes_mismatch")
                    digest.update(block)
            if count != size or digest.hexdigest() != wanted:
                fail("archive_bytes_mismatch")


def build(source_root: str | Path, output: str | Path, manifest: str | Path | None = None,
          prefix: str | None = None) -> dict:
    """Create two exclusive outputs. Failures remove only files this call created and still owns."""
    owned = []
    try:
        root = absolute_local(source_root)
        checked_stat(root, "directory")
        manifest_path = root / MANIFEST if manifest is None else absolute_local(manifest)
        if manifest_path != root / MANIFEST:
            fail("canonical_manifest_required")
        target = absolute_local(output)
        checksum = target.with_name(target.name + ".sha256")
        if target.suffix.lower() != ".zip":
            fail("zip_output_required")
        if target.is_relative_to(root) or checksum.is_relative_to(root):
            fail("output_inside_source")
        checked_stat(target.parent, "directory")
        ensure_absent(target)
        ensure_absent(checksum)
        if prefix is not None and (not PREFIX.fullmatch(prefix) or not portable_component(prefix)):
            fail("prefix_invalid")
        lead = prefix + "/" if prefix else ""
        data, manifest_before = read_manifest(manifest_path)
        records = parse_manifest(data)
        states = {row["path"]: source_bytes(root, row) for row in records}
        expected = {lead + row["path"]: (row["bytes"], row["sha256"]) for row in records}
        expected[lead + MANIFEST] = len(data), hashlib.sha256(data).hexdigest()
        archive_stream, identity = new_output(target)
        owned.append((target, identity))
        try:
            checksum_stream, identity = new_output(checksum)
            owned.append((checksum, identity))
        except BaseException:
            archive_stream.close()
            raise
        with archive_stream, checksum_stream:
            # Store rather than compress: fixed metadata and original bytes do not depend on zlib versions.
            with ZipFile(archive_stream, "w", compression=ZIP_STORED, allowZip64=True) as archive:
                members = {row["path"]: row for row in records}
                members[MANIFEST] = None
                for name in sorted(members):
                    row = members[name]
                    size = len(data) if row is None else row["bytes"]
                    with archive.open(zip_info(lead + name, size), "w") as member:
                        if row is None:
                            member.write(data)
                        else:
                            before = source_bytes(root, row, member)
                            if fingerprint(before) != fingerprint(states[name]):
                                fail("source_changed")
            archive_stream.flush()
            os.fsync(archive_stream.fileno())
            for row in records:
                if fingerprint(source_bytes(root, row)) != fingerprint(states[row["path"]]):
                    fail("source_changed")
            latest, latest_state = read_manifest(manifest_path)
            if latest != data or fingerprint(latest_state) != fingerprint(manifest_before):
                fail("source_changed")
            # Read via a separate checked readonly handle; output streams remain exclusively owned.
            review, before = readonly(target)
            with review:
                if object_id(before) != object_id(owned[0][1]):
                    fail("output_changed")
                verify_archive(review, expected)
                review.seek(0)
                digest = hashlib.sha256()
                while block := review.read(BLOCK_BYTES):
                    digest.update(block)
                stable(target, review, before)
            if object_id(checked_stat(checksum, "file")) != object_id(owned[1][1]):
                fail("output_changed")
            checksum_stream.write((digest.hexdigest() + "  " + target.name + "\n").encode("ascii"))
            checksum_stream.flush()
            os.fsync(checksum_stream.fileno())
            stable(target, archive_stream, before)
            if object_id(os.fstat(checksum_stream.fileno())) != object_id(checked_stat(checksum, "file")):
                fail("output_changed")
            # Also catch changes made while the completed archive was being verified.
            for row in records:
                if fingerprint(source_bytes(root, row)) != fingerprint(states[row["path"]]):
                    fail("source_changed")
            latest, latest_state = read_manifest(manifest_path)
            if latest != data or fingerprint(latest_state) != fingerprint(manifest_before):
                fail("source_changed")
        return {"schema_version": 1, "tool_version": VERSION, "status": "PASS",
                "source_files": len(records), "archive_members": len(expected),
                "source_bytes": sum(row["bytes"] for row in records),
                "archive_bytes": target.stat().st_size, "sha256": digest.hexdigest(),
                "archive_name": target.name, "checksum_name": checksum.name,
                "all_archive_bytes_match": True}
    except (BuildError, OSError, ValueError, UnicodeError, RuntimeError, RecursionError,
            BadZipFile, LargeZipFile) as error:
        removed = sum(remove_owned(path, identity) for path, identity in reversed(owned))
        code = str(error) if isinstance(error, BuildError) else "io_or_archive_failure"
        return {"schema_version": 1, "tool_version": VERSION, "status": "FAIL", "code": code,
                "created_outputs": len(owned), "removed_outputs": removed,
                "partial_outputs_possible": removed != len(owned)}
    except BaseException:
        for path, identity in reversed(owned):
            remove_owned(path, identity)
        raise


class Parser(argparse.ArgumentParser):
    def error(self, message):
        fail("arguments_invalid")


def main(argv: list[str] | None = None) -> int:
    parser = Parser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--source-root", required=True, help="Existing local reviewed source tree")
    parser.add_argument("--manifest", help="Canonical SOURCE-MANIFEST.json inside that root")
    parser.add_argument("--output", required=True, help="New .zip outside source with an existing local parent")
    parser.add_argument("--prefix", help="Optional portable root folder inside the ZIP")
    try:
        args = parser.parse_args(argv)
        result = build(args.source_root, args.output, args.manifest, args.prefix)
    except BuildError as error:
        result = {"schema_version": 1, "tool_version": VERSION, "status": "FAIL", "code": str(error),
                  "created_outputs": 0, "removed_outputs": 0, "partial_outputs_possible": False}
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
