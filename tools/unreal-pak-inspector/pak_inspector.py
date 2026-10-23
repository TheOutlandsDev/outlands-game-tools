#!/usr/bin/env python3
"""Inspect standard unencrypted version-3 Unreal PAK indexes; never extract payloads.

Original MIT source, Python 3.12+ standard library. See ../../LICENSE.
Index assertions and virtual-path overlaps do not establish game compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys

VERSION = '1.0.0'
MAGIC, FOOTER_BYTES = 0x5A6F12E1, 44
MIB = 1024 * 1024
REPORT_LIMIT, METADATA_LIMIT = 8 * MIB, 32 * MIB
PATH_LIMIT, DEPTH_LIMIT, STRING_UNITS, BLOCK_LIMIT = 1024, 64, 2049, 1024
DEFAULTS = {'max_paks': 32, 'max_archive_bytes': 64 * 1024**3,
            'max_index_bytes': 8 * MIB, 'max_total_index_bytes': 32 * MIB,
            'max_entries': 50000, 'max_conflicts': 10000}
HARD = {'max_paks': 128, 'max_archive_bytes': 1024**4,
        'max_index_bytes': 64 * MIB, 'max_total_index_bytes': 128 * MIB,
        'max_entries': 200000, 'max_conflicts': 100000}
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)
LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')


class Failure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def component(value):
    return (0 < len(value) <= 255 and value not in ('.', '..')
            and not value.endswith((' ', '.')) and not BAD.search(value)
            and not DEVICE.match(value))


def local_path(value):
    raw = os.fspath(value)
    if (not raw or raw.startswith(('\\\\', '//')) or '\x00' in raw
            or re.match(r'^[A-Za-z]:(?:$|[^\\/])', raw)):
        raise Failure('invalid_local_path')
    path = Path(os.path.abspath(raw))
    if str(path).startswith(('\\\\', '//')):
        raise Failure('invalid_local_path')
    if len(str(path)) > PATH_LIMIT or len(path.parts) > 128:
        raise Failure('local_path_limit')
    if any(not component(part) for part in path.parts if part != path.anchor):
        raise Failure('unsafe_local_name')
    return path


def checked(path):
    try:
        for part in [*reversed(path.parents), path]:
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise Failure('linked_path')
            if part != path and not stat.S_ISDIR(info.st_mode):
                raise Failure('invalid_parent')
        return info
    except OSError:
        raise Failure('unreadable_or_missing_path') from None


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def object_id(info):
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def new_output(value, inputs):
    if value is None:
        return None
    path = local_path(value)
    if not stat.S_ISDIR(checked(path.parent).st_mode):
        raise Failure('invalid_output_parent')
    if any(str(path).casefold() == str(source).casefold() for source in inputs):
        raise Failure('output_overlaps_input')
    try:
        path.lstat()
    except FileNotFoundError:
        return path
    except OSError:
        raise Failure('unsafe_output') from None
    raise Failure('output_exists')


class Budget:
    """Conservative cumulative metadata accounting, not a process-RAM guarantee."""
    def __init__(self):
        self.used = 0

    def charge(self, value, overhead=256):
        count = overhead
        for piece in json.JSONEncoder(ensure_ascii=True, separators=(',', ':')).iterencode(value):
            count += len(piece)
            if self.used + count > METADATA_LIMIT:
                raise Failure('metadata_byte_limit')
        self.used += count


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, size):
        if size < 0 or size > len(self.data) - self.pos:
            raise Failure('truncated_index')
        start = self.pos
        self.pos += size
        return self.data[start:self.pos]

    def number(self, fmt):
        return struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))[0]

    def string(self):
        units = self.number('i')
        if not units or abs(units) > STRING_UNITS:
            raise Failure('unsupported_string_length')
        raw = self.take(abs(units) * (2 if units < 0 else 1))
        terminal = b'\0\0' if units < 0 else b'\0'
        if not raw.endswith(terminal):
            raise Failure('unterminated_string')
        try:
            value = raw[:-len(terminal)].decode('utf-16-le' if units < 0 else 'ascii')
        except UnicodeError:
            raise Failure('unsupported_string_encoding') from None
        if '\0' in value:
            raise Failure('embedded_string_nul')
        return value


def portable_asset(value):
    if (not value or len(value) > PATH_LIMIT or not value.isascii()
            or value.startswith('/') or '\\' in value):
        raise Failure('unsafe_virtual_path')
    parts = value.split('/')
    if len(parts) > DEPTH_LIMIT or any(not component(part) for part in parts):
        raise Failure('unsafe_virtual_path')
    return value


def mount_prefix(mount):
    # These parents name a common virtual namespace; never resolve them on disk.
    if not mount.startswith('../../../') or not mount.endswith('/'):
        raise Failure('unsupported_mount')
    suffix = mount[9:-1] if len(mount) > 9 else ''
    if suffix:
        portable_asset(suffix)
    return suffix + '/' if suffix else ''


def entry(reader, index_offset, prefix):
    path = portable_asset(reader.string())
    virtual = portable_asset(prefix + path)
    offset, size, unpacked = (reader.number('q') for unused in range(3))
    method = reader.number('I')
    declared_hash = reader.take(20).hex()
    count, first, last, previous_end = 0, None, None, None
    if method:
        count = reader.number('i')
        if not 1 <= count <= BLOCK_LIMIT:
            raise Failure('compression_block_limit')
        header_bytes = 57 + 16 * count
        if min(offset, size, unpacked) < 0 or offset + header_bytes + size > index_offset:
            raise Failure('entry_range_invalid')
        for unused in range(count):
            start, end = reader.number('q'), reader.number('q')
            if (start < offset + header_bytes or end <= start or end > offset + header_bytes + size
                    or (previous_end is not None and start != previous_end)):
                raise Failure('compression_range_invalid')
            if first is None:
                first = start
            previous_end, last = end, end
    else:
        header_bytes = 53
    flags, block_size = reader.number('B'), reader.number('I')
    if flags:
        raise Failure('unsupported_encryption_or_flags')
    if min(offset, size, unpacked) < 0 or offset + header_bytes + size > index_offset:
        raise Failure('entry_range_invalid')
    if not method and size != unpacked:
        raise Failure('stored_size_mismatch')
    if method and (not block_size or not unpacked or not size
                   or count != (unpacked + block_size - 1) // block_size
                   or first != offset + header_bytes or last != offset + header_bytes + size):
        raise Failure('compression_metadata_invalid')
    return {'path': path, 'virtual_path': virtual, 'offset': offset,
            'header_bytes': header_bytes, 'stored_bytes': size, 'uncompressed_bytes': unpacked,
            'compression_method': method, 'block_count': count, 'block_size': block_size,
            'declared_sha1': declared_hash}


def region(stream, offset, size):
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise Failure('truncated_archive')
    return data


def inspect_pak(path, label, limits, counters, budget):
    info = checked(path)
    if not stat.S_ISREG(info.st_mode):
        raise Failure('not_a_regular_file')
    if not FOOTER_BYTES <= info.st_size <= limits['max_archive_bytes']:
        raise Failure('archive_size_limit')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(info):
            raise Failure('input_changed')
        footer = region(stream, info.st_size - FOOTER_BYTES, FOOTER_BYTES)
        magic, version, start, size, digest = struct.unpack('<Iiqq20s', footer)
        if magic != MAGIC:
            raise Failure('unsupported_footer')
        if version != 3:
            raise Failure('unsupported_pak_version')
        if start < 0 or size < 8 or start + size != info.st_size - FOOTER_BYTES:
            raise Failure('index_range_invalid')
        if size > limits['max_index_bytes']:
            raise Failure('index_byte_limit')
        counters['index_bytes'] += size
        if counters['index_bytes'] > limits['max_total_index_bytes']:
            raise Failure('total_index_byte_limit')
        data = region(stream, start, size)
        if hashlib.sha1(data).digest() != digest:
            raise Failure('index_hash_mismatch')
        if (identity(os.fstat(stream.fileno())) != identity(info)
                or identity(checked(path)) != identity(info)):
            raise Failure('input_changed')
    reader = Reader(data)
    mount = reader.string()
    prefix = mount_prefix(mount)
    count = reader.number('i')
    if count < 0 or count > limits['max_entries'] - counters['entries']:
        raise Failure('entry_count_limit')
    # Every supported entry requires a filename length/NUL and 53 metadata bytes.
    if count > (len(data) - reader.pos) // 58:
        raise Failure('truncated_index')
    counters['entries'] += count
    entries, names, ranges = [], set(), []
    for number in range(count):
        try:
            record = entry(reader, start, prefix)
            key = record['virtual_path'].lower()
            if key in names:
                raise Failure('duplicate_or_case_colliding_entry')
            budget.charge({'label': label, 'entry': record, 'key': key})
            names.add(key)
            ranges.append((record['offset'], record['offset'] + record['header_bytes'] + record['stored_bytes']))
            entries.append(record)
        except Failure as error:
            error.entry = number
            raise
    if reader.pos != len(data):
        raise Failure('trailing_index_bytes')
    previous = None
    for name in sorted(names, key=lambda value: value.split('/')):
        if previous is not None and name.startswith(previous + '/'):
            raise Failure('internal_file_directory_collision')
        previous = name
    end = -1
    for first, last in sorted(ranges):
        if first < end:
            raise Failure('overlapping_entry_ranges')
        end = last
    budget.charge({'label': label, 'mount': mount, 'index_bytes': size})
    return {'label': label, 'bytes': info.st_size, 'version': version, 'mount': mount,
            'index': {'offset': start, 'bytes': size, 'sha1': digest.hex(),
                      'sha256': hashlib.sha256(data).hexdigest(), 'hash_verified': True},
            'entries': entries}, info


def conflicts(paks, limits, budget):
    paths = {}
    for pak in paks:
        for number, record in enumerate(pak['entries']):
            key = record['virtual_path'].lower()
            provider = {'pak': pak['label'], 'entry': number}
            budget.charge({'key': key, 'provider': provider})
            paths.setdefault(key, []).append(provider)
    output, ancestors = [], []
    def add(row):
        if len(output) >= limits['max_conflicts']:
            raise Failure('conflict_count_limit')
        budget.charge(row)
        output.append(row)
    for key in sorted(paths, key=lambda value: value.split('/')):
        providers = paths[key]
        if len(providers) > 1:
            add({'kind': 'path_overlap', 'path': key, 'providers': providers})
        while ancestors and not key.startswith(ancestors[-1] + '/'):
            ancestors.pop()
        for ancestor in ancestors:
            add({'kind': 'file_directory', 'path': ancestor, 'descendant': key,
                 'file_providers': paths[ancestor], 'descendant_providers': providers})
        ancestors.append(key)
    return output, len(paths)


def blank(limits=None):
    return {'schema_version': 1, 'kind': 'unreal-pak-index-conflict-inspector', 'tool_version': VERSION,
            'complete': False, 'policy': {'pak_version': 3, 'path_comparison': 'ascii_case_insensitive',
                'payloads_read': False, 'local_headers_checked': False, 'load_order_inferred': False},
            'limits': DEFAULTS.copy() if limits is None else limits, 'paks': [], 'conflicts': [],
            'summary': {'paks': 0, 'entries': 0, 'unique_paths': 0, 'index_bytes': 0,
                        'path_overlaps': 0, 'file_directory_conflicts': 0}, 'errors': []}


def inspect(args):
    limits = {name: getattr(args, name) for name in DEFAULTS}
    report, target, active = blank(limits), None, None
    try:
        if not 1 <= len(args.pak) <= limits['max_paks']:
            raise Failure('pak_count_limit')
        selected, labels = [], set()
        for value in args.pak:
            label, equals, raw = value.partition('=')
            if not equals or LABEL.fullmatch(label) is None or label.lower() in labels:
                raise Failure('invalid_or_duplicate_label')
            labels.add(label.lower())
            selected.append((label, local_path(raw)))
        selected.sort()
        target = new_output(args.output, [path for unused, path in selected])
        budget, counters, seen, states, paks = Budget(), {'entries': 0, 'index_bytes': 0}, set(), [], []
        for active, path in selected:
            info = checked(path)
            if object_id(info) in seen:
                raise Failure('repeated_archive')
            seen.add(object_id(info))
            pak, info = inspect_pak(path, active, limits, counters, budget)
            states.append((active, path, info))
            paks.append(pak)
        active = None
        findings, unique = conflicts(paks, limits, budget)
        for active, path, info in states:
            if identity(checked(path)) != identity(info):
                raise Failure('input_changed')
        report.update(complete=True, paks=paks, conflicts=findings,
                      summary={'paks': len(paks), 'entries': counters['entries'], 'unique_paths': unique,
                               'index_bytes': counters['index_bytes'],
                               'path_overlaps': sum(row['kind'] == 'path_overlap' for row in findings),
                               'file_directory_conflicts': sum(row['kind'] == 'file_directory' for row in findings)})
    except Failure as error:
        row = {'code': error.code}
        if active is not None:
            row['pak'] = active
        if getattr(error, 'entry', None) is not None:
            row['entry'] = error.entry
        report['errors'].append(row)
    return report, target


def encode(report):
    data = bytearray()
    for piece in json.JSONEncoder(ensure_ascii=True, indent=2).iterencode(report):
        block = piece.encode('utf-8')
        if len(data) + len(block) + 1 > REPORT_LIMIT:
            raise Failure('report_byte_limit')
        data.extend(block)
    data.extend(b'\n')
    return data


def write(data, target):
    if target is None:
        sys.stdout.write(data.decode('utf-8'))
        return
    if not stat.S_ISDIR(checked(target.parent).st_mode):
        raise Failure('invalid_output_parent')
    created = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(target, flags, 0o600), 'wb') as stream:
            created = os.fstat(stream.fileno())
            stream.write(data)
            stream.flush()
            if object_id(checked(target)) != object_id(created):
                raise Failure('output_changed')
    except (Failure, OSError):
        if created is not None:
            try:
                if object_id(target.lstat()) == object_id(created):
                    target.unlink()
            except OSError:
                pass
        raise Failure('output_write_failed') from None


class Parser(argparse.ArgumentParser):
    def error(self, unused):
        raise Failure('invalid_arguments')


def positive(name):
    def parse(value):
        try:
            number = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError('bounded positive integer required') from None
        if not 1 <= number <= HARD[name]:
            raise argparse.ArgumentTypeError('bounded positive integer required')
        return number
    return parse


def parser():
    result = Parser(description=__doc__)
    result.add_argument('--version', action='version', version=VERSION)
    result.add_argument('--pak', action='append', required=True, metavar='LABEL=FILE',
                        help='Repeat an explicit ordinary local PAK, using a shareable alias; order is not priority')
    result.add_argument('--output', help='Exclusive new JSON report; existing parent required')
    for name, default in DEFAULTS.items():
        result.add_argument('--' + name.replace('_', '-'), type=positive(name), default=default,
                            help=f'Default {default}; hard ceiling {HARD[name]}')
    return result


def main(argv=None):
    report = blank()
    try:
        report, target = inspect(parser().parse_args(argv))
        write(encode(report), target)
        return (2 if report['conflicts'] else 0) if report['complete'] else 1
    except (Failure, OSError, ValueError, OverflowError, RecursionError) as error:
        report = blank(report['limits'])
        report['errors'].append({'code': error.code if isinstance(error, Failure) else 'operation_failed'})
        try:
            sys.stdout.write(encode(report).decode('utf-8'))
        except (Failure, OSError, ValueError):
            pass
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
