#!/usr/bin/env python3
"""Read-only loose-file inspection of a Mod Organizer 2 profile.

MIT licensed; see the repository LICENSE. Python 3.12+, standard library only.
This inventories physical files and applies heuristic text checks, not the VFS.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

VERSION = "1.0.0"
DEFAULT_MAX_TEXT_BYTES = 2 * 1024 * 1024
MODLIST_MAX_BYTES = 2 * 1024 * 1024
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DEVICE_NAME = re.compile(r"^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)", re.I)
_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_QUALIFIED = rf"{_IDENTIFIER}(?:[.:]{_IDENTIFIER})+"
_FUNCTION = re.compile(rf"\bfunction\s+({_QUALIFIED})\s*\(")
_LONG_BRACKET = re.compile(r"\[(=*)\[")
_SYMBOL = re.compile(rf"{_IDENTIFIER}(?:[.:]{_IDENTIFIER})*\Z")
_SECTION = re.compile(r"^[!+\-]?\[([^\]\r\n]+)\]")
_DECLARATION_NAME = re.compile(r"[\w .!<>+@#$%?&(){}~\-]{1,256}\Z")

LIMITATIONS = [
    "Loose physical files only; archives, base-game files, foreign entries, and the MO2 virtual filesystem are not inspected.",
    "MO2 modlist order is highest priority first; an explicitly supplied overwrite folder has highest priority.",
    "Case matching uses Python Unicode casefold, not exact NTFS/Win32 collation; unusual Unicode names may need MO2 confirmation.",
    "Root meta.ini and paths ending in .mohidden are excluded as MO2 metadata or hidden content.",
    "Text checks inspect only effective .lua, .script, and .ltx files; UTF-8 (optional BOM) and a bounded size are required.",
    "Lua declaration checks are heuristic, case-sensitive, and limited to repeated qualified function declarations across different effective files; they are not syntax validation.",
    "LTX checks find repeated exact section/key names within one effective file; inheritance, includes, DLTX merging, and cross-file targets are not evaluated.",
    "LTX section/key labels containing path punctuation, control characters, or more than 256 characters are unsupported and make the report partial.",
    "Unlocalizer checks compare bare identifier declarations under sections in effective .ltx files within an unlocalizers directory.",
    "A file overlap or repeated declaration does not establish a bug, compatibility, or actual game load order.",
    "Missing, unreadable, linked, ambiguous, or unsupported input makes this a partial report; absence of findings is not proof of compatibility.",
    "Paths are checked without following links, but concurrent filesystem changes are not supported; inspect a stable profile.",
    "Reports omit absolute paths, source text, and configuration values; mod names, relative filenames, and declared names can still be sensitive.",
]


class InspectionError(Exception):
    """A sanitized filesystem or input failure, never an operating-system message."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _absolute(path: os.PathLike[str] | str) -> Path:
    try:
        raw = os.fspath(path)
        if not isinstance(raw, str) or not raw or "\x00" in raw:
            raise InspectionError("invalid_path")
        # UNC and device namespace paths are outside this local-file tool's scope.
        if raw.startswith(("\\\\", "//")):
            raise InspectionError("unsupported_network_path")
        return Path(os.path.abspath(raw))
    except (TypeError, ValueError, OSError):
        raise InspectionError("invalid_path") from None


def _linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _check_ancestors(path: Path, *, include_leaf: bool = True) -> os.stat_result | None:
    """Reject symlinks and Windows reparse points in every existing component."""
    chain = list(reversed(path.parents)) + ([path] if include_leaf else [])
    last = None
    for component in chain:
        try:
            last = component.lstat()
        except FileNotFoundError:
            raise InspectionError("missing_path") from None
        except OSError:
            raise InspectionError("unreadable_path") from None
        if _linked(last):
            raise InspectionError("linked_path")
        if component != path or not include_leaf:
            if not stat.S_ISDIR(last.st_mode):
                raise InspectionError("invalid_directory")
    return last


def _validate_directory(path: Path) -> None:
    info = _check_ancestors(path)
    if info is None or not stat.S_ISDIR(info.st_mode):
        raise InspectionError("invalid_directory")


def _read_bounded(path: Path, limit: int) -> bytes:
    info = _check_ancestors(path)
    if info is None or not stat.S_ISREG(info.st_mode):
        raise InspectionError("nonregular_file")
    if info.st_size > limit:
        raise InspectionError("text_size_limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or _linked(opened):
                raise InspectionError("nonregular_file")
            data = stream.read(limit + 1)
    except OSError:
        raise InspectionError("unreadable_file") from None
    if len(data) > limit:
        raise InspectionError("text_size_limit")
    return data


def _text(path: Path, limit: int) -> str:
    try:
        result = _read_bounded(path, limit).decode("utf-8-sig")
    except UnicodeError:
        raise InspectionError("unsupported_text_encoding") from None
    if "\x00" in result:
        raise InspectionError("binary_text")
    return result


def _safe_mod_name(name: str) -> bool:
    return bool(
        name
        and name not in (".", "..")
        and not name.endswith((" ", "."))
        and not _INVALID_NAME.search(name)
        and not _DEVICE_NAME.match(name)
    )


def _new_report() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "tool": {"name": "mo2-conflict-inspector", "version": VERSION},
        "summary": {
            "complete": True,
            "enabled_mods": 0,
            "scanned_providers": 0,
            "loose_files": 0,
            "effective_files": 0,
            "file_conflicts": 0,
            "lua_function_repeats": 0,
            "ltx_duplicate_keys": 0,
            "unlocalizer_duplicates": 0,
            "findings": 0,
        },
        "providers_priority_highest_first": [],
        "file_conflicts": [],
        "analysis": {
            "lua_function_repeats": [],
            "ltx_duplicate_keys": [],
            "unlocalizer_duplicates": [],
        },
        "warnings": [],
        "errors": [],
        "limitations": list(LIMITATIONS),
    }


def _issue(report: dict[str, Any], code: str, *, error: bool = False,
           provider: str | None = None, path: str | None = None,
           line: int | None = None) -> None:
    item: dict[str, Any] = {"code": code}
    if provider is not None:
        item["provider"] = provider
    if path is not None:
        item["path"] = path
    if line is not None:
        item["line"] = line
    report["errors" if error else "warnings"].append(item)
    report["summary"]["complete"] = False


def _mod_names(text: str, report: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#") or raw.startswith("-"):
            continue
        if not raw.startswith("+"):
            _issue(report, "unsupported_foreign_entry" if raw.startswith("*")
                   else "unsupported_modlist_entry", line=number)
            continue
        name = raw[1:]
        if name.casefold().endswith("_separator"):
            continue
        if not _safe_mod_name(name):
            # Do not echo malformed names: they could contain an absolute path.
            _issue(report, "invalid_mod_name", error=True, line=number)
            continue
        key = name.casefold()
        if key in seen:
            _issue(report, "duplicate_mod_name", error=True, line=number)
            continue
        seen.add(key)
        names.append(name)
    return names


def _directory_entries(path: Path) -> list[os.DirEntry[str]]:
    _validate_directory(path)
    try:
        with os.scandir(path) as iterator:
            return sorted(iterator, key=lambda e: (e.name.casefold(), e.name))
    except OSError:
        raise InspectionError("unreadable_directory") from None


def _inventory(root: Path, name: str, report: dict[str, Any]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    pending: list[tuple[Path, str]] = [(root, "")]
    while pending:
        folder, relative = pending.pop()
        try:
            entries = _directory_entries(folder)
        except InspectionError as exc:
            _issue(report, exc.code, provider=name, path=relative or ".")
            continue
        groups: dict[str, list[os.DirEntry[str]]] = defaultdict(list)
        for entry in entries:
            if entry.name.casefold().endswith(".mohidden"):
                continue
            if not relative and entry.name.casefold() == "meta.ini":
                continue
            groups[entry.name.casefold()].append(entry)
        subdirectories = []
        for key in sorted(groups):
            group = groups[key]
            rel = f"{relative}/{key}" if relative else key
            if len(group) != 1:
                _issue(report, "ambiguous_case_path", provider=name, path=rel)
                continue
            entry = group[0]
            candidate = folder / entry.name
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                _issue(report, "unreadable_file", provider=name, path=rel)
                continue
            if _linked(info):
                _issue(report, "linked_path", provider=name, path=rel)
            elif stat.S_ISDIR(info.st_mode):
                subdirectories.append((candidate, rel))
            elif stat.S_ISREG(info.st_mode):
                files[rel] = candidate
            else:
                _issue(report, "nonregular_file", provider=name, path=rel)
        pending.extend(reversed(subdirectories))
    return files


def _blank_preserving_lines(text: str) -> str:
    return "".join("\n" if c == "\n" else " " for c in text)


def _lua_code(text: str) -> str:
    """Mask Lua comments/strings, including [=[long blocks]=], keeping lines."""
    result: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        start = index
        if text.startswith("--", index):
            index += 2
            bracket = _LONG_BRACKET.match(text, index)
            if bracket:
                marker = "]" + bracket[1] + "]"
                end = text.find(marker, index + len(bracket[0]))
                index = length if end < 0 else end + len(marker)
            else:
                end = text.find("\n", index)
                index = length if end < 0 else end
            result.append(_blank_preserving_lines(text[start:index]))
        elif text[index] in "\"'":
            quote = text[index]
            index += 1
            while index < length:
                if text[index] == "\\":
                    index = min(index + 2, length)
                elif text[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
            result.append(_blank_preserving_lines(text[start:index]))
        else:
            bracket = _LONG_BRACKET.match(text, index) if text[index] == "[" else None
            if bracket:
                marker = "]" + bracket[1] + "]"
                end = text.find(marker, index + len(bracket[0]))
                index = length if end < 0 else end + len(marker)
                result.append(_blank_preserving_lines(text[start:index]))
            else:
                result.append(text[index])
                index += 1
    return "".join(result)


def _ltx_line(text: str) -> str:
    """Strip semicolon comments outside quoted values."""
    quote = None
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
        elif char == "\\" and quote:
            escaped = True
        elif char in "\"'":
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
        elif char == ";" and quote is None:
            return text[:index].strip()
    return text.strip()


def _ref(provider: str, path: str, line: int) -> dict[str, Any]:
    return {"provider": provider, "path": path, "line": line}


def _analyze(effective: dict[str, tuple[str, Path]], report: dict[str, Any], limit: int) -> None:
    lua: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unlocalizers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relative, (provider, path) in sorted(effective.items()):
        suffix = path.suffix.casefold()
        if suffix not in {".lua", ".script", ".ltx"}:
            continue
        try:
            source = _text(path, limit)
        except InspectionError as exc:
            _issue(report, exc.code, provider=provider, path=relative)
            continue
        if suffix in {".lua", ".script"}:
            code = _lua_code(source)
            previous_start = 0
            line = 1
            for match in _FUNCTION.finditer(code):
                line += code.count("\n", previous_start, match.start())
                lua[match[1]].append(_ref(provider, relative, line))
                previous_start = match.start()
            continue
        section: str | None = None
        keys: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        is_unlocalizer = "unlocalizers" in relative.split("/")[:-1]
        for number, raw in enumerate(source.splitlines(), 1):
            line = _ltx_line(raw)
            if not line or line.startswith("#"):
                continue
            match = _SECTION.match(line)
            if match:
                section = match[1].strip()
                if not _DECLARATION_NAME.fullmatch(section):
                    _issue(report, "unsupported_ltx_name", provider=provider, path=relative, line=number)
                    section = None
            elif section and "=" in line:
                key = line.split("=", 1)[0].strip()
                if key and _DECLARATION_NAME.fullmatch(key):
                    keys[(section, key)].append(_ref(provider, relative, number))
                elif key:
                    _issue(report, "unsupported_ltx_name", provider=provider, path=relative, line=number)
            elif section and is_unlocalizer and _SYMBOL.fullmatch(line):
                unlocalizers[f"{section}.{line}"].append(_ref(provider, relative, number))
        for (section_name, key), declarations in sorted(keys.items()):
            if len(declarations) > 1:
                report["analysis"]["ltx_duplicate_keys"].append({
                    "section": section_name, "key": key, "declarations": declarations,
                })
    for symbol, declarations in sorted(lua.items()):
        if len({ref["path"] for ref in declarations}) > 1:
            report["analysis"]["lua_function_repeats"].append({
                "symbol": symbol, "declarations": declarations,
            })
    for symbol, declarations in sorted(unlocalizers.items()):
        if len(declarations) > 1:
            report["analysis"]["unlocalizer_duplicates"].append({
                "symbol": symbol, "declarations": declarations,
            })


def inspect_profile(mods_dir: os.PathLike[str] | str, modlist: os.PathLike[str] | str,
                    overwrite_dir: os.PathLike[str] | str | None = None,
                    max_text_bytes: int = DEFAULT_MAX_TEXT_BYTES) -> dict[str, Any]:
    """Inspect a stable profile. Invalid or skipped input returns complete=false.

    Input paths are never included in the report. This function writes no files.
    """
    report = _new_report()
    if not isinstance(max_text_bytes, int) or isinstance(max_text_bytes, bool) or max_text_bytes < 1:
        _issue(report, "invalid_text_limit", error=True)
        return report
    try:
        mods = _absolute(mods_dir)
        _validate_directory(mods)
    except InspectionError as exc:
        _issue(report, exc.code if exc.code == "linked_path" else "invalid_mods_dir", error=True)
        return report
    try:
        profile = _absolute(modlist)
        names = _mod_names(_text(profile, MODLIST_MAX_BYTES), report)
    except InspectionError as exc:
        _issue(report, exc.code if exc.code == "linked_path" else "invalid_modlist", error=True)
        return report
    report["summary"]["enabled_mods"] = len(names)
    roots: list[tuple[str, str, Path]] = []
    if overwrite_dir is not None:
        try:
            overwrite = _absolute(overwrite_dir)
            _validate_directory(overwrite)
            if _within(overwrite, mods) or _within(mods, overwrite):
                _issue(report, "overlapping_source_roots", error=True)
                return report
            roots.append(("<overwrite>", "overwrite", overwrite))
        except InspectionError as exc:
            _issue(report, exc.code if exc.code == "linked_path" else "invalid_overwrite_dir", error=True)
    try:
        entries = _directory_entries(mods)
        folders: dict[str, list[os.DirEntry[str]]] = defaultdict(list)
        for entry in entries:
            folders[entry.name.casefold()].append(entry)
    except InspectionError as exc:
        _issue(report, exc.code, error=True)
        return report
    for name in names:
        choices = folders.get(name.casefold(), [])
        if len(choices) > 1:
            _issue(report, "ambiguous_case_mod", provider=name)
            continue
        if not choices:
            _issue(report, "missing_mod", provider=name)
            continue
        root = mods / choices[0].name
        try:
            _validate_directory(root)
        except InspectionError as exc:
            _issue(report, exc.code, provider=name)
            continue
        roots.append((name, "mod", root))
    all_files: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    for priority, (name, kind, root) in enumerate(roots):
        report["providers_priority_highest_first"].append({
            "name": name, "kind": kind, "priority": priority,
        })
        inventory = _inventory(root, name, report)
        report["summary"]["scanned_providers"] += 1
        report["summary"]["loose_files"] += len(inventory)
        for relative, path in inventory.items():
            all_files[relative].append((name, path))
    effective = {}
    for relative, providers in sorted(all_files.items()):
        effective[relative] = providers[0]
        if len(providers) > 1:
            report["file_conflicts"].append({
                "path": relative,
                "providers_highest_first": [name for name, _ in providers],
                "winner": providers[0][0],
            })
    _analyze(effective, report, max_text_bytes)
    summary = report["summary"]
    summary["effective_files"] = len(effective)
    summary["file_conflicts"] = len(report["file_conflicts"])
    for key, findings in report["analysis"].items():
        summary[key] = len(findings)
    summary["findings"] = summary["file_conflicts"] + sum(len(v) for v in report["analysis"].values())
    report["warnings"].sort(key=lambda x: (x.get("provider", ""), x.get("path", ""), x.get("line", 0), x["code"]))
    report["errors"].sort(key=lambda x: (x.get("provider", ""), x.get("path", ""), x.get("line", 0), x["code"]))
    return report


def _within(path: Path, root: Path) -> bool:
    # Case-insensitive comparison deliberately follows Windows path semantics.
    candidate = os.path.normcase(str(path)).casefold()
    parent = os.path.normcase(str(root)).casefold().rstrip("/\\")
    return candidate == parent or candidate.startswith(parent + os.sep)


def _write_report(destination: str, report_text: str, mods_dir: str,
                  modlist: str, overwrite_dir: str | None) -> None:
    output = _absolute(destination)
    if not _safe_mod_name(output.name):
        raise InspectionError("unsafe_output_destination")
    _validate_directory(output.parent)
    for value in (mods_dir, overwrite_dir):
        if value is not None and _within(output, _absolute(value)):
            raise InspectionError("unsafe_output_destination")
    if str(output).casefold() == str(_absolute(modlist)).casefold():
        raise InspectionError("unsafe_output_destination")
    # O_EXCL prohibits replacement, including a pre-existing hardlink or symlink.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(output, flags, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write((report_text + "\n").encode("utf-8"))
    except OSError:
        raise InspectionError("unsafe_output_destination") from None


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse otherwise repeats user input, potentially exposing local paths.
        self.print_usage(sys.stderr)
        self.exit(1, "Error: invalid arguments; use --help for usage.\n")


def _positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a positive integer") from None
    if number < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--mods-dir", required=True, help="MO2 mods directory (read only)")
    parser.add_argument("--modlist", required=True, help="MO2 profile modlist.txt (highest priority first)")
    parser.add_argument("--overwrite-dir", help="optional overwrite directory; highest priority")
    parser.add_argument("--output", help="new JSON file outside mods/overwrite; default is stdout")
    parser.add_argument("--max-text-bytes", type=_positive, default=DEFAULT_MAX_TEXT_BYTES,
                        help="maximum bytes per effective text file (default: 2097152)")
    parser.add_argument("--fail-on-conflicts", action="store_true", help="exit 2 if a complete report has any findings")
    args = parser.parse_args(argv)
    try:
        report = inspect_profile(args.mods_dir, args.modlist, args.overwrite_dir, args.max_text_bytes)
        serialized = json.dumps(report, ensure_ascii=True, indent=2)
        if args.output:
            _write_report(args.output, serialized, args.mods_dir, args.modlist, args.overwrite_dir)
        else:
            print(serialized)
    except (InspectionError, OSError, ValueError):
        print("Error: unable to write report; choose a new file outside inspected sources.", file=sys.stderr)
        return 1
    if not report["summary"]["complete"]:
        return 1
    return 2 if args.fail_on_conflicts and report["summary"]["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
