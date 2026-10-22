#!/usr/bin/env python3
"""Summarize selected X-Ray log markers without printing source log text. MIT."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

VERSION = "1.0.0"
MAX_RECORDED_LINES = 1000
DEFAULT_MAX_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_LINE_BYTES = 64 * 1024
DEFAULT_MAX_LINES = 500_000
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_BAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DEVICE = re.compile(r"^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)", re.I)

# These are category definitions, never substitutions into the source text.
_FATAL = re.compile(r"\bfatal\s+error\b", re.I)
_SCRIPT = re.compile(r"\[script\s+error\]|\bscript\s+runtime\s+error\b", re.I)
_WARNING = re.compile(r"\bwarning\b|^\s*!", re.I)
_AUDIO = re.compile(r"\bsound\b|\baudio\b|\bopenal\b|\bsampling\b|\bsample\s+rate\b|\bfrequency\b", re.I)
_TREASURE = re.compile(r"\btreasure\b", re.I)
_ITEM = re.compile(r"\bitems?\b", re.I)
_MISSING = re.compile(r"\bmissing\b|\bnot\s+found\b|\bdoes\s+not\s+exist\b|\bunknown\b", re.I)
_MARKERS = {
    "startup_marker": re.compile(r"\bstarting\s+engine\b|\binitializing\s+engine\b|\bengine\s+startup\b", re.I),
    "session_marker": re.compile(r"\bstarting\s+new\s+game\b|\bload\s+saved\s+game\b|\bgame\s+loaded\b", re.I),
    "transport_marker": re.compile(r"\bGameNetworkingSockets\b|\bxrRazom\b", re.I),
    "connection_marker": re.compile(r"\bconnected\s+to\s+server\b|\bclient\s+connected\b", re.I),
    "shutdown_marker": re.compile(r"\bengine\s+shutdown\b|\bdestroying\s+engine\b", re.I),
}
_CODES = ("fatal_error", "script_error", "audio_warning", "missing_treasure_item_warning",
          "other_warning", *_MARKERS)

LIMITATIONS = [
    "Only the selected local physical log is read. There is no log discovery, tailing, archive extraction, process inspection, network access, or game modification.",
    "Categories use documented English text patterns, not an X-Ray protocol or complete log grammar. Localized, differently worded, multiline, and unrecognized messages may be missed or misclassified.",
    "Markers are observations in text. They do not prove a root cause, crash, working transport, successful host/client connection, successful shutdown, or gameplay compatibility.",
    "The report contains only static category/error codes, counts, capped line numbers, configured limits, and the selected encoding. It contains no source excerpts, log filenames, input paths, timestamps, player names, or extracted identifiers.",
    "Counts and marker context can still be sensitive. Review reports before sharing. This tool omits source text; it is not a general log redactor and must not be used to publish raw logs safely.",
    "Byte, line-byte, and line-count limits make stopped scans incomplete. Strict decoding stops at the first invalid line; no later lines are classified.",
    "Filesystem identity/stat checks detect some changes. Use an inactive, stable local log; races, same-size edits with restored timestamps, and all filesystem changes cannot be detected. This is not a filesystem snapshot.",
    "A complete scan with no recognized findings does not prove a healthy game. Existing files are never overwritten; a failed new report write can leave a partial new output file.",
]


class LogError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _report(encoding: str = "utf-8", max_bytes: int = DEFAULT_MAX_BYTES,
            max_line_bytes: int = DEFAULT_MAX_LINE_BYTES, max_lines: int = DEFAULT_MAX_LINES) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "tool": {"name": "xray-log-summary", "version": VERSION},
        "options": {"encoding": encoding, "max_bytes": max_bytes,
                    "max_line_bytes": max_line_bytes, "max_lines": max_lines,
                    "max_recorded_lines_per_category": MAX_RECORDED_LINES},
        "summary": {"complete": True, "bytes_read": 0, "lines_read": 0,
                    "fatal_errors": 0, "script_errors": 0, "warnings": 0,
                    "has_findings": False},
        "categories": [{"code": code, "count": 0, "line_numbers": [],
                        "line_numbers_truncated": False} for code in _CODES],
        "markers": {code: False for code in _MARKERS},
        "errors": [],
        "limitations": list(LIMITATIONS),
    }


def _fail(report: dict[str, Any], code: str, line: int | None = None) -> None:
    issue: dict[str, Any] = {"code": code}
    if line is not None:
        issue["line"] = line
    report["errors"].append(issue)
    report["summary"]["complete"] = False


def _path(value: str) -> Path:
    if not value or "\0" in value or value.startswith(("\\\\", "//")):
        raise LogError("unsupported_path")
    if re.match(r"^[A-Za-z]:[^\\/]", value) or re.fullmatch(r"[A-Za-z]:", value):
        raise LogError("unsupported_path")
    try:
        path = Path(os.path.abspath(value))
        if str(path).startswith(("\\\\", "//")):
            raise LogError("unsupported_path")
        for part in path.parts:
            if part == path.anchor:
                continue
            if (_BAD_NAME.search(part) or _DEVICE.match(part)
                    or part.endswith((" ", "."))):
                raise LogError("unsupported_path")
        return path
    except (OSError, ValueError, TypeError):
        raise LogError("unsupported_path") from None


def _linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE)


def _physical(path: Path) -> os.stat_result:
    result = None
    for component in (*reversed(path.parents), path):
        try:
            result = component.lstat()
        except FileNotFoundError:
            raise LogError("missing_path") from None
        except OSError:
            raise LogError("unreadable_path") from None
        if _linked(result):
            raise LogError("linked_path")
        if component != path and not stat.S_ISDIR(result.st_mode):
            raise LogError("invalid_parent")
    assert result is not None
    return result


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    # Windows lstat/fstat expose different ctime semantics on some Python builds.
    # Device, inode, length and last-write time have consistent handle/path meaning.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _prepare_output(path: Path, source: Path) -> None:
    if str(path).casefold() == str(source).casefold():
        raise LogError("output_is_input")
    parent = _physical(path.parent)
    if not stat.S_ISDIR(parent.st_mode):
        raise LogError("invalid_output_parent")
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        raise LogError("unreadable_output") from None
    raise LogError("output_exists")


def _hit(categories: dict[str, dict[str, Any]], code: str, line_number: int) -> None:
    category = categories[code]
    category["count"] += 1
    if len(category["line_numbers"]) < MAX_RECORDED_LINES:
        category["line_numbers"].append(line_number)
    else:
        category["line_numbers_truncated"] = True


def _classify(report: dict[str, Any], categories: dict[str, dict[str, Any]],
              line: str, number: int) -> None:
    fatal = bool(_FATAL.search(line))
    script = bool(_SCRIPT.search(line))
    if fatal:
        _hit(categories, "fatal_error", number)
        report["summary"]["fatal_errors"] += 1
    if script:
        _hit(categories, "script_error", number)
        report["summary"]["script_errors"] += 1
    # A fatal/script line is not also counted as a warning.
    if not (fatal or script) and _WARNING.search(line):
        if _AUDIO.search(line):
            code = "audio_warning"
        elif _TREASURE.search(line) and _ITEM.search(line) and _MISSING.search(line):
            code = "missing_treasure_item_warning"
        else:
            code = "other_warning"
        _hit(categories, code, number)
        report["summary"]["warnings"] += 1
    for code, pattern in _MARKERS.items():
        if pattern.search(line):
            _hit(categories, code, number)
            report["markers"][code] = True


def _scan(report: dict[str, Any], source: Path) -> None:
    limits = report["options"]
    before = _physical(source)
    if not stat.S_ISREG(before.st_mode):
        raise LogError("nonregular_input")
    if before.st_size > limits["max_bytes"]:
        raise LogError("byte_limit")
    descriptor = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(source, flags)
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or _linked(opened):
                raise LogError("nonregular_input")
            if _identity(before) != _identity(opened):
                raise LogError("input_changed")
            categories = {row["code"]: row for row in report["categories"]}
            try:
                while True:
                    remaining = limits["max_bytes"] - report["summary"]["bytes_read"]
                    raw = stream.readline(min(limits["max_line_bytes"] + 1, remaining + 1))
                    if not raw:
                        break
                    report["summary"]["bytes_read"] += len(raw)
                    number = report["summary"]["lines_read"] + 1
                    if report["summary"]["bytes_read"] > limits["max_bytes"]:
                        _fail(report, "byte_limit", number)
                        break
                    if len(raw) > limits["max_line_bytes"]:
                        _fail(report, "line_byte_limit", number)
                        break
                    if number > limits["max_lines"]:
                        _fail(report, "line_count_limit", number)
                        break
                    try:
                        text = raw.decode(limits["encoding"], errors="strict")
                    except UnicodeError:
                        _fail(report, "decoding_error", number)
                        break
                    if "\0" in text:
                        _fail(report, "binary_log", number)
                        break
                    if number == 1 and text.startswith("\ufeff"):
                        text = text[1:]
                    report["summary"]["lines_read"] = number
                    _classify(report, categories, text, number)
            finally:
                try:
                    final = _physical(source)
                    if (_identity(before) != _identity(os.fstat(stream.fileno()))
                            or _identity(before) != _identity(final)):
                        _fail(report, "input_changed")
                except (LogError, OSError):
                    _fail(report, "input_changed")
    except OSError:
        raise LogError("unreadable_input") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if before.st_size == 0:
        _fail(report, "empty_log")


def summarize(log: str, *, encoding: str = "utf-8", max_bytes: int = DEFAULT_MAX_BYTES,
              max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
              max_lines: int = DEFAULT_MAX_LINES, output: str | None = None) -> dict[str, Any]:
    """Return a schema-v1 report; only an optional new output file is created."""
    report = _report()
    try:
        if encoding not in {"utf-8", "cp1251"}:
            raise LogError("invalid_encoding")
        if any(type(value) is not int or not 1 <= value < sys.maxsize
               for value in (max_bytes, max_line_bytes, max_lines)):
            raise LogError("invalid_limits")
        report["options"].update({"encoding": encoding, "max_bytes": max_bytes,
                                  "max_line_bytes": max_line_bytes, "max_lines": max_lines})
        source = _path(log)
        destination = _path(output) if output is not None else None
        if destination is not None:
            _prepare_output(destination, source)
        _scan(report, source)
    except LogError as exc:
        _fail(report, exc.code)
    except (MemoryError, OverflowError):
        _fail(report, "resource_limit")
    except (OSError, ValueError, TypeError):
        _fail(report, "input_error")
    report["summary"]["has_findings"] = any(
        report["summary"][key] for key in ("fatal_errors", "script_errors", "warnings"))
    # Output is attempted only after input validation/scanning. Incomplete reports
    # from a valid scan are useful, but a preflight error must not create output.
    if output is not None and "source" in locals() and "destination" in locals() and destination is not None:
        if not any(row["code"] in {"output_is_input", "output_exists", "unreadable_output",
                                   "invalid_output_parent", "unsupported_path", "missing_path",
                                   "invalid_parent", "linked_path", "nonregular_input", "unreadable_path"}
                   for row in report["errors"]):
            try:
                _prepare_output(destination, source)
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(destination, flags, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
            except (LogError, OSError, ValueError):
                _fail(report, "output_write_error")
    return report


def exit_code(report: dict[str, Any]) -> int:
    if not report["summary"]["complete"]:
        return 1
    return 2 if report["summary"]["has_findings"] else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        report = _report()
        _fail(report, "invalid_arguments")
        print(json.dumps(report, indent=2))
        raise SystemExit(1)


def _positive(value: str) -> int:
    try:
        number = int(value)
        if not 1 <= number < sys.maxsize:
            raise ValueError
        return number
    except (ValueError, OverflowError):
        raise argparse.ArgumentTypeError("expected a positive bounded integer") from None


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--log", required=True, action="append", help="One stable local physical log file; supply exactly once")
    parser.add_argument("--encoding", choices=("utf-8", "cp1251"), default="utf-8")
    parser.add_argument("--max-bytes", type=_positive, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--max-line-bytes", type=_positive, default=DEFAULT_MAX_LINE_BYTES)
    parser.add_argument("--max-lines", type=_positive, default=DEFAULT_MAX_LINES)
    parser.add_argument("--output", help="Create a new JSON report; existing files are refused")
    args = parser.parse_args(argv)
    if len(args.log) != 1:
        parser.error("supply exactly one log")
    if sys.version_info < (3, 12):
        report = _report()
        _fail(report, "unsupported_python")
    else:
        report = summarize(args.log[0], encoding=args.encoding, max_bytes=args.max_bytes,
                           max_line_bytes=args.max_line_bytes, max_lines=args.max_lines,
                           output=args.output)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
