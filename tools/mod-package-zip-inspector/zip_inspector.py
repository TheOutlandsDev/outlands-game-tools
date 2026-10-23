#!/usr/bin/env python3
"""Read bounded classic ZIP layout metadata without extraction. Original MIT source.

Python 3.12+ standard library. See ../../LICENSE and README.md for scope.
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
import unicodedata

VERSION = '1.0.0'
MIB = 1024 * 1024
REPORT_LIMIT, METADATA_LIMIT = 8 * MIB, 32 * MIB
ENTRY_LIMIT, CENTRAL_LIMIT, NAME_LIMIT = 10000, 8 * MIB, 1024
PATH_LIMIT = 1024
TOTAL_READ_LIMIT = 32 * MIB
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)
LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')


class Failure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


# Ordinary local filesystem and exclusive-output guards are shared MIT patterns.
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


def region(stream, offset, count, size, counter):
    if offset < 0 or count < 0 or offset + count > size:
        raise Failure('metadata_range_invalid')
    counter[0] += count
    if counter[0] > TOTAL_READ_LIMIT:
        raise Failure('metadata_read_limit')
    stream.seek(offset)
    data = stream.read(count)
    if len(data) != count:
        raise Failure('truncated_archive')
    return data


def extra_fields(data):
    pos, ids = 0, []
    while pos < len(data):
        if pos + 4 > len(data):
            raise Failure('malformed_extra_field')
        tag, size = struct.unpack_from('<HH', data, pos)
        pos += 4
        if pos + size > len(data):
            raise Failure('malformed_extra_field')
        if tag in (1, 0x7075, 0x6375):
            raise Failure('unsupported_zip64_or_unicode_override')
        ids.append(tag)
        pos += size
    return ids


def path_issues(name):
    path = name[:-1] if name.endswith('/') else name
    parts = path.split('/')
    issues = []
    if len(parts) > 64 or any(not component(part) for part in parts):
        issues.append('unsafe_path')
    if not name.isascii():
        issues.append('non_ascii_name')
    return issues


def inspect_stream(stream, size, label, budget):
    counter = [0]
    def read(offset, count):
        return region(stream, offset, count, size, counter)
    if not 22 <= size < 0xFFFFFFFF:
        raise Failure('unsupported_archive_size')
    tail = read(max(0, size - 65557), min(size, 65557))
    candidates, pos = [], 0
    while True:
        pos = tail.find(b'PK\x05\x06', pos)
        if pos < 0:
            break
        if pos + 22 <= len(tail) and pos + 22 + struct.unpack_from('<H', tail, pos + 20)[0] == len(tail):
            candidates.append(size - len(tail) + pos)
        pos += 1
    if len(candidates) != 1:
        raise Failure('missing_or_ambiguous_end_record')
    end = candidates[0]
    sig, disk, central_disk, disk_count, count, length, start, comment = struct.unpack('<4s4H2IH', read(end, 22))
    if disk or central_disk or disk_count != count:
        raise Failure('unsupported_multidisk')
    if count == 0xFFFF or length == 0xFFFFFFFF or start == 0xFFFFFFFF:
        raise Failure('unsupported_zip64')
    if count > ENTRY_LIMIT:
        raise Failure('entry_count_limit')
    if length > CENTRAL_LIMIT:
        raise Failure('central_byte_limit')
    if start + length != end or count * 46 > length:
        raise Failure('central_range_invalid')
    data = read(start, length)
    entries, ranges, position = [], [], 0
    for number in range(count):
        if position + 46 > length:
            raise Failure('truncated_central_entry')
        fields = struct.unpack_from('<4s6H3I5H2I', data, position)
        (signature, made, needed, flags, method, time, date, crc, packed, unpacked,
         namesize, extrasize, commentsize, disk, internal, external, offset) = fields
        if signature != b'PK\x01\x02':
            raise Failure('invalid_central_signature')
        if disk:
            raise Failure('unsupported_multidisk')
        if 0xFFFFFFFF in (packed, unpacked, offset):
            raise Failure('unsupported_zip64')
        if needed > 20 or method not in (0, 8) or flags & ~0x080F or (method == 0 and flags & 6):
            raise Failure('unsupported_version_method_or_flags')
        position += 46
        if not 1 <= namesize <= NAME_LIMIT or position + namesize + extrasize + commentsize > length:
            raise Failure('name_or_central_entry_limit')
        rawname = data[position:position + namesize]
        try:
            name = rawname.decode('utf-8' if flags & 0x800 else 'cp437')
        except UnicodeError:
            raise Failure('invalid_name_encoding') from None
        extra = extra_fields(data[position + namesize:position + namesize + extrasize])
        position += namesize + extrasize + commentsize
        if offset + 30 > start:
            raise Failure('local_range_invalid')
        local = struct.unpack('<4s5H3I2H', read(offset, 30))
        lsig, lv, lf, lm, lt, ld, lc, lp, lu, ln, le = local
        if lsig != b'PK\x03\x04' or (lv, lf, lm, lt, ld, ln) != (needed, flags, method, time, date, namesize):
            raise Failure('local_central_mismatch')
        payload = offset + 30 + ln + le
        if payload + packed > start:
            raise Failure('local_range_invalid')
        variable = read(offset + 30, ln + le)
        if variable[:ln] != rawname:
            raise Failure('local_central_mismatch')
        local_extra = extra_fields(variable[ln:])
        record_end = payload + packed
        if flags & 8:
            if (lc, lp, lu) not in ((0, 0, 0), (crc, packed, unpacked)):
                raise Failure('local_descriptor_mismatch')
            # Signed and unsigned classic descriptors; reject CRC/signature ambiguity.
            if crc == 0x08074B50:
                raise Failure('ambiguous_descriptor')
            prefix = read(record_end, 4)
            descriptor_size = 16 if prefix == b'PK\x07\x08' else 12
            if record_end + descriptor_size > start:
                raise Failure('descriptor_range_invalid')
            descriptor = read(record_end, descriptor_size)
            if struct.unpack('<3I', descriptor[-12:]) != (crc, packed, unpacked):
                raise Failure('descriptor_mismatch')
            record_end += descriptor_size
        elif (lc, lp, lu) != (crc, packed, unpacked):
            raise Failure('local_central_mismatch')
        if method == 0 and not flags & 1 and packed != unpacked:
            raise Failure('stored_size_mismatch')
        directory = name.endswith('/')
        mode = external >> 16 if made >> 8 == 3 else 0
        issues = path_issues(name)
        if flags & 1:
            issues.append('encrypted_entry')
        if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
            issues.append('link_or_special_entry')
        if bool(external & 0x10) != directory or (stat.S_IFMT(mode) == stat.S_IFDIR and not directory):
            issues.append('directory_attribute_mismatch')
        if directory and (packed or unpacked):
            issues.append('directory_has_declared_data')
        if extra or local_extra:
            issues.append('uninterpreted_extra_fields')
        if unpacked > 1024 * MIB:
            issues.append('large_declared_entry')
        if unpacked > MIB and unpacked > max(packed, 1) * 1000:
            issues.append('high_declared_ratio')
        row = {'name': name, 'directory': directory, 'method': method, 'flags': flags,
               'compressed_bytes': packed, 'uncompressed_bytes': unpacked,
               'declared_crc32': f'{crc:08x}', 'local_offset': offset,
               'extra_field_ids': sorted(set(extra + local_extra)), 'issues': issues}
        budget.charge(row)
        entries.append(row)
        ranges.append((offset, record_end))
    if position != length:
        raise Failure('trailing_central_bytes')
    previous = 0
    for first, last in sorted(ranges):
        if first != previous:
            raise Failure('noncontiguous_or_overlapping_layout')
        previous = last
    if previous != start:
        raise Failure('noncontiguous_or_overlapping_layout')
    # The first provider is enough evidence: bound output, avoid pairwise expansion.
    exact, folded = {}, {}
    for number, row in enumerate(entries):
        name = row['name'].rstrip('/')
        key = unicodedata.normalize('NFC', name).casefold()
        budget.charge({'name': name, 'comparison_key': key, 'entry': number})
        if name in exact:
            row['issues'].append('duplicate_name')
            row['first_name_entry'] = exact[name]
        elif key in folded:
            row['issues'].append('case_or_normalization_collision')
            row['first_name_entry'] = folded[key]
        exact.setdefault(name, number)
        folded.setdefault(key, number)
    for row in entries:
        parts = unicodedata.normalize('NFC', row['name'].rstrip('/')).casefold().split('/')
        for depth in range(1, len(parts)):
            other = folded.get('/'.join(parts[:depth]))
            if other is not None and not entries[other]['directory']:
                row['issues'].append('file_directory_collision')
                row['ancestor_entry'] = other
                break
        budget.charge({'issues': row['issues']})
    total = sum(row['uncompressed_bytes'] for row in entries)
    issues = []
    if total > 8 * 1024 * MIB:
        issues.append('large_declared_total')
    files = [row['name'] for row in entries if not row['directory']]
    wrapper = None
    if files and all('/' in name and not path_issues(name) for name in files):
        tops = {name.split('/')[0] for name in files}
        if len(tops) == 1:
            wrapper = next(iter(tops))
            issues.append('common_top_level_folder')
    return {'label': label, 'bytes': size, 'central_directory': {'offset': start, 'bytes': length,
            'sha256': hashlib.sha256(data).hexdigest()}, 'archive_comment_bytes': comment,
            'metadata_bytes_read': counter[0], 'entries': entries, 'issues': issues,
            'common_top_level_folder': wrapper, 'declared_total_uncompressed_bytes': total}


def blank():
    return {'schema_version': 1, 'kind': 'mod-package-zip-layout-inspector', 'tool_version': VERSION,
            'complete': False, 'policy': {'format': 'single_disk_contiguous_classic_zip32',
            'methods': [0, 8], 'extracted': False, 'payload_integrity_checked': False,
            'comparison': 'NFC_casefold', 'metadata_only': True},
            'limits': {'archive_bytes_exclusive': 0xFFFFFFFF, 'entries': ENTRY_LIMIT,
            'central_bytes': CENTRAL_LIMIT, 'name_bytes': NAME_LIMIT, 'metadata_read_bytes': TOTAL_READ_LIMIT,
            'metadata_accounting_bytes': METADATA_LIMIT, 'report_bytes': REPORT_LIMIT},
            'archive': None, 'errors': []}


def inspect(args):
    report, target = blank(), None
    try:
        label, equals, raw = args.archive.partition('=')
        if not equals or not LABEL.fullmatch(label):
            raise Failure('invalid_label')
        path = local_path(raw)
        target = new_output(args.output, [path])
        info = checked(path)
        if not stat.S_ISREG(info.st_mode):
            raise Failure('not_a_regular_file')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            if identity(os.fstat(stream.fileno())) != identity(info):
                raise Failure('input_changed')
            archive = inspect_stream(stream, info.st_size, label, Budget())
            if identity(os.fstat(stream.fileno())) != identity(info) or identity(checked(path)) != identity(info):
                raise Failure('input_changed')
        report.update(complete=True, archive=archive)
    except Failure as error:
        report['errors'].append({'code': error.code})
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


def parser():
    result = Parser(description=__doc__)
    result.add_argument('--version', action='version', version=VERSION)
    result.add_argument('--archive', required=True, metavar='LABEL=FILE', help='One explicit ordinary local ZIP and a shareable alias')
    result.add_argument('--output', help='New JSON report, existing ordinary parent directory')
    return result


def main(argv=None):
    try:
        report, target = inspect(parser().parse_args(argv))
        write(encode(report), target)
        if not report['complete']:
            return 1
        archive = report['archive']
        return 2 if archive['issues'] or any(row['issues'] for row in archive['entries']) else 0
    except (Failure, OSError, ValueError, OverflowError, RecursionError) as error:
        report = blank()
        report['errors'].append({'code': error.code if isinstance(error, Failure) else 'operation_failed'})
        try:
            sys.stdout.write(encode(report).decode('utf-8'))
        except (Failure, OSError, ValueError):
            pass
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
