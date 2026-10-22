#!/usr/bin/env python3
"""Create new hash-verified local snapshots or verify an existing snapshot.

Original MIT source; see ../../LICENSE. Python 3.12+, standard library only.
No restore, deletion, game detection, background service or upload feature.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

VERSION = '1.0.0'
CHUNK = 1024 * 1024
MAX_MANIFEST = 16 * CHUNK
DEFAULT_FILE = 1024 * CHUNK
DEFAULT_TOTAL = 8 * 1024 * CHUNK
DEFAULT_COUNT = 100000
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)
LABEL = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


class Failure(Exception):
    def __init__(self, code, path=None):
        self.code, self.path = code, path
        super().__init__(code)


def safe_name(name):
    return bool(name and name not in ('.', '..') and not name.endswith((' ', '.'))
                and not INVALID.search(name) and not DEVICE.match(name))


def absolute(value):
    raw = os.fspath(value)
    if (not isinstance(raw, str) or not raw or '\x00' in raw
            or raw.startswith(('\\\\', '//')) or re.match(r'^[A-Za-z]:(?:$|[^\\/])', raw)):
        raise Failure('invalid_local_path')
    path = Path(os.path.abspath(raw))
    if str(path).startswith(('\\\\', '//')):
        raise Failure('invalid_local_path')
    if any(not safe_name(part) for part in path.parts if part != path.anchor):
        raise Failure('unsafe_path_name')
    return path


def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def checked(path):
    try:
        for item in [*reversed(path.parents), path]:
            info = item.lstat()
            if linked(info):
                raise Failure('linked_path')
            if item != path and not stat.S_ISDIR(info.st_mode):
                raise Failure('invalid_parent')
        return info
    except OSError:
        raise Failure('unreadable_or_missing_path') from None


def directory(path):
    if not stat.S_ISDIR(checked(path).st_mode):
        raise Failure('not_a_directory')


def within(path, root):
    a, b = str(path).casefold(), str(root).casefold().rstrip('/\\')
    return a == b or a.startswith(b + os.sep)


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def readonly(path, limit):
    before = checked(path)
    if not stat.S_ISREG(before.st_mode):
        raise Failure('not_a_regular_file')
    if before.st_size > limit:
        raise Failure('file_byte_limit')
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
        stream = os.fdopen(fd, 'rb')
        if identity(os.fstat(stream.fileno())) != identity(before):
            stream.close()
            raise Failure('input_changed')
        return stream
    except OSError:
        raise Failure('unreadable_file') from None


def unchanged(path, stream, before):
    if (identity(os.fstat(stream.fileno())) != identity(before)
            or identity(checked(path)) != identity(before)):
        raise Failure('input_changed')


def digest(path, limit):
    with readonly(path, limit) as stream:
        before = os.fstat(stream.fileno())
        sha, size = hashlib.sha256(), 0
        while block := stream.read(min(CHUNK, limit - size + 1)):
            size += len(block)
            if size > limit:
                raise Failure('file_byte_limit')
            sha.update(block)
        unchanged(path, stream, before)
        if size != before.st_size:
            raise Failure('input_changed')
    return size, sha.hexdigest()


def new_file(path, data):
    directory(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        with os.fdopen(os.open(path, flags, 0o600), 'wb') as stream:
            stream.write(data)
    except OSError:
        raise Failure('new_file_creation_failed') from None


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode('utf-8')


def fresh(path):
    directory(path.parent)
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        raise Failure('unsafe_destination') from None
    raise Failure('destination_exists')


def inventory(root, count_limit):
    """Return regular files only; reject every unsupported entry, not silently skip."""
    info = checked(root)
    if stat.S_ISREG(info.st_mode):
        return {root.name: (root, identity(info))}, 'file'
    directory(root)
    records, pending = {}, [(root, '')]
    visited = 0
    while pending:
        folder, relative = pending.pop()
        directory(folder)
        try:
            with os.scandir(folder) as items:
                entries = []
                for item in items:
                    entries.append(item)
                    if visited + len(entries) > count_limit:
                        raise Failure('entry_count_limit')
                entries.sort(key=lambda e: (e.name.casefold(), e.name))
        except OSError:
            raise Failure('unreadable_directory', relative or '.') from None
        seen = set()
        for item in entries:
            visited += 1
            if visited > count_limit:
                raise Failure('entry_count_limit')
            if not safe_name(item.name) or item.name.casefold() in seen:
                raise Failure('unsafe_or_ambiguous_entry', relative or '.')
            seen.add(item.name.casefold())
            rel = f'{relative}/{item.name}' if relative else item.name
            path = folder / item.name
            try:
                info = item.stat(follow_symlinks=False)
            except OSError:
                raise Failure('unreadable_entry', rel) from None
            if linked(info):
                raise Failure('linked_path', rel)
            if stat.S_ISDIR(info.st_mode):
                pending.append((path, rel))
            elif stat.S_ISREG(info.st_mode):
                # Windows DirEntry.stat can omit inode/device fields. Obtain
                # the same path-stat identity used by the checked open.
                records[rel] = (path, identity(checked(path)))
            else:
                raise Failure('not_a_regular_file', rel)
    return records, 'directory'


def report(mode):
    return {'schema_version':1, 'tool':{'name':'save-snapshot-verifier','version':VERSION},
            'mode':mode, 'summary':{'complete':False, 'files':0, 'bytes':0},
            'sources':[], 'differences':[], 'errors':[],
            'limitations':[
                'Local ordinary files only. Links, reparse points, device/network paths and ambiguous case names are refused.',
                'A stat/identity recheck is not an atomic filesystem snapshot. Close the game and other writers first.',
                'Hashes detect differences against this manifest; an editable manifest does not authenticate a backup or prove authorship.',
                'Reports and manifests contain relative names, labels, sizes and hashes. Review before sharing; snapshot data may be private.',
                'No restore, replacement, retention pruning, save-format validation or cloud upload is implemented.',
                'Failed creation may leave a new partial destination with an INCOMPLETE.json marker; it is not a verified snapshot.',
            ]}


def parse_sources(values):
    if len(values) > 64:
        raise Failure('source_count_limit')
    result, names = [], set()
    for value in values:
        if '=' not in value:
            raise Failure('expected_label_equals_path')
        label, raw = value.split('=', 1)
        if not LABEL.fullmatch(label) or not safe_name(label) or label.casefold() in names:
            raise Failure('invalid_or_duplicate_label')
        names.add(label.casefold())
        root = absolute(raw)
        checked(root)
        if any(within(root, old) or within(old, root) for _, old in result):
            raise Failure('overlapping_inputs')
        result.append((label, root))
    return result


def output_path(value, protected):
    if value is None:
        return None
    path = absolute(value)
    fresh(path)
    if any(within(path, root) for root in protected):
        raise Failure('output_inside_input_or_snapshot')
    return path


def make_parent(path, base):
    directory(base)
    relative = path.parent.relative_to(base)
    current = base
    for part in relative.parts:
        current = current / part
        try:
            current.mkdir()
        except FileExistsError:
            pass
        directory(current)


def create_snapshot(args, result):
    sources = parse_sources(args.source)
    destination = absolute(args.destination)
    fresh(destination)
    if any(within(destination, root) or within(root, destination) for _, root in sources):
        raise Failure('overlapping_destination')
    output = output_path(args.output, [destination, *(root for _, root in sources)])
    selection = []
    total, count = 0, 0
    for label, root in sources:
        files, kind = inventory(root, args.max_entries)
        count += len(files)
        if count > args.max_entries:
            raise Failure('entry_count_limit')
        for relative, (path, fingerprint) in files.items():
            size = fingerprint[2]
            if size > args.max_file_bytes:
                raise Failure('file_byte_limit', f'{label}/{relative}')
            total += size
            if total > args.max_total_bytes:
                raise Failure('total_byte_limit')
        result['sources'].append({'label':label, 'kind':kind, 'files':len(files)})
        selection.append((label, root, files, kind))
    if not count:
        raise Failure('no_files_selected')
    if not args.confirm_closed:
        raise Failure('confirm_closed_required')
    # No existing destination is merged, replaced or deleted. Failure leaves a
    # visibly incomplete new folder so valuable data is never removed as cleanup.
    destination.mkdir()
    marker = destination / 'INCOMPLETE.json'
    new_file(marker, json_bytes({'state':'INCOMPLETE','tool':'save-snapshot-verifier'}))
    marker_id = identity(checked(marker))
    data_root = destination / 'data'; data_root.mkdir()
    manifest = {'schema_version':1, 'tool':'save-snapshot-verifier', 'version':VERSION,
                'created_utc':datetime.now(timezone.utc).isoformat(),
                'sources':result['sources'], 'files':[]}
    copies = {}
    for label, root, files, kind in selection:
        for relative, (source, expected) in sorted(files.items()):
            key = f'{label}/{relative}'
            target = data_root.joinpath(*key.split('/'))
            make_parent(target, data_root)
            with readonly(source, args.max_file_bytes) as stream:
                before = os.fstat(stream.fileno())
                if identity(before) != expected:
                    raise Failure('input_changed', key)
                sha, size = hashlib.sha256(), 0
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
                with os.fdopen(os.open(target, flags, 0o600), 'wb') as copy:
                    while block := stream.read(min(CHUNK, args.max_file_bytes - size + 1)):
                        size += len(block)
                        if size > args.max_file_bytes:
                            raise Failure('file_byte_limit', key)
                        copy.write(block)
                        sha.update(block)
                    copy.flush()
                    os.fsync(copy.fileno())
                unchanged(source, stream, before)
                if size != before.st_size:
                    raise Failure('input_changed', key)
            copied_size, copied_hash = digest(target, args.max_file_bytes)
            if copied_size != size or copied_hash != sha.hexdigest():
                raise Failure('copy_verification_failed', key)
            manifest['files'].append({'path':key,'bytes':size,'sha256':copied_hash})
            copies[key] = (target, identity(checked(target)))
    for _, root, original, kind in selection:
        after, after_kind = inventory(root, args.max_entries)
        if after_kind != kind or after != original:
            raise Failure('input_tree_changed')
    actual_copies, _ = inventory(data_root, args.max_entries)
    if actual_copies != copies:
        raise Failure('snapshot_tree_changed')
    encoded = json_bytes(manifest)
    if len(encoded) > MAX_MANIFEST:
        raise Failure('manifest_byte_limit')
    new_file(destination / 'manifest.json', encoded)
    if identity(checked(marker)) != marker_id:
        raise Failure('snapshot_marker_changed')
    marker.unlink()
    result['summary'].update(complete=True, files=count, bytes=total, copies_verified=True)
    return output


def manifest_path(value):
    if not isinstance(value, str) or '\\' in value or len(value) > 4096:
        raise Failure('invalid_manifest_path')
    parts = value.split('/')
    if len(parts) < 2 or any(not safe_name(part) for part in parts):
        raise Failure('invalid_manifest_path')
    return parts


def verify_snapshot(args, result):
    root = absolute(args.snapshot)
    directory(root)
    output = output_path(args.output, [root])
    names = {entry.name.casefold():entry.name for entry in root.iterdir()}
    if set(names) != {'manifest.json','data'} or len(list(root.iterdir())) != 2:
        raise Failure('incomplete_or_unexpected_snapshot_layout')
    manifest_file = root / names['manifest.json']
    with readonly(manifest_file, MAX_MANIFEST) as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(MAX_MANIFEST + 1)
        unchanged(manifest_file, stream, before)
    if len(raw) > MAX_MANIFEST:
        raise Failure('manifest_byte_limit')
    try:
        manifest = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError):
        raise Failure('invalid_manifest') from None
    if (not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int
            or manifest.get('schema_version') != 1
            or manifest.get('tool') != 'save-snapshot-verifier'
            or not isinstance(manifest.get('files'), list)
            or not isinstance(manifest.get('sources'), list)):
        raise Failure('invalid_manifest')
    entries = manifest['files']
    if not 1 <= len(entries) <= args.max_entries:
        raise Failure('invalid_manifest_count')
    labels = set()
    for source in manifest['sources']:
        if (not isinstance(source, dict) or not isinstance(source.get('label'), str)
                or not LABEL.fullmatch(source['label']) or not safe_name(source['label'])
                or source['label'].casefold() in labels or source.get('kind') not in ('file','directory')):
            raise Failure('invalid_manifest_source')
        labels.add(source['label'].casefold())
    wanted, folded, total = {}, set(), 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise Failure('invalid_manifest_entry')
        parts = manifest_path(entry.get('path'))
        key = entry['path']
        size, sha = entry.get('bytes'), entry.get('sha256')
        if (parts[0].casefold() not in labels or key.casefold() in folded
                or not isinstance(size,int) or isinstance(size,bool) or size < 0
                or not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha)):
            raise Failure('invalid_manifest_entry')
        if size > args.max_file_bytes:
            raise Failure('file_byte_limit', key)
        folded.add(key.casefold()); wanted[key] = entry
        total += size
        if total > args.max_total_bytes:
            raise Failure('total_byte_limit')
    data_root = root / names['data']
    directory(data_root)
    observed, _ = inventory(data_root, args.max_entries)
    if sum(fingerprint[2] for _, fingerprint in observed.values()) > args.max_total_bytes:
        raise Failure('total_byte_limit')
    result['summary'].update(files=len(wanted), bytes=total, matched_files=0)
    for key in sorted(set(wanted) | set(observed)):
        if key not in wanted:
            result['differences'].append({'path':key,'code':'unexpected_file'})
        elif key not in observed:
            result['differences'].append({'path':key,'code':'missing_file'})
        else:
            size, sha = digest(observed[key][0], args.max_file_bytes)
            expected = wanted[key]
            if size != expected['bytes'] or sha != expected['sha256']:
                result['differences'].append({'path':key,'code':'changed_file'})
            else:
                result['summary']['matched_files'] += 1
    after, _ = inventory(data_root, args.max_entries)
    if after != observed:
        raise Failure('snapshot_tree_changed')
    with readonly(manifest_file, MAX_MANIFEST) as stream:
        if stream.read(MAX_MANIFEST + 1) != raw:
            raise Failure('manifest_changed')
    # Untrusted extra metadata from a manifest is deliberately never echoed.
    result['summary']['complete'] = True
    return output


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, 'Error: invalid arguments; use --help.\n')


def positive(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('expected a positive integer') from None
    if not 1 <= number < sys.maxsize:
        raise argparse.ArgumentTypeError('expected a positive integer')
    return number


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    modes = parser.add_subparsers(dest='mode', required=True, parser_class=Parser)
    for name in ('snapshot','verify'):
        command = modes.add_parser(name)
        command.add_argument('--output', help='new JSON report outside inputs and snapshot; default stdout')
        command.add_argument('--max-file-bytes', type=positive, default=DEFAULT_FILE)
        command.add_argument('--max-total-bytes', type=positive, default=DEFAULT_TOTAL)
        command.add_argument('--max-entries', type=positive, default=DEFAULT_COUNT)
        if name == 'snapshot':
            command.add_argument('--source', action='append', required=True, metavar='LABEL=PATH', help='repeat for selected files or directories')
            command.add_argument('--destination', required=True, help='new snapshot folder; parent must exist')
            command.add_argument('--confirm-closed', action='store_true', help='attest that game and other input writers are closed')
        else:
            command.add_argument('--snapshot', required=True)
    args = parser.parse_args(argv)
    result, output = report(args.mode), None
    try:
        output = create_snapshot(args, result) if args.mode == 'snapshot' else verify_snapshot(args, result)
    except Failure as exc:
        result['summary']['complete'] = False
        item = {'code':exc.code}
        if exc.path is not None:
            item['path'] = exc.path
        result['errors'].append(item)
    except (OSError, ValueError, OverflowError, MemoryError, RecursionError):
        result['summary']['complete'] = False
        result['errors'].append({'code':'operation_failed'})
    try:
        # Errors go to stdout rather than writing a requested output that has
        # not passed every preflight check or lies in a partial snapshot.
        if output is not None:
            new_file(output, json_bytes(result))
        else:
            print(json_bytes(result).decode('utf-8'), end='')
    except (Failure, OSError, ValueError):
        print('Error: unable to create new report.', file=sys.stderr)
        return 1
    if not result['summary']['complete']:
        return 1
    return 2 if result['differences'] else 0


if __name__ == '__main__':
    sys.exit(main())
