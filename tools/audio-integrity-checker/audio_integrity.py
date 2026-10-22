#!/usr/bin/env python3
"""Inspect loose audio metadata and stream-decode effective files without playback.

MIT licensed; see the repository LICENSE. Python 3.12+ and pinned SoundFile/NumPy.
Use stable, trusted local trees. Native decoding is not a hostile-input sandbox.
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
SOUNDFILE_VERSION = "0.13.1"
NUMPY_VERSION = "2.2.6"
DEFAULT_MAX_FILE_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_FRAMES = 20_000_000
DEFAULT_MAX_CHANNELS = 32
MAX_ALLOWED_CHANNELS = 256
BLOCK_SAMPLES = 262_144
MODLIST_MAX_BYTES = 2 * 1024 * 1024
EXTENSIONS = frozenset({".wav", ".ogg", ".flac", ".aiff", ".aif"})
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DEVICE_NAME = re.compile(r"^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)", re.I)

LIMITATIONS = [
    "Only physical loose .wav, .ogg, .flac, .aiff, and .aif files are candidates; successful decoding depends on the installed libsndfile build. Archives, MP3, game banks, MO2's virtual filesystem, and other extensions are not inspected.",
    "MO2 modlist order is highest priority first; overwrite is above enabled mods, and an optional loose base is below them. All roots must represent the same virtual directory level. Only winning files are decoded.",
    "Case matching uses Python Unicode casefold, not exact NTFS/Win32 collation. Root meta.ini and .mohidden files/directories are excluded.",
    "Audio is read as float32 in bounded blocks. File-byte, declared/actual-frame, and channel limits restrict this tool's reads but do not isolate native decoder memory, CPU, crashes, or codec vulnerabilities. Use trusted local audio.",
    "A successful decode does not prove every file byte is valid, that trailing data is clean, or that the asset works in a game, X-Ray, OpenAL, or another decoder. No sample rate or channel layout is classified as corruption by itself.",
    "Missing, unreadable, linked, ambiguous, oversized, changed, dependency-unavailable, or otherwise skipped input makes the report incomplete. Zero effective audio files also makes it incomplete.",
    "File identity/stat and modlist content are checked again to detect changes. All races and directory membership changes cannot be detected; this is not a filesystem snapshot.",
    "Reports omit absolute input paths, tags, audio samples, and raw decoder errors. Relative filenames, mod names, and optional hashes may still be sensitive; review before sharing.",
    "The tool never plays, fixes, transcodes, deletes, or uploads inspected audio. --output only creates a new report outside input trees.",
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


def _open_readonly(path: Path, limit: int) -> Any:
    before = _check_ancestors(path)
    if not stat.S_ISREG(before.st_mode):
        raise InspectionError("nonregular_file")
    if before.st_size > limit:
        raise InspectionError("file_size_limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        stream = os.fdopen(descriptor, "rb")
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or _linked(opened):
            stream.close()
            raise InspectionError("nonregular_file")
        if _fingerprint(opened) != _fingerprint(before):
            stream.close()
            raise InspectionError("input_changed")
        return stream
    except OSError:
        raise InspectionError("unreadable_file") from None


def _unchanged(path: Path, stream: Any, before: os.stat_result) -> None:
    try:
        opened_after = os.fstat(stream.fileno())
        path_after = _check_ancestors(path)
    except (OSError, ValueError):
        raise InspectionError("input_changed") from None
    if (_fingerprint(before) != _fingerprint(opened_after)
            or _fingerprint(before) != _fingerprint(path_after)):
        raise InspectionError("input_changed")


def _read_bounded(path: Path, limit: int) -> bytes:
    try:
        with _open_readonly(path, limit) as stream:
            before = os.fstat(stream.fileno())
            data = stream.read(limit + 1)
            _unchanged(path, stream, before)
        if len(data) > limit:
            raise InspectionError("file_size_limit")
        return data
    except OSError:
        raise InspectionError("unreadable_file") from None
    except (MemoryError, OverflowError):
        raise InspectionError("read_resource_limit") from None


def _within(path: Path, root: Path) -> bool:
    candidate = str(path).casefold()
    parent = str(root).casefold().rstrip("/\\")
    return candidate == parent or candidate.startswith(parent + os.sep)


def _new_report(mode: str, sha256: bool, limits: dict[str, int]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "tool": {"name": "audio-integrity-checker", "version": VERSION},
        "mode": mode,
        "runtime": {"soundfile_version": None, "numpy_version": None, "libsndfile_version": None},
        "options": {"sha256": sha256, **limits},
        "summary": {
            "complete": True, "enabled_mods": 0, "scanned_providers": 0,
            "loose_audio_files": 0, "effective_files": 0, "checked_files": 0,
            "passes": 0, "decode_errors": 0, "anomalies": 0,
            "skipped_files": 0, "shadowed_files": 0,
        },
        "providers_priority_highest_first": [], "files": [], "file_conflicts": [],
        "modlist": None, "warnings": [], "errors": [], "limitations": list(LIMITATIONS),
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
                if candidate.suffix.casefold() in EXTENSIONS:
                    result[rel] = candidate
            else:
                _issue(report, "nonregular_file", provider=provider, path=rel)
        pending.extend(reversed(subdirectories))
    return result


def _runtime(report: dict[str, Any]) -> tuple[Any, Any]:
    try:
        sf = importlib.import_module("soundfile")
        np = importlib.import_module("numpy")
        if getattr(sf, "__version__", None) != SOUNDFILE_VERSION:
            raise InspectionError("unsupported_soundfile_version")
        if getattr(np, "__version__", None) != NUMPY_VERSION:
            raise InspectionError("unsupported_numpy_version")
        report["runtime"].update(soundfile_version=sf.__version__,
                                 numpy_version=np.__version__,
                                 libsndfile_version=str(sf.__libsndfile_version__))
        return sf, np
    except InspectionError:
        raise
    except Exception:
        raise InspectionError("decoder_unavailable") from None


def _decode_file(path: Path, item: dict[str, Any], sf: Any, np: Any,
                 *, sha256: bool, max_file_bytes: int, max_frames: int,
                 max_channels: int) -> None:
    with _open_readonly(path, max_file_bytes) as source:
        before = os.fstat(source.fileno())
        item["bytes"] = before.st_size
        try:
            if sha256:
                digest = hashlib.sha256()
                total = 0
                while block := source.read(min(1024 * 1024, max_file_bytes - total + 1)):
                    total += len(block)
                    if total > max_file_bytes:
                        raise InspectionError("file_size_limit")
                    digest.update(block)
                if total != before.st_size:
                    raise InspectionError("input_changed")
                item["sha256"] = digest.hexdigest()
                source.seek(0)
            try:
                # A checked, read-only file object is passed through virtual IO;
                # native error strings and absolute paths are never reported.
                with sf.SoundFile(source, mode="r") as audio:
                    channels = int(audio.channels)
                    declared = int(audio.frames)
                    rate = int(audio.samplerate)
                    item.update(format=str(audio.format), subtype=str(audio.subtype),
                                sample_rate=rate, channels=channels, declared_frames=declared)
                    if channels < 1 or channels > max_channels:
                        raise InspectionError("channel_limit")
                    if declared < 0 or declared > max_frames:
                        raise InspectionError("frame_limit")
                    if rate < 1:
                        raise InspectionError("invalid_audio_metadata")
                    block_frames = max(1, BLOCK_SAMPLES // channels)
                    frames = 0
                    finite = True
                    while True:
                        # Read at most one frame beyond the cap to detect an
                        # inconsistent decoder without unbounded allocation.
                        request = min(block_frames, max_frames - frames + 1)
                        block = audio.read(request, dtype="float32", always_2d=True)
                        if len(block) == 0:
                            break
                        frames += len(block)
                        item["decoded_frames"] = frames
                        if frames > max_frames:
                            raise InspectionError("frame_limit")
                        finite = finite and bool(np.isfinite(block).all())
                    item["decoded_frames"] = frames
                    item["finite_samples"] = finite
                    issues = []
                    if frames == 0:
                        issues.append("empty_audio")
                    if frames != declared:
                        issues.append("frame_count_mismatch")
                    if not finite:
                        issues.append("nonfinite_samples")
                    item["issues"] = issues
                    item["status"] = "DECODE_ANOMALY" if issues else "DECODE_PASS"
            except InspectionError:
                raise
            except (MemoryError, OverflowError):
                raise InspectionError("decode_resource_limit") from None
            except (RuntimeError, ValueError, OSError):
                item["status"] = "DECODE_ERROR"
                item["code"] = "decode_failed"
            except Exception:
                raise InspectionError("decoder_operation_failed") from None
        finally:
            _unchanged(path, source, before)


def _decode(effective: dict[str, tuple[str, str, Path]], report: dict[str, Any],
            **options: Any) -> None:
    sf = np = None
    runtime_error = None
    try:
        sf, np = _runtime(report)
    except InspectionError as exc:
        runtime_error = exc.code
        _issue(report, exc.code, error=True)
    for relative, (provider, kind, path) in sorted(effective.items()):
        item: dict[str, Any] = {
            "path": relative, "provider": provider, "kind": kind,
            "status": "SKIPPED", "bytes": None, "sha256": None,
            "format": None, "subtype": None, "sample_rate": None,
            "channels": None, "declared_frames": None, "decoded_frames": None,
            "finite_samples": None, "issues": [],
        }
        report["files"].append(item)
        try:
            if sf is None:
                raise InspectionError(runtime_error or "decoder_unavailable")
            _decode_file(path, item, sf, np, **options)
        except InspectionError as exc:
            item["status"] = "SKIPPED"
            item["code"] = exc.code
            _issue(report, exc.code, provider=provider, path=relative)
        except (OSError, ValueError):
            item["status"] = "SKIPPED"
            item["code"] = "unreadable_file"
            _issue(report, "unreadable_file", provider=provider, path=relative)
        except (MemoryError, OverflowError):
            item["status"] = "SKIPPED"
            item["code"] = "read_resource_limit"
            _issue(report, "read_resource_limit", provider=provider, path=relative)


def inspect_audio(*, source_dir: os.PathLike[str] | str | None = None,
                  mods_dir: os.PathLike[str] | str | None = None,
                  modlist: os.PathLike[str] | str | None = None,
                  base_dir: os.PathLike[str] | str | None = None,
                  overwrite_dir: os.PathLike[str] | str | None = None,
                  sha256: bool = False,
                  max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
                  max_frames: int = DEFAULT_MAX_FRAMES,
                  max_channels: int = DEFAULT_MAX_CHANNELS) -> dict[str, Any]:
    """Return a read-only audio report for stable, trusted local source trees."""
    limits = {"max_file_bytes": max_file_bytes, "max_frames": max_frames,
              "max_channels": max_channels}
    valid_limits = all(isinstance(value, int) and not isinstance(value, bool)
                       and 1 <= value < sys.maxsize for value in limits.values())
    # Never echo invalid arbitrary API values into a shareable report.
    safe_limits = limits if valid_limits else {}
    report = _new_report("tree" if source_dir is not None else "mo2",
                         sha256 if isinstance(sha256, bool) else False, safe_limits)
    if (not valid_limits or max_channels > MAX_ALLOWED_CHANNELS or not isinstance(sha256, bool)
            or (source_dir is None) == (mods_dir is None)
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
    providers: dict[str, list[dict[str, str]]] = defaultdict(list)
    for priority, (provider, kind, root) in enumerate(roots):
        report["providers_priority_highest_first"].append({"name": provider, "kind": kind, "priority": priority})
        inventory = _inventory(root, provider, report)
        report["summary"]["scanned_providers"] += 1
        report["summary"]["loose_audio_files"] += len(inventory)
        for relative, path in inventory.items():
            effective.setdefault(relative, (provider, kind, path))
            providers[relative].append({"name": provider, "kind": kind})
    report["file_conflicts"] = [
        {"path": relative, "winner": choices[0], "providers_in_priority_order": choices}
        for relative, choices in sorted(providers.items()) if len(choices) > 1
    ]
    report["summary"]["effective_files"] = len(effective)
    report["summary"]["shadowed_files"] = report["summary"]["loose_audio_files"] - len(effective)
    if not effective:
        _issue(report, "no_audio_files", error=True)
    else:
        _decode(effective, report, sha256=sha256, **limits)
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
    for key, status in (("passes", "DECODE_PASS"), ("decode_errors", "DECODE_ERROR"),
                        ("anomalies", "DECODE_ANOMALY"), ("skipped_files", "SKIPPED")):
        summary[key] = sum(item["status"] == status for item in report["files"])
    summary["checked_files"] = summary["passes"] + summary["decode_errors"] + summary["anomalies"]
    for kind in ("warnings", "errors"):
        report[kind].sort(key=lambda item: (item.get("provider", ""), item.get("path", ""), item.get("line", 0), item["code"]))
    return report


def exit_status(report: dict[str, Any]) -> int:
    """1: incomplete; 2: complete with decode findings; 0: complete clean."""
    if not report["summary"]["complete"]:
        return 1
    return 2 if report["summary"]["decode_errors"] or report["summary"]["anomalies"] else 0


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
    selection.add_argument("--source-dir", help="recursive loose audio tree (read only)")
    selection.add_argument("--mods-dir", help="MO2 mods directory (read only)")
    parser.add_argument("--modlist", help="MO2 modlist.txt; first active entry has highest priority")
    parser.add_argument("--base-dir", help="optional MO2 loose base; lowest priority")
    parser.add_argument("--overwrite-dir", help="optional MO2 overwrite; highest priority")
    parser.add_argument("--sha256", action="store_true", help="also hash effective file bytes in streaming chunks")
    parser.add_argument("--max-file-bytes", type=_positive, default=DEFAULT_MAX_FILE_BYTES,
                        help="maximum bytes per effective audio file (default: 268435456)")
    parser.add_argument("--max-frames", type=_positive, default=DEFAULT_MAX_FRAMES,
                        help="maximum declared and decoded frames per file (default: 20000000)")
    parser.add_argument("--max-channels", type=_positive, default=DEFAULT_MAX_CHANNELS,
                        help="maximum channels per file, 1..256 (default: 32)")
    parser.add_argument("--output", help="new JSON file outside all input sources; default: stdout")
    args = parser.parse_args(argv)
    report = inspect_audio(source_dir=args.source_dir, mods_dir=args.mods_dir, modlist=args.modlist,
                           base_dir=args.base_dir, overwrite_dir=args.overwrite_dir,
                           sha256=args.sha256, max_file_bytes=args.max_file_bytes,
                           max_frames=args.max_frames, max_channels=args.max_channels)
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
