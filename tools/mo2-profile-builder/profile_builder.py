#!/usr/bin/env python3
"""Create a separate MO2 comparison profile. Python 3.12+, MIT licensed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

VERSION = "1.0.0"
FILES = ("modlist.txt", "archives.txt", "initweaks.ini", "lockedorder.txt", "settings.ini")
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_DIRECTORY_ENTRIES = 4096
REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
DEVICE = re.compile(r"^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)", re.I)
LIMITATIONS = [
    "Only the five documented saved-profile files are considered; saves, plugins.txt, loadorder.txt, mod files, and other files are not copied.",
    "The new profile shares the same mods, game installation, and potentially saves, MCM settings, overwrite, and application data. It is not an isolated game copy.",
    "Disabling mods may break existing saves. Use an appropriate new game or disposable test save; profile creation does not verify game compatibility.",
    "Close MO2, the game, and all profile writers before applying. --confirm-closed is a user attestation, not process detection.",
    "Source identity, bytes, and directory inventory are checked again, but this is not an atomic snapshot or a hostile-filesystem sandbox.",
    "Destination creation is exclusive but is not an atomic directory transaction. Do not use the destination until a successful report is returned.",
    "Reports omit absolute roots and file contents. Mod names, profile filenames, and hashes may still be sensitive; review before sharing.",
]


class BuildError(Exception):
    """A public error code with no raw operating-system details."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def safe_name(value: str) -> bool:
    return bool(value and value not in (".", "..") and len(value) <= 255
                and value == value.strip() and not value.endswith(".")
                and not INVALID.search(value) and not DEVICE.match(value))


def absolute(value: str) -> Path:
    if (not value or "\x00" in value or value.startswith(("\\\\", "//"))
            or re.match(r"^[A-Za-z]:(?:$|[^\\/])", value)):
        raise BuildError("unsupported_path")
    try:
        raw_path = Path(value)
        for part in raw_path.parts:
            if part != raw_path.anchor and part not in (".", "..") and not safe_name(part):
                raise BuildError("unsafe_path_component")
        path = Path(os.path.abspath(value))
    except (OSError, ValueError):
        raise BuildError("invalid_path") from None
    # Check Windows-compatible components on every platform; reject ADS/devices.
    for part in path.parts[1:]:
        if not safe_name(part):
            raise BuildError("unsafe_path_component")
    return path


def linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & REPARSE)


def identity(info: os.stat_result) -> tuple:
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns


def same_object(info: os.stat_result) -> tuple:
    return info.st_dev, info.st_ino, info.st_mode


def check_path(path: Path, *, directory: bool = False) -> os.stat_result:
    result = None
    for component in (*reversed(path.parents), path):
        try:
            result = component.lstat()
        except OSError:
            raise BuildError("missing_or_unreadable_path") from None
        if linked(result):
            raise BuildError("linked_path")
        if component != path and not stat.S_ISDIR(result.st_mode):
            raise BuildError("invalid_directory")
    if directory and not stat.S_ISDIR(result.st_mode):
        raise BuildError("invalid_directory")
    return result


def ensure_absent(path: Path) -> None:
    check_path(path.parent, directory=True)
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    except OSError:
        raise BuildError("unreadable_destination") from None
    else:
        raise BuildError("destination_exists")
    # Do not create case variants of existing files even on a case-sensitive host.
    try:
        with os.scandir(path.parent) as entries:
            for index, entry in enumerate(entries):
                if index >= MAX_DIRECTORY_ENTRIES:
                    raise BuildError("directory_entry_limit")
                if entry.name.casefold() == path.name.casefold():
                    raise BuildError("destination_exists")
    except OSError:
        raise BuildError("unreadable_directory") from None


def within(left: Path, right: Path) -> bool:
    a, b = left.as_posix().casefold(), right.as_posix().casefold()
    return a == b or a.startswith(b.rstrip("/") + "/")


def inventory(source: Path) -> tuple[str, ...]:
    check_path(source, directory=True)
    found = {}
    try:
        with os.scandir(source) as entries:
            for index, entry in enumerate(entries):
                if index >= MAX_DIRECTORY_ENTRIES:
                    raise BuildError("directory_entry_limit")
                key = entry.name.casefold()
                if key in FILES:
                    if key in found or entry.name != key:
                        raise BuildError("ambiguous_profile_filename")
                    info = check_path(source / entry.name)
                    if not stat.S_ISREG(info.st_mode):
                        raise BuildError("nonregular_profile_file")
                    found[key] = entry.name
    except OSError:
        raise BuildError("unreadable_directory") from None
    if "modlist.txt" not in found:
        raise BuildError("missing_modlist")
    return tuple(name for name in FILES if name in found)


def read_file(path: Path) -> tuple[bytes, tuple]:
    before = check_path(path)
    if not stat.S_ISREG(before.st_mode):
        raise BuildError("nonregular_profile_file")
    if before.st_size > MAX_FILE_BYTES:
        raise BuildError("profile_file_size_limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if identity(before) != identity(opened) or linked(opened):
                raise BuildError("source_changed")
            data = stream.read(MAX_FILE_BYTES + 1)
            after = os.fstat(stream.fileno())
    except OSError:
        raise BuildError("unreadable_profile_file") from None
    if len(data) > MAX_FILE_BYTES:
        raise BuildError("profile_file_size_limit")
    if identity(before) != identity(after) or identity(check_path(path)) != identity(before):
        raise BuildError("source_changed")
    return data, identity(before)


def transform(data: bytes, disable: list[str]) -> tuple[bytes, dict]:
    if not disable:
        raise BuildError("no_disable_requests")
    if any(not safe_name(name) or name.endswith("_separator") for name in disable):
        raise BuildError("unsafe_mod_request")
    if len(set(name.casefold() for name in disable)) != len(disable):
        raise BuildError("duplicate_disable_request")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        raise BuildError("unsupported_modlist_encoding") from None
    if "\x00" in text or any(ord(c) < 32 and c not in "\r\n\t" for c in text):
        raise BuildError("invalid_modlist_text")
    # splitlines(keepends=True) retains CRLF/LF/CR and an absent final newline.
    lines = text.splitlines(keepends=True)
    rows = {}
    enabled = 0
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        if not body or body.startswith("#"):
            continue
        if body[0] not in "+-":
            raise BuildError("unsupported_modlist_entry")
        name = body[1:]
        if not safe_name(name):
            raise BuildError("unsafe_modlist_entry")
        key = name.casefold()
        if key in rows:
            raise BuildError("duplicate_modlist_entry")
        rows[key] = (name, body[0], index)
        enabled += int(body[0] == "+" and not name.endswith("_separator"))
    changed = []
    for name in disable:
        row = rows.get(name.casefold())
        if row is None:
            raise BuildError("requested_mod_missing")
        actual, marker, index = row
        if actual != name:
            raise BuildError("requested_mod_case_mismatch")
        if marker != "+":
            raise BuildError("requested_mod_already_disabled")
        lines[index] = "-" + lines[index][1:]
        changed.append(name)
    output = "".join(lines).encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        output = b"\xef\xbb\xbf" + output
    return output, {"enabled_before": enabled, "enabled_after": enabled - len(changed),
                    "disabled_mods": changed, "priority_order_preserved": True}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_file(path: Path, data: bytes) -> tuple:
    check_path(path.parent, directory=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError:
        raise BuildError("exclusive_file_creation_failed") from None
    created = same_object(os.fstat(descriptor))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            owned = identity(os.fstat(stream.fileno()))
        return owned
    except OSError:
        # Caller records no ownership until success; remove this incomplete file
        # only if its inode still matches the descriptor initially created here.
        try:
            current = path.lstat()
            if not linked(current) and same_object(current) == created:
                path.unlink()
        except OSError:
            pass
        raise BuildError("file_write_failed") from None


def cleanup(directory: Path, owner: tuple | None, owned: dict[str, tuple]) -> bool:
    if owner is None:
        return True
    try:
        current = directory.lstat()
        if linked(current) or same_object(current) != owner:
            return False
        complete = True
        for name, expected in reversed(tuple(owned.items())):
            path = directory / name
            try:
                info = path.lstat()
                if not linked(info) and identity(info) == expected:
                    path.unlink()
                else:
                    complete = False
            except FileNotFoundError:
                pass
            except OSError:
                complete = False
        try:
            directory.rmdir()  # Deliberately never recursive.
        except OSError:
            complete = False
        return complete
    except FileNotFoundError:
        return True
    except OSError:
        return False


def prepare(source: Path, destination: Path, disable: list[str]) -> tuple[dict, dict, dict, tuple]:
    check_path(source, directory=True)
    ensure_absent(destination)
    if within(source, destination) or within(destination, source):
        raise BuildError("source_destination_overlap")
    names = inventory(source)
    source_identity = same_object(check_path(source, directory=True))
    originals, identities = {}, {}
    for name in names:
        originals[name], identities[name] = read_file(source / name)
    transformed, changes = transform(originals["modlist.txt"], disable)
    expected = dict(originals)
    expected["modlist.txt"] = transformed
    report = {"schema_version": 1, "tool": "mo2-profile-builder", "tool_version": VERSION,
              "mode": "preview", "status": "PREVIEW", "complete": True,
              "changes": changes, "files": [
                  {"path": name, "bytes_before": len(originals[name]), "bytes_after": len(expected[name]),
                   "source_sha256": digest(originals[name]), "destination_sha256": digest(expected[name]),
                   "changed": originals[name] != expected[name]} for name in names],
              "source_verified_unchanged": False, "destination_verified": False,
              "limitations": LIMITATIONS}
    return report, originals, expected, (names, identities, source_identity)


def verify_source(source: Path, originals: dict, state: tuple) -> None:
    names, identities, source_identity = state
    if same_object(check_path(source, directory=True)) != source_identity or inventory(source) != names:
        raise BuildError("source_changed")
    for name in names:
        data, current = read_file(source / name)
        if data != originals[name] or current != identities[name]:
            raise BuildError("source_changed")


def verify_destination(destination: Path, owner: tuple, expected: dict) -> None:
    if same_object(check_path(destination, directory=True)) != owner:
        raise BuildError("destination_changed")
    try:
        with os.scandir(destination) as entries:
            names = []
            for index, entry in enumerate(entries):
                if index >= len(FILES):
                    raise BuildError("unexpected_destination_file")
                names.append(entry.name)
    except OSError:
        raise BuildError("destination_verification_failed") from None
    if set(names) != set(expected):
        raise BuildError("unexpected_destination_file")
    for name, data in expected.items():
        if read_file(destination / name)[0] != data:
            raise BuildError("destination_verification_failed")


def apply(source: Path, destination: Path, originals: dict, expected: dict, state: tuple) -> None:
    stage = destination.parent / (".mo2-profile-stage-" + uuid.uuid4().hex)
    stage_owner = destination_owner = None
    stage_files, destination_files = {}, {}
    try:
        check_path(destination.parent, directory=True)
        stage.mkdir(mode=0o700)
        stage_owner = same_object(check_path(stage, directory=True))
        for name, data in expected.items():
            stage_files[name] = create_file(stage / name, data)
        for name, data in expected.items():
            if read_file(stage / name)[0] != data:
                raise BuildError("staging_verification_failed")
        verify_source(source, originals, state)
        ensure_absent(destination)
        destination.mkdir(mode=0o700)
        destination_owner = same_object(check_path(destination, directory=True))
        for name, data in expected.items():
            destination_files[name] = create_file(destination / name, data)
        verify_destination(destination, destination_owner, expected)
        verify_source(source, originals, state)
        if not cleanup(stage, stage_owner, stage_files):
            raise BuildError("staging_cleanup_incomplete")
        stage_owner = None
    except (BuildError, OSError):
        rolled_back = cleanup(destination, destination_owner, destination_files)
        stage_clean = cleanup(stage, stage_owner, stage_files)
        if not rolled_back or not stage_clean:
            raise BuildError("rollback_incomplete") from None
        raise BuildError("apply_failed_rolled_back") from None


def output_preflight(output: Path, source: Path, destination: Path) -> None:
    if within(output, source) or within(output, destination) or within(source, output) or within(destination, output):
        raise BuildError("output_overlaps_inputs")
    ensure_absent(output)


def error_report(code: str, mode: str) -> dict:
    return {"schema_version": 1, "tool": "mo2-profile-builder", "tool_version": VERSION,
            "mode": mode, "status": "ERROR", "complete": False, "error": code,
            "limitations": LIMITATIONS}


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default error embeds unknown arguments and supplied values.
        # Do not echo those strings into a potentially shareable CLI report.
        print(json.dumps(error_report("invalid_arguments", "preview"), indent=2))
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    parser = Parser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--source-profile", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--disable", action="append", required=True, metavar="EXACT_MOD_NAME")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-closed", action="store_true", help="Attest MO2, game, and profile writers are closed")
    parser.add_argument("--output", help="New JSON report outside source and destination; existing parent required")
    args = parser.parse_args(argv)
    mode = "apply" if args.apply else "preview"
    output_path = None
    output_owner = None
    output_stream = None
    try:
        if sys.version_info < (3, 12):
            raise BuildError("unsupported_python")
        source, destination = absolute(args.source_profile), absolute(args.destination)
        if args.apply and not args.confirm_closed:
            raise BuildError("closed_attestation_required")
        if args.confirm_closed and not args.apply:
            raise BuildError("closed_attestation_requires_apply")
        if args.output:
            output_path = absolute(args.output)
            output_preflight(output_path, source, destination)
        report, originals, expected, state = prepare(source, destination, args.disable)
        verify_source(source, originals, state)
        report["source_verified_unchanged"] = True
        # Reserve a safe report path before any profile mutation.
        if output_path:
            check_path(output_path.parent, directory=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(output_path, flags, 0o600)
            output_owner = same_object(os.fstat(descriptor))
            output_stream = os.fdopen(descriptor, "wb")
        if args.apply:
            apply(source, destination, originals, expected, state)
            report.update(mode="apply", status="APPLIED", destination_verified=True)
        code = 0
    except (BuildError, OSError, ValueError):
        exception = sys.exc_info()[1]
        report = error_report(exception.code if isinstance(exception, BuildError) else "filesystem_operation_failed", mode)
        code = 1
    payload = (json.dumps(report, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    try:
        if output_stream:
            with output_stream:
                if same_object(check_path(output_path)) != output_owner:
                    raise BuildError("report_destination_changed")
                output_stream.write(payload)
                output_stream.flush()
                os.fsync(output_stream.fileno())
        else:
            sys.stdout.buffer.write(payload)
    except (OSError, BuildError):
        # Profile creation may already have committed; never claim it was undone.
        sys.stderr.write("Report write failed. Check the requested destination before retrying.\n")
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
