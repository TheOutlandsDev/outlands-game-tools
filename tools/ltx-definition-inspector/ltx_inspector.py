#!/usr/bin/env python3
"""Inspect a conservative LTX declaration/include graph without evaluating values.

Copyright (c) 2026 TheOutlandsDev. Distributed under the repository MIT license.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import re
import stat
import sys

VERSION = "1.0.0"
IDENTIFIER = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
HEADER = re.compile(rf"\[({IDENTIFIER})\](?:\s*:\s*({IDENTIFIER}(?:\s*,\s*{IDENTIFIER})*))?")
INCLUDE = re.compile(r'#include\s+"([^"\r\n]+)"')
KEY = re.compile(r"[A-Za-z0-9_$][A-Za-z0-9_.$-]*")
MAX_DIRECTORY_ENTRIES = 100000
RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$",
            *(f"COM{i}" for i in "123456789¹²³"),
            *(f"LPT{i}" for i in "123456789¹²³")}


class CheckError(Exception):
    """An intentionally sanitized machine-readable failure."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, "ltx-definition-inspector: INVALID_ARGUMENTS (use --help)\n")


def positive(value: str) -> int:
    try:
        number = int(value)
    except (ValueError, OverflowError):
        raise argparse.ArgumentTypeError("expected a positive integer") from None
    if number < 1 or number >= sys.maxsize:
        raise argparse.ArgumentTypeError("expected an integer from 1 to sys.maxsize - 1")
    return number


def component(value: str) -> None:
    if (not value or value in {".", ".."} or value[-1] in ". "
            or any(ord(char) < 32 or ord(char) == 127 or char in '<>:"|?*' for char in value)
            or value.split(".")[0].rstrip(" ").upper() in RESERVED):
        raise CheckError("UNSAFE_PATH")


def relative(value: str, parent: str = "", *, entry: bool = False) -> str:
    value = value.replace("\\", "/")
    if not value or value.startswith("/") or ":" in value:
        raise CheckError("UNSAFE_PATH")
    parts = parent.split("/") if parent else []
    for item in value.split("/"):
        if item == "..":
            if entry or not parts:
                raise CheckError("UNSAFE_PATH")
            parts.pop()
        elif item == ".":
            if entry:
                raise CheckError("UNSAFE_PATH")
        else:
            component(item)
            parts.append(item)
    if not parts:
        raise CheckError("UNSAFE_PATH")
    result = "/".join(parts)
    if Path(result).suffix.lower() not in {".ltx", ".ini"}:
        raise CheckError("UNSUPPORTED_FILE_TYPE")
    return result


def absolute(value: str) -> Path:
    normalized = value.replace("\\", "/")
    if (normalized.startswith("//") or "\x00" in value
            or (re.match(r"^[A-Za-z]:", normalized) and not re.match(r"^[A-Za-z]:/", normalized))):
        raise CheckError("UNSAFE_PATH")
    path = Path(os.path.abspath(value))
    # Windows abspath can turn a raw device basename such as NUL into a
    # device-namespace anchor. Validate again after normalization, before I/O.
    if str(path).replace("\\", "/").startswith("//"):
        raise CheckError("UNSAFE_PATH")
    for item in path.parts[1:]:
        component(item)
    return path


def not_link(info: os.stat_result) -> None:
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise CheckError("LINK_OR_REPARSE_POINT")


def ancestry(path: Path, *, directory: bool = False) -> os.stat_result:
    try:
        for item in [*reversed(path.parents), path]:
            info = item.lstat()
            not_link(info)
            if item != path and not stat.S_ISDIR(info.st_mode):
                raise CheckError("NOT_A_DIRECTORY")
        if directory and not stat.S_ISDIR(info.st_mode):
            raise CheckError("NOT_A_DIRECTORY")
        return info
    except OSError:
        raise CheckError("INPUT_UNAVAILABLE") from None


def checked_child(root: Path, name: str) -> tuple[Path, os.stat_result]:
    cursor = root
    ancestry(root, directory=True)
    try:
        for index, part in enumerate(name.split("/")):
            matches = case_matches(cursor, part)
            if len(matches) > 1:
                raise CheckError("CASE_AMBIGUITY")
            if not matches:
                raise CheckError("MISSING_FILE")
            if matches[0] != part:
                raise CheckError("CASE_MISMATCH")
            cursor /= part
            info = cursor.lstat()
            not_link(info)
            if index < len(name.split("/")) - 1 and not stat.S_ISDIR(info.st_mode):
                raise CheckError("NOT_A_DIRECTORY")
        if not stat.S_ISREG(info.st_mode):
            raise CheckError("NOT_A_REGULAR_FILE")
        return cursor, info
    except OSError:
        raise CheckError("INPUT_UNAVAILABLE") from None


def case_matches(directory: Path, name: str) -> list[str]:
    """Stream a bounded directory lookup without os.listdir's eager allocation."""
    matches: list[str] = []
    with os.scandir(directory) as entries:
        for count, item in enumerate(entries, 1):
            if count > MAX_DIRECTORY_ENTRIES:
                raise CheckError("DIRECTORY_ENTRY_LIMIT")
            if item.name.casefold() == name.casefold() and len(matches) < 2:
                matches.append(item.name)
    return matches


def identity(info: os.stat_result) -> tuple:
    # CPython 3.12 Windows lstat/fstat can expose different legacy ctime values
    # for the same unchanged file. It is not a portable cross-API identity field.
    common = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    return common if os.name == "nt" else (*common, info.st_ctime_ns)


def read_source(root: Path, name: str, limit: int, remaining: int) -> bytes:
    path, before = checked_child(root, name)
    if before.st_size > limit:
        raise CheckError("FILE_BYTE_LIMIT")
    if before.st_size > remaining:
        raise CheckError("TOTAL_BYTE_LIMIT")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        with os.fdopen(os.open(path, flags), "rb") as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or identity(opened) != identity(before):
                raise CheckError("SOURCE_CHANGED")
            data = handle.read(min(before.st_size + 1, limit + 1, remaining + 1))
            after = os.fstat(handle.fileno())
        _, final = checked_child(root, name)
        if identity(before) != identity(after) or identity(before) != identity(final):
            raise CheckError("SOURCE_CHANGED")
        if len(data) > limit:
            raise CheckError("FILE_BYTE_LIMIT")
        return data
    except OSError:
        raise CheckError("READ_ERROR") from None


def strip_comment(line: str) -> str:
    quoted = False
    index = 0
    while index < len(line):
        if line[index] == '"':
            if index and line[index - 1] == "\\":
                raise CheckError("UNSUPPORTED_QUOTING")
            quoted = not quoted
        elif not quoted and (line[index] == ";" or line[index:index + 2] == "//"):
            return line[:index].strip()
        index += 1
    if quoted:
        raise CheckError("UNSUPPORTED_MULTILINE_OR_QUOTING")
    return line.strip()


def cycles(graph: dict[str, list[str]], budget: int) -> tuple[list[list[str]], bool]:
    """Find DFS back-edge cycles with an iterative traversal, not all simple cycles."""
    color: dict[str, int] = {}
    found: list[list[str]] = []
    used = 0
    truncated = False
    costs = {name: len(json.dumps(name, ensure_ascii=True)) + 16 for name in graph}
    character_budget = 4 * 1024 * 1024
    characters = 0
    for origin in graph:
        if color.get(origin):
            continue
        color[origin] = 1
        active = [origin]
        prefix = [0, costs[origin]]
        positions = {origin: 0}
        stack = [(origin, iter(graph[origin]))]
        while stack:
            name, children = stack[-1]
            child = next(children, None)
            if child is None:
                stack.pop()
                color[name] = 2
                positions.pop(name)
                active.pop()
                prefix.pop()
            elif child not in graph:
                continue
            elif not color.get(child):
                color[child] = 1
                positions[child] = len(active)
                active.append(child)
                prefix.append(prefix[-1] + costs[child])
                stack.append((child, iter(graph[child])))
            elif color[child] == 1:
                length = len(active) - positions[child] + 1
                cost = prefix[-1] - prefix[positions[child]] + costs[child]
                if used + length > budget or characters + cost > character_budget:
                    truncated = True
                else:
                    found.append([*active[positions[child]:], child])
                    used += length
                    characters += cost
    return found, truncated


def inspect(args: argparse.Namespace) -> tuple[dict, int]:
    report = {"schema_version": 1, "tool": "ltx-definition-inspector", "version": VERSION,
              "complete": True, "encoding": args.encoding, "entries": [], "files": [],
              "includes": [], "definitions": [], "findings": [], "errors": []}
    report["limits"] = {"max_file_bytes": args.max_file_bytes, "max_total_bytes": args.max_total_bytes,
                        "max_files": args.max_files, "max_depth": args.max_depth,
                        "max_records": args.max_records, "max_report_bytes": args.max_report_bytes,
                        "directory_entries_per_lookup": MAX_DIRECTORY_ENTRIES}
    findings, errors = report["findings"], report["errors"]

    def error(code: str, file: str | None = None, line: int | None = None) -> None:
        item: dict = {"code": code}
        if file is not None:
            item["file"] = file
        if line is not None:
            item["line"] = line
        errors.append(item)
        report["complete"] = False

    try:
        root = absolute(args.root)
        ancestry(root, directory=True)
        entries = [relative(item, entry=True) for item in args.entry]
        if len({item.casefold() for item in entries}) != len(entries):
            raise CheckError("DUPLICATE_ENTRY")
        report["entries"] = entries
    except CheckError as exc:
        error(exc.code)
        return finish(report)

    pending = [(name, 0) for name in reversed(entries)]
    visited: set[str] = set()
    graph: dict[str, list[str]] = {}
    incoming: Counter = Counter()
    total = 0
    records = 0
    while pending:
        name, depth = pending.pop()
        if name in visited:
            continue
        if depth > args.max_depth:
            error("INCLUDE_DEPTH_LIMIT", name)
            continue
        if len(visited) >= args.max_files:
            error("FILE_COUNT_LIMIT", name)
            continue
        visited.add(name)
        try:
            data = read_source(root, name, args.max_file_bytes, args.max_total_bytes - total)
            if total + len(data) > args.max_total_bytes:
                raise CheckError("TOTAL_BYTE_LIMIT")
            total += len(data)
            # UTF-8 BOM is accepted even with the legacy encoding explicitly selected.
            text = data.decode("utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else args.encoding,
                               errors="strict")
            if any(ord(char) < 32 and char not in "\t\r\n" for char in text) or "\x7f" in text:
                raise CheckError("UNSUPPORTED_CONTROL_CHARACTER")
        except UnicodeError:
            error("ENCODING_ERROR", name)
            continue
        except CheckError as exc:
            error(exc.code, name)
            continue
        report["files"].append({"file": name, "bytes": len(data)})
        graph[name] = []
        children = []
        current = False
        for number, original in enumerate(text.splitlines(), 1):
            try:
                line = strip_comment(original)
                if not line:
                    continue
                if line.startswith("#"):
                    match = INCLUDE.fullmatch(line)
                    if not match:
                        raise CheckError("UNSUPPORTED_DIRECTIVE")
                    target = relative(match[1], name.rpartition("/")[0])
                    if records + 1 > args.max_records:
                        raise CheckError("RECORD_COUNT_LIMIT")
                    records += 1
                    graph[name].append(target)
                    incoming[target] += 1
                    report["includes"].append({"file": name, "line": number, "target": target})
                    children.append((target, depth + 1))
                elif line.startswith("["):
                    match = HEADER.fullmatch(line)
                    if not match:
                        raise CheckError("UNSUPPORTED_SECTION_SYNTAX")
                    parent_count = match[2].count(",") + 1 if match[2] else 0
                    if records + 1 + parent_count > args.max_records:
                        raise CheckError("RECORD_COUNT_LIMIT")
                    records += 1 + parent_count
                    parents = [item.strip().lower() for item in (match[2] or "").split(",") if item.strip()]
                    report["definitions"].append({"file": name, "line": number,
                                                  "section": match[1].lower(), "parents": parents})
                    current = True
                else:
                    if line[0] in "!@><" or not current:
                        raise CheckError("UNSUPPORTED_CONTENT")
                    key = line.partition("=")[0].strip()
                    if not KEY.fullmatch(key):
                        raise CheckError("UNSUPPORTED_CONTENT")
            except CheckError as exc:
                error(exc.code, name, number)
                # A multiline/foreign construct can make subsequent apparent headers values.
                # Stop this file, retaining its earlier declarations as partial evidence.
                break
        pending.extend(reversed(children))

    include_cycles, include_truncated = cycles(graph, args.max_records)
    for cycle in include_cycles:
        findings.append({"code": "INCLUDE_CYCLE", "files": cycle})
        error("INCLUDE_GRAPH_INCOMPLETE")
    if include_truncated:
        error("CYCLE_REPORT_LIMIT")
    for name, count in sorted(incoming.items()):
        if count > 1:
            findings.append({"code": "REPEATED_INCLUDE", "file": name, "references": count})

    declarations: dict[str, list[dict]] = defaultdict(list)
    for definition in report["definitions"]:
        declarations[definition["section"]].append(definition)
    inheritance: dict[str, list[str]] = {}
    for name, definitions in sorted(declarations.items()):
        inheritance[name] = list(dict.fromkeys(parent for item in definitions for parent in item["parents"]))
        if len(definitions) > 1:
            findings.append({"code": "DUPLICATE_SECTION", "section": name,
                             "locations": [{"file": item["file"], "line": item["line"]} for item in definitions]})
        for definition in definitions:
            for parent in definition["parents"]:
                if parent not in declarations:
                    findings.append({"code": "MISSING_PARENT", "section": name, "parent": parent,
                                     "file": definition["file"], "line": definition["line"]})
    inheritance_cycles, inheritance_truncated = cycles(inheritance, args.max_records)
    for cycle in inheritance_cycles:
        findings.append({"code": "INHERITANCE_CYCLE", "sections": cycle})
    if inheritance_truncated:
        error("CYCLE_REPORT_LIMIT")
    if not declarations:
        error("NO_DEFINITIONS")
    return finish(report)


def finish(report: dict) -> tuple[dict, int]:
    report["summary"] = {"files_read": len(report["files"]),
                         "bytes_read": sum(item["bytes"] for item in report["files"]),
                         "definitions": len(report["definitions"]),
                         "unique_sections": len({item["section"] for item in report["definitions"]}),
                         "includes": len(report["includes"]),
                         "findings": len(report["findings"]), "errors": len(report["errors"])}
    code = 1 if not report["complete"] else 2 if report["findings"] else 0
    report["exit_code"] = code
    return report, code


def write_report(path_value: str, root_value: str, payload: str) -> None:
    path = absolute(path_value)
    root = absolute(root_value)
    if path == root or root in path.parents:
        raise CheckError("OUTPUT_INSIDE_INPUT_ROOT")
    ancestry(path.parent, directory=True)
    # Report destination must use an exact, unambiguous new portable filename.
    matches = case_matches(path.parent, path.name)
    if matches:
        raise CheckError("OUTPUT_EXISTS")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    except OSError:
        raise CheckError("OUTPUT_UNAVAILABLE") from None


def encode_report(report: dict, limit: int) -> tuple[str, int]:
    """Bound serialization before constructing a potentially expanded JSON string."""
    chunks: list[str] = []
    size = 1  # final newline
    for chunk in json.JSONEncoder(ensure_ascii=True, indent=2).iterencode(report):
        size += len(chunk)
        if size > limit:
            minimal = {"schema_version": 1, "tool": report["tool"], "version": VERSION,
                       "complete": False, "encoding": report["encoding"], "limits": report["limits"],
                       "entries": [], "files": [], "includes": [], "definitions": [], "findings": [],
                       "errors": [{"code": "REPORT_BYTE_LIMIT"}]}
            minimal, code = finish(minimal)
            return json.dumps(minimal, ensure_ascii=True, indent=2) + "\n", code
        chunks.append(chunk)
    return "".join(chunks) + "\n", report["exit_code"]


def main(argv: list[str] | None = None) -> int:
    parser = Parser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--root", required=True, help="local directory containing all selected inputs")
    parser.add_argument("--entry", required=True, action="append", help="root-relative .ltx/.ini entry (repeatable)")
    parser.add_argument("--encoding", choices=("utf-8", "cp1251"), default="utf-8")
    parser.add_argument("--max-file-bytes", type=positive, default=2 * 1024 * 1024)
    parser.add_argument("--max-total-bytes", type=positive, default=32 * 1024 * 1024)
    parser.add_argument("--max-files", type=positive, default=4096)
    parser.add_argument("--max-depth", type=positive, default=64)
    parser.add_argument("--max-records", type=positive, default=100000,
                        help="combined include/declaration/parent-reference budget")
    parser.add_argument("--max-report-bytes", type=positive, default=16 * 1024 * 1024,
                        help="JSON graph-report budget; overflow returns a small incomplete report")
    parser.add_argument("--output", help="new JSON file outside root; parent must already exist")
    args = parser.parse_args(argv)
    try:
        report, code = inspect(args)
        payload, code = encode_report(report, args.max_report_bytes)
        if args.output:
            write_report(args.output, args.root, payload)
        else:
            sys.stdout.write(payload)
        return code
    except (OSError, CheckError) as exc:
        reason = exc.code if isinstance(exc, CheckError) else "IO_ERROR"
        sys.stderr.write(f"ltx-definition-inspector: {reason}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
