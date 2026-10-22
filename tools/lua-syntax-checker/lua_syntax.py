#!/usr/bin/env python3
"""Compile loose Lua sources without executing their compiled closures.

MIT licensed; see the repository LICENSE. Python 3.12+ and Lupa 2.8.
Inspect stable, trusted local source trees. This is not a hostile-input sandbox.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

VERSION = "1.0.0"
LUPA_VERSION = "2.8"
DEFAULT_MAX_SCRIPT_BYTES = 2 * 1024 * 1024
MODLIST_MAX_BYTES = 2 * 1024 * 1024
RUNTIMES = ("luajit21", "lua51", "lua54")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DEVICE_NAME = re.compile(r"^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)", re.I)
_ERROR_LINE = re.compile(br"^syntax-check:([1-9][0-9]{0,9}):")

LIMITATIONS = [
    "Only physical loose .lua and .script files are compiled; archives, MO2's virtual filesystem, foreign entries, and engine transformations are not inspected.",
    "MO2 modlist order is highest priority first; overwrite is above enabled mods, and an optional loose base is below them. All roots must represent the same virtual directory level.",
    "Case matching uses Python Unicode casefold, not exact NTFS/Win32 collation. Root meta.ini and .mohidden files/directories are excluded.",
    "The selected Lupa runtime may differ from your game's Lua dialect, extensions, bytecode, or compiler build. A syntax error is relative to that selected runtime.",
    "Source is passed as bytes without transcoding or newline normalization. An initial UTF-8 BOM is recorded and removed only from parser input; binary chunks and NUL bytes are refused.",
    "Compilation creates a closure that is discarded without calling it. No scanned script, require, or game callback is executed. Only the tool's fixed compiler helper and runtime metadata expressions are evaluated.",
    "Syntax success does not verify globals, types, dependencies, callbacks, mod interactions, gameplay, or game compatibility.",
    "Lupa contains native parsers. Size limits do not make this a sandbox or guarantee bounded parser time/memory or protection against native crashes; use trusted local sources.",
    "Missing, unreadable, linked, ambiguous, binary, oversized, changed, or otherwise skipped input makes the report incomplete. Zero effective scripts also makes it incomplete.",
    "Effective files and modlist content are reread to detect changes, but directory membership changes and all races cannot be detected. This is not a filesystem snapshot; inspect a stable tree.",
    "Reports omit absolute input paths, source text, and raw parser errors. Relative filenames, mod names, hashes, and line numbers may still be sensitive; review before sharing.",
]


class InspectionError(Exception):
    """An intentionally sanitized input/runtime failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _safe_name(name: str) -> bool:
    return bool(name and name not in (".", "..")
                and not name.endswith((" ", "."))
                and not _INVALID_NAME.search(name)
                and not _DEVICE_NAME.match(name))


def _absolute(value: os.PathLike[str] | str) -> Path:
    try:
        raw = os.fspath(value)
        if not isinstance(raw, str) or not raw or "\x00" in raw:
            raise InspectionError("invalid_path")
        if raw.startswith(("\\\\", "//")):
            raise InspectionError("unsupported_network_path")
        # Drive-relative Windows names (C:folder) depend on process state.
        if re.match(r"^[A-Za-z]:[^\\/]", raw) or re.fullmatch(r"[A-Za-z]:", raw):
            raise InspectionError("invalid_path")
        path = Path(os.path.abspath(raw))
        if any(not _safe_name(part) for part in path.parts if part != path.anchor):
            raise InspectionError("invalid_path")
        return path
    except (TypeError, ValueError, OSError):
        raise InspectionError("invalid_path") from None


def _linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _check_ancestors(path: Path) -> os.stat_result:
    info = None
    for component in list(reversed(path.parents)) + [path]:
        try:
            info = component.lstat()
        except FileNotFoundError:
            raise InspectionError("missing_path") from None
        except OSError:
            raise InspectionError("unreadable_path") from None
        if _linked(info):
            raise InspectionError("linked_path")
        if component != path and not stat.S_ISDIR(info.st_mode):
            raise InspectionError("invalid_directory")
    assert info is not None
    return info


def _directory(path: Path) -> None:
    if not stat.S_ISDIR(_check_ancestors(path).st_mode):
        raise InspectionError("invalid_directory")


def _fingerprint(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _read_bounded(path: Path, limit: int) -> bytes:
    before = _check_ancestors(path)
    if not stat.S_ISREG(before.st_mode):
        raise InspectionError("nonregular_file")
    if before.st_size > limit:
        raise InspectionError("script_size_limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or _linked(opened):
                raise InspectionError("nonregular_file")
            if _fingerprint(opened) != _fingerprint(before):
                raise InspectionError("input_changed")
            data = stream.read(min(limit + 1, opened.st_size + 1))
            after = os.fstat(stream.fileno())
        if _fingerprint(opened) != _fingerprint(after):
            raise InspectionError("input_changed")
    except OSError:
        raise InspectionError("unreadable_file") from None
    except (MemoryError, OverflowError):
        raise InspectionError("read_resource_limit") from None
    if len(data) > limit:
        raise InspectionError("script_size_limit")
    return data


def _within(path: Path, root: Path) -> bool:
    candidate = str(path).casefold()
    parent = str(root).casefold().rstrip("/\\")
    return candidate == parent or candidate.startswith(parent + os.sep)


def _new_report(runtime: str, mode: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "tool": {"name": "lua-syntax-checker", "version": VERSION},
        "mode": mode,
        "runtime": {
            "requested": runtime, "module": None, "lupa_version": None,
            "lua_version": None, "implementation": None,
            "operation": "compile only; scanned closures are discarded without calling",
        },
        "summary": {
            "complete": True, "enabled_mods": 0, "scanned_providers": 0,
            "loose_scripts": 0, "effective_scripts": 0, "checked_scripts": 0,
            "passes": 0, "syntax_errors": 0, "skipped_scripts": 0,
            "shadowed_scripts": 0,
        },
        "providers_priority_highest_first": [], "scripts": [],
        "modlist": None, "warnings": [], "errors": [],
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


def _mod_names(data: bytes, report: dict[str, Any]) -> list[str]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        raise InspectionError("invalid_modlist_encoding") from None
    if "\x00" in text:
        raise InspectionError("invalid_modlist_encoding")
    names: list[str] = []
    seen: set[str] = set()
    for line, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#") or raw.startswith("-"):
            continue
        if not raw.startswith("+"):
            _issue(report, "unsupported_foreign_entry" if raw.startswith("*")
                   else "unsupported_modlist_entry", line=line)
            continue
        name = raw[1:]
        if name.casefold().endswith("_separator"):
            continue
        if not _safe_name(name):
            _issue(report, "invalid_mod_name", error=True, line=line)
            continue
        if name.casefold() in seen:
            _issue(report, "duplicate_mod_name", error=True, line=line)
            continue
        seen.add(name.casefold())
        names.append(name)
    return names


def _entries(path: Path) -> list[os.DirEntry[str]]:
    _directory(path)
    try:
        with os.scandir(path) as iterator:
            return sorted(iterator, key=lambda entry: (entry.name.casefold(), entry.name))
    except OSError:
        raise InspectionError("unreadable_directory") from None


def _inventory(root: Path, provider: str, report: dict[str, Any]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    pending = [(root, "")]
    while pending:
        folder, relative = pending.pop()
        try:
            entries = _entries(folder)
        except InspectionError as exc:
            _issue(report, exc.code, provider=provider, path=relative or ".")
            continue
        groups: dict[str, list[os.DirEntry[str]]] = defaultdict(list)
        for entry in entries:
            if entry.name.casefold().endswith(".mohidden"):
                continue
            if not relative and entry.name.casefold() == "meta.ini":
                continue
            if not _safe_name(entry.name):
                _issue(report, "invalid_entry_name", provider=provider, path=relative or ".")
                continue
            groups[entry.name.casefold()].append(entry)
        subdirectories = []
        for key in sorted(groups):
            group = groups[key]
            rel = f"{relative}/{key}" if relative else key
            if len(group) != 1:
                _issue(report, "ambiguous_case_path", provider=provider, path=rel)
                continue
            entry = group[0]
            candidate = folder / entry.name
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                _issue(report, "unreadable_file", provider=provider, path=rel)
                continue
            if _linked(info):
                _issue(report, "linked_path", provider=provider, path=rel)
            elif stat.S_ISDIR(info.st_mode):
                subdirectories.append((candidate, rel))
            elif stat.S_ISREG(info.st_mode):
                if candidate.suffix.casefold() in {".lua", ".script"}:
                    result[rel] = candidate
            else:
                _issue(report, "nonregular_file", provider=provider, path=rel)
        pending.extend(reversed(subdirectories))
    return result


def _runtime(runtime: str, report: dict[str, Any]) -> Any:
    try:
        package = importlib.import_module("lupa")
        version = getattr(package, "__version__", None)
        if version != LUPA_VERSION:
            raise InspectionError("unsupported_lupa_version")
        module = importlib.import_module("lupa." + runtime)
        lua = module.LuaRuntime(encoding=None, unpack_returned_tuples=True,
                               register_eval=False, register_builtins=False)
        # Only this fixed helper is evaluated. Its returned function compiles
        # input and discards the resulting closure, never invoking source.
        if runtime == "lua54":
            helper = b"function(source) local fn, err = load(source, '@syntax-check', 't', {}); return fn ~= nil, err end"
        else:
            helper = b"function(source) local fn, err = loadstring(source, '@syntax-check'); return fn ~= nil, err end"
        compiler = lua.eval(helper)
        lua_version = lua.eval(b"_VERSION")
        implementation = lua.eval(b"jit and jit.version or _VERSION")
        report["runtime"].update({
            "module": "lupa." + runtime, "lupa_version": version,
            "lua_version": lua_version.decode("ascii"),
            "implementation": implementation.decode("ascii"),
        })
        # Keeping the runtime alive explicitly also makes its ownership clear.
        return lua, compiler
    except InspectionError:
        raise
    except Exception:
        raise InspectionError("runtime_unavailable") from None


def _compile(effective: dict[str, tuple[str, str, Path]], report: dict[str, Any],
             runtime: str, limit: int) -> None:
    compiler = None
    runtime_error = None
    try:
        runtime_owner, compiler = _runtime(runtime, report)
    except InspectionError as exc:
        runtime_error = exc.code
        _issue(report, exc.code, error=True)
    for relative, (provider, kind, path) in sorted(effective.items()):
        item: dict[str, Any] = {
            "path": relative, "provider": provider, "kind": kind,
            "status": "SKIPPED", "bytes": None, "sha256": None,
            "utf8_bom": None, "parser_input_sha256": None,
        }
        report["scripts"].append(item)
        data = None
        try:
            data = _read_bounded(path, limit)
            item["bytes"] = len(data)
            item["sha256"] = hashlib.sha256(data).hexdigest()
            bom = data.startswith(b"\xef\xbb\xbf")
            item["utf8_bom"] = bom
            parser_input = data[3:] if bom else data
            item["parser_input_sha256"] = hashlib.sha256(parser_input).hexdigest()
            if parser_input.startswith((b"\x1bLua", b"\x1bLJ")):
                raise InspectionError("binary_chunk")
            if b"\x00" in parser_input:
                raise InspectionError("nul_byte")
            if compiler is None:
                raise InspectionError(runtime_error or "runtime_unavailable")
            try:
                passed, error = compiler(parser_input)
            except Exception:
                raise InspectionError("runtime_compile_failed") from None
            if not passed and error in {
                b"not enough memory", b"memory allocation error",
                b"memory allocation error: not enough memory",
            }:
                raise InspectionError("runtime_compile_failed")
            item["status"] = "PASS" if passed else "SYNTAX_ERROR"
            if not passed:
                item["code"] = "syntax_error"
                # Parser messages may echo private literals. Keep only a line
                # number matching our fixed chunk label, never raw messages.
                match = _ERROR_LINE.match(error) if isinstance(error, bytes) else None
                if match and int(match[1]) <= parser_input.count(b"\n") + 1:
                    item["line"] = int(match[1])
        except InspectionError as exc:
            item["code"] = exc.code
            _issue(report, exc.code, provider=provider, path=relative)
        finally:
            if data is not None:
                try:
                    if _read_bounded(path, limit) != data:
                        raise InspectionError("input_changed")
                except InspectionError as exc:
                    item["status"] = "SKIPPED"
                    item["code"] = exc.code
                    item.pop("line", None)
                    _issue(report, exc.code, provider=provider, path=relative)


def inspect_sources(*, source_dir: os.PathLike[str] | str | None = None,
                    mods_dir: os.PathLike[str] | str | None = None,
                    modlist: os.PathLike[str] | str | None = None,
                    base_dir: os.PathLike[str] | str | None = None,
                    overwrite_dir: os.PathLike[str] | str | None = None,
                    runtime: str = "luajit21",
                    max_script_bytes: int = DEFAULT_MAX_SCRIPT_BYTES) -> dict[str, Any]:
    """Return a privacy-conscious syntax report; never write to source trees.

    Sources must be stable, trusted local files. An incomplete report is never
    a successful syntax result. Relative names and hashes can be sensitive.
    """
    mode = "tree" if source_dir is not None else "mo2"
    report = _new_report(runtime if runtime in RUNTIMES else "unsupported", mode)
    if (runtime not in RUNTIMES or not isinstance(max_script_bytes, int)
            or isinstance(max_script_bytes, bool) or not 1 <= max_script_bytes < sys.maxsize):
        _issue(report, "invalid_options", error=True)
        return report
    if ((source_dir is None) == (mods_dir is None)
            or (source_dir is not None and any(value is not None for value in (modlist, base_dir, overwrite_dir)))
            or (mods_dir is not None and modlist is None)):
        _issue(report, "invalid_options", error=True)
        return report
    roots: list[tuple[str, str, Path]] = []
    profile = None
    profile_data = None
    try:
        if source_dir is not None:
            source = _absolute(source_dir)
            _directory(source)
            roots.append(("<source>", "source", source))
        else:
            mods = _absolute(mods_dir)
            _directory(mods)
            profile = _absolute(modlist)
            profile_data = _read_bounded(profile, MODLIST_MAX_BYTES)
            report["modlist"] = {"sha256": hashlib.sha256(profile_data).hexdigest(), "unchanged": None}
            names = _mod_names(profile_data, report)
            report["summary"]["enabled_mods"] = len(names)
            checked_roots = [mods]
            for value, name, kind in ((overwrite_dir, "<overwrite>", "overwrite"),
                                      (base_dir, "<base>", "base")):
                if value is not None:
                    root = _absolute(value)
                    _directory(root)
                    if any(_within(root, old) or _within(old, root) for old in checked_roots):
                        raise InspectionError("overlapping_source_roots")
                    checked_roots.append(root)
                    roots.append((name, kind, root))
            if any(_within(profile, root) for root in checked_roots):
                raise InspectionError("overlapping_source_roots")
            folders: dict[str, list[os.DirEntry[str]]] = defaultdict(list)
            for entry in _entries(mods):
                folders[entry.name.casefold()].append(entry)
            mod_roots = []
            for name in names:
                choices = folders.get(name.casefold(), [])
                if not choices:
                    _issue(report, "missing_mod", provider=name)
                    continue
                if len(choices) != 1:
                    _issue(report, "ambiguous_case_mod", provider=name)
                    continue
                root = mods / choices[0].name
                try:
                    _directory(root)
                except InspectionError as exc:
                    _issue(report, exc.code, provider=name)
                    continue
                mod_roots.append((name, "mod", root))
            roots = [root for root in roots if root[1] == "overwrite"] + mod_roots + [
                root for root in roots if root[1] == "base"]
    except InspectionError as exc:
        _issue(report, exc.code, error=True)
        return report
    effective: dict[str, tuple[str, str, Path]] = {}
    for priority, (provider, kind, root) in enumerate(roots):
        report["providers_priority_highest_first"].append({"name": provider, "kind": kind, "priority": priority})
        inventory = _inventory(root, provider, report)
        report["summary"]["scanned_providers"] += 1
        report["summary"]["loose_scripts"] += len(inventory)
        for relative, path in inventory.items():
            effective.setdefault(relative, (provider, kind, path))
    report["summary"]["effective_scripts"] = len(effective)
    report["summary"]["shadowed_scripts"] = report["summary"]["loose_scripts"] - len(effective)
    if not effective:
        _issue(report, "no_scripts", error=True)
    else:
        _compile(effective, report, runtime, max_script_bytes)
    if profile is not None and profile_data is not None:
        try:
            unchanged = _read_bounded(profile, MODLIST_MAX_BYTES) == profile_data
            report["modlist"]["unchanged"] = unchanged
            if not unchanged:
                _issue(report, "modlist_changed", error=True)
        except InspectionError:
            report["modlist"]["unchanged"] = False
            _issue(report, "modlist_changed", error=True)
    summary = report["summary"]
    summary["passes"] = sum(item["status"] == "PASS" for item in report["scripts"])
    summary["syntax_errors"] = sum(item["status"] == "SYNTAX_ERROR" for item in report["scripts"])
    summary["skipped_scripts"] = sum(item["status"] == "SKIPPED" for item in report["scripts"])
    summary["checked_scripts"] = summary["passes"] + summary["syntax_errors"]
    for kind in ("warnings", "errors"):
        report[kind].sort(key=lambda item: (item.get("provider", ""), item.get("path", ""), item.get("line", 0), item["code"]))
    return report


def exit_status(report: dict[str, Any]) -> int:
    """1: incomplete; 2: complete with syntax errors; 0: complete clean."""
    if not report["summary"]["complete"]:
        return 1
    return 2 if report["summary"]["syntax_errors"] else 0


def _write_report(destination: str, text: str, *, source_dir: str | None,
                  mods_dir: str | None, modlist: str | None,
                  base_dir: str | None, overwrite_dir: str | None) -> None:
    output = _absolute(destination)
    _directory(output.parent)
    for root in (source_dir, mods_dir, base_dir, overwrite_dir):
        if root is not None and _within(output, _absolute(root)):
            raise InspectionError("unsafe_output_destination")
    if modlist is not None and str(output).casefold() == str(_absolute(modlist)).casefold():
        raise InspectionError("unsafe_output_destination")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(output, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write((text + "\n").encode("utf-8"))
    except OSError:
        raise InspectionError("unsafe_output_destination") from None


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, "Error: invalid arguments; use --help for usage.\n")


def _positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a positive integer") from None
    if not 1 <= number < sys.maxsize:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source-dir", help="recursive loose source tree (read only)")
    selection.add_argument("--mods-dir", help="MO2 mods directory (read only)")
    parser.add_argument("--modlist", help="MO2 modlist.txt; first active entry has highest priority")
    parser.add_argument("--base-dir", help="optional MO2 loose base; lowest priority")
    parser.add_argument("--overwrite-dir", help="optional MO2 overwrite; highest priority")
    parser.add_argument("--runtime", choices=RUNTIMES, default="luajit21", help="parser dialect (default: luajit21)")
    parser.add_argument("--max-script-bytes", type=_positive, default=DEFAULT_MAX_SCRIPT_BYTES,
                        help="maximum bytes per effective script (default: 2097152)")
    parser.add_argument("--output", help="new JSON file outside all input sources; default: stdout")
    args = parser.parse_args(argv)
    report = inspect_sources(source_dir=args.source_dir, mods_dir=args.mods_dir, modlist=args.modlist,
                             base_dir=args.base_dir, overwrite_dir=args.overwrite_dir,
                             runtime=args.runtime, max_script_bytes=args.max_script_bytes)
    try:
        text = json.dumps(report, ensure_ascii=True, indent=2)
        if args.output:
            _write_report(args.output, text, source_dir=args.source_dir, mods_dir=args.mods_dir,
                          modlist=args.modlist, base_dir=args.base_dir, overwrite_dir=args.overwrite_dir)
        else:
            print(text)
    except (InspectionError, OSError, ValueError):
        print("Error: unable to write report; choose a new file outside inspected sources.", file=sys.stderr)
        return 1
    return exit_status(report)


if __name__ == "__main__":
    sys.exit(main())
