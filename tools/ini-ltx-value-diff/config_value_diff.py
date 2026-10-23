#!/usr/bin/env python3
"""Compare explicit literal INI/LTX assignments without changing either source.

Original MIT source; see ../../LICENSE. Python 3.12+, standard library only.
No ConfigParser interpolation, configuration merge, includes, or engine calls.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys

VERSION = '1.0.0'
CHUNK = 64 * 1024
MIB = 1024 * 1024
REPORT_LIMIT, METADATA_LIMIT, LINE_LIMIT, NAME_LIMIT = 8 * MIB, 16 * MIB, 65536, 255
PARENT_LIMIT = 256
DEFAULT_LIMITS = {'max_file_bytes': 2 * MIB, 'max_lines': 100000,
                  'max_records': 20000, 'max_changes': 20000}
HARD_LIMITS = {'max_file_bytes': 16 * MIB, 'max_lines': 1000000,
               'max_records': 200000, 'max_changes': 200000}
INI_SECTION = re.compile(r'[A-Za-z0-9_. $-]+\Z')
LTX_SECTION = re.compile(r'[A-Za-z0-9_.$-]+\Z')
KEY_NAME = re.compile(r'[A-Za-z0-9_.$:-]+\Z')
HEADER = re.compile(r'^\[([^\]]*)\](.*)$')
INCLUDE = re.compile(r'^#\s*include\b', re.I)
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)


class Failure(Exception):
    """Public errors contain controlled codes, never native exception text."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def safe_name(value):
    return (isinstance(value, str) and 0 < len(value) <= 255 and value not in ('.', '..')
            and not value.endswith((' ', '.')) and not INVALID.search(value)
            and not DEVICE.match(value))


def absolute(value):
    raw = os.fspath(value)
    if (not isinstance(raw, str) or not raw or '\x00' in raw
            or raw.startswith(('\\\\', '//'))
            or re.match(r'^[A-Za-z]:(?:$|[^\\/])', raw)):
        raise Failure('invalid_local_path')
    path = Path(os.path.abspath(raw))
    if str(path).startswith(('\\\\', '//')):
        raise Failure('invalid_local_path')
    if len(str(path)) > 1024 or len(path.parts) > 128:
        raise Failure('local_path_limit')
    if any(not safe_name(part) for part in path.parts if part != path.anchor):
        raise Failure('unsafe_path_name')
    return path


def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def checked(path):
    try:
        for part in [*reversed(path.parents), path]:
            info = part.lstat()
            if linked(info):
                raise Failure('linked_path')
            if part != path and not stat.S_ISDIR(info.st_mode):
                raise Failure('invalid_parent')
        return info
    except OSError:
        raise Failure('unreadable_or_missing_path') from None


def directory(path):
    if not stat.S_ISDIR(checked(path).st_mode):
        raise Failure('not_a_directory')


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def object_id(info):
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def read_bounded(path, limit):
    before = checked(path)
    if not stat.S_ISREG(before.st_mode):
        raise Failure('not_a_regular_file')
    if before.st_size > limit:
        raise Failure('input_byte_limit')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            if identity(os.fstat(stream.fileno())) != identity(before):
                raise Failure('input_changed')
            data = bytearray()
            while block := stream.read(min(CHUNK, limit - len(data) + 1)):
                data.extend(block)
                if len(data) > limit:
                    raise Failure('input_byte_limit')
            if (len(data) != before.st_size or identity(os.fstat(stream.fileno())) != identity(before)
                    or identity(checked(path)) != identity(before)):
                raise Failure('input_changed')
    except OSError:
        raise Failure('unreadable_file') from None
    return bytes(data), before


def destination(value, inputs):
    if value is None:
        return None
    path = absolute(value)
    directory(path.parent)
    if any(str(path).casefold() == str(item).casefold() for item in inputs):
        raise Failure('output_overlaps_input')
    try:
        path.lstat()
    except FileNotFoundError:
        return path
    except OSError:
        raise Failure('unsafe_output') from None
    raise Failure('output_exists')


def write_report(data, path):
    if path is None:
        sys.stdout.write(data.decode('utf-8'))
        return
    directory(path.parent)
    created = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(path, flags, 0o600), 'wb') as stream:
            created = os.fstat(stream.fileno())
            stream.write(data)
            stream.flush()
            if object_id(checked(path)) != object_id(created):
                raise Failure('output_changed')
    except (Failure, OSError):
        if created is not None:
            try:
                if object_id(path.lstat()) == object_id(created):
                    path.unlink()
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
        except (ValueError, TypeError):
            raise argparse.ArgumentTypeError('positive bounded integer required') from None
        if not 1 <= number <= HARD_LIMITS[name]:
            raise argparse.ArgumentTypeError('positive bounded integer required')
        return number
    return parse


def policy(args):
    inline = args.inline_comments
    if inline is None:
        inline = 'none' if args.dialect == 'ini' else 'semicolon'
    return {'dialect': args.dialect, 'case': args.case, 'duplicate_keys': args.duplicate_keys,
            'inline_comments': inline, 'before_encoding': args.before_encoding,
            'after_encoding': args.after_encoding, 'include_values': args.include_values}


def blank_report(settings=None, limits=None):
    return {'schema_version': 1, 'kind': 'ini-ltx-configuration-value-diff', 'tool_version': VERSION,
            'complete': False, 'policy': {} if settings is None else settings,
            'limits': DEFAULT_LIMITS.copy() if limits is None else limits,
            'inputs': {'before': None, 'after': None},
            'summary': {'sections_added': 0, 'sections_removed': 0, 'parents_changed': 0,
                        'keys_added': 0, 'keys_removed': 0, 'keys_changed': 0, 'keys_unchanged': 0},
            'section_changes': [], 'value_changes': [], 'errors': []}


class Budget:
    """Account bounded escaped record metadata before inserting it into retained maps."""
    def __init__(self):
        self.used = 0

    def charge(self, value):
        total = 0
        for piece in json.JSONEncoder(ensure_ascii=True, separators=(',', ':')).iterencode(value):
            total += len(piece.encode('utf-8'))
            if self.used + total + 64 > METADATA_LIMIT:
                raise Failure('metadata_byte_limit')
        self.used += total + 64


def strip_inline(value):
    quoted = False
    for index, character in enumerate(value):
        if character == '"':
            quoted = not quoted
        elif character == ';' and not quoted:
            return value[:index]
    if quoted:
        raise Failure('unbalanced_double_quote')
    return value


def name(value, pattern, settings):
    result = value.strip(' \t')
    if not 0 < len(result) <= NAME_LIMIT or pattern.fullmatch(result) is None:
        raise Failure('unsupported_identifier')
    return result.lower() if settings['case'] == 'insensitive' else result


def parse_contents(path, encoding, settings, limits, budget, location):
    raw, before = read_bounded(path, limits['max_file_bytes'])
    if encoding == 'utf-16' and not raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        raise Failure('utf16_bom_required')
    try:
        text = raw.decode(encoding)
    except UnicodeError:
        raise Failure('unsupported_encoding') from None
    sections, values = {}, {}
    current, record_count, duplicates = None, 0, 0
    section_pattern = INI_SECTION if settings['dialect'] == 'ini' else LTX_SECTION
    for number, raw_line in enumerate(io.StringIO(text, newline=None), 1):
        location['line'] = number
        if number > limits['max_lines']:
            raise Failure('line_count_limit')
        line = raw_line.rstrip('\r\n')
        if len(line) > LINE_LIMIT:
            raise Failure('line_character_limit')
        if any(((ord(character) < 32 or 127 <= ord(character) <= 159)
                and character not in '\t\r\n') for character in line):
            raise Failure('unsupported_control_character')
        line = line.strip(' \t')
        if not line or line.startswith(';'):
            continue
        if line.startswith('#'):
            if INCLUDE.match(line):
                raise Failure('unsupported_directive')
            if settings['dialect'] == 'ltx' and len(line) > 1 and line[1] not in ' \t':
                raise Failure('unsupported_directive')
            continue
        if settings['inline_comments'] == 'semicolon':
            line = strip_inline(line).strip(' \t')
            if not line:
                continue
        if line.startswith('['):
            match = HEADER.fullmatch(line)
            if match is None:
                raise Failure('unsupported_header')
            section = name(match[1], section_pattern, settings)
            tail = match[2].strip(' \t')
            parents = []
            if tail:
                if settings['dialect'] != 'ltx' or not tail.startswith(':'):
                    raise Failure('unsupported_header')
                if tail.count(',') + 1 > PARENT_LIMIT:
                    raise Failure('parent_count_limit')
                for value in tail[1:].split(','):
                    parent = name(value, LTX_SECTION, settings)
                    budget.charge(parent)  # Account each retained string/list item before append.
                    parents.append(parent)
            if section in sections:
                raise Failure('duplicate_section')
            record_count += 1
            if record_count > limits['max_records']:
                raise Failure('record_count_limit')
            record = {'line': number, 'parents': parents}
            budget.charge({'section': section, **record})
            sections[section] = record
            current = section
            continue
        key, equals, value = line.partition('=')
        if not equals:
            raise Failure('unsupported_assignment')
        if current is None and settings['dialect'] != 'ini':
            raise Failure('global_assignment_not_supported')
        key = name(key, KEY_NAME, settings)
        value = value.strip(' \t')
        record_count += 1
        if record_count > limits['max_records']:
            raise Failure('record_count_limit')
        locator = current, key
        if locator in values:
            if settings['duplicate_keys'] == 'reject':
                raise Failure('duplicate_key')
            duplicates += 1
        record = {'line': number, 'value': value}
        budget.charge({'section': current, 'key': key, **record})
        values[locator] = record
    details = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
               'sections': len(sections), 'keys': len(values), 'duplicate_assignments': duplicates}
    return sections, values, details, before


def parse_source(path, encoding, settings, limits, budget):
    location = {}
    try:
        return parse_contents(path, encoding, settings, limits, budget, location)
    except Failure as error:
        error.line = location.get('line')
        raise


def value_record(record, include_values):
    if record is None:
        return None
    value = record['value']
    result = {'line': record['line'], 'characters': len(value),
              'sha256': hashlib.sha256(value.encode('utf-8')).hexdigest()}
    if include_values:
        result['value'] = value
    return result


def row_bytes(row, remaining):
    total = 0
    for piece in json.JSONEncoder(ensure_ascii=True, separators=(',', ':')).iterencode(row):
        total += len(piece.encode('utf-8'))
        if total > remaining:
            raise Failure('report_byte_limit')
    return total + 1


def differences(before_sections, before_values, after_sections, after_values, report):
    sections, values = [], []
    summary = report['summary'].copy()
    count, retained = 0, 0

    def add(row, destination_rows):
        nonlocal count, retained
        count += 1
        if count > report['limits']['max_changes']:
            raise Failure('change_count_limit')
        retained += row_bytes(row, REPORT_LIMIT - retained)
        if retained > REPORT_LIMIT:
            raise Failure('report_byte_limit')
        destination_rows.append(row)

    for section in sorted(before_sections.keys() | after_sections.keys()):
        old, new = before_sections.get(section), after_sections.get(section)
        if old is None:
            add({'kind': 'added', 'section': section, 'before': None, 'after': new}, sections)
            summary['sections_added'] += 1
        elif new is None:
            add({'kind': 'removed', 'section': section, 'before': old, 'after': None}, sections)
            summary['sections_removed'] += 1
        elif old['parents'] != new['parents']:
            add({'kind': 'parents_changed', 'section': section, 'before': old, 'after': new}, sections)
            summary['parents_changed'] += 1
    keys = before_values.keys() | after_values.keys()
    for section, key in sorted(keys, key=lambda item: (item[0] is not None, item[0] or '', item[1])):
        old, new = before_values.get((section, key)), after_values.get((section, key))
        if old is not None and new is not None and old['value'] == new['value']:
            summary['keys_unchanged'] += 1
            continue
        kind = 'added' if old is None else 'removed' if new is None else 'changed'
        add({'kind': kind, 'section': section, 'key': key,
             'before': value_record(old, report['policy']['include_values']),
             'after': value_record(new, report['policy']['include_values'])}, values)
        summary[{'added': 'keys_added', 'removed': 'keys_removed', 'changed': 'keys_changed'}[kind]] += 1
    # Commit only a full comparison; unsupported/limited data never leaves partial diff claims.
    report['section_changes'], report['value_changes'], report['summary'] = sections, values, summary


def compare(args):
    settings = policy(args)
    limits = {key: getattr(args, key) for key in DEFAULT_LIMITS}
    report, target = blank_report(settings, limits), None
    active_side = None
    try:
        before_path, after_path = absolute(args.before), absolute(args.after)
        target = destination(args.output, [before_path, after_path])
        budget = Budget()
        active_side = 'before'
        before_sections, before_values, details, before_state = parse_source(
            before_path, settings['before_encoding'], settings, limits, budget)
        report['inputs']['before'] = details
        active_side = 'after'
        after_sections, after_values, details, after_state = parse_source(
            after_path, settings['after_encoding'], settings, limits, budget)
        report['inputs']['after'] = details
        active_side = None
        differences(before_sections, before_values, after_sections, after_values, report)
        for active_side, path, state in (('before', before_path, before_state),
                                         ('after', after_path, after_state)):
            if identity(checked(path)) != identity(state):
                raise Failure('input_changed')
        report['complete'] = True
    except Failure as error:
        report['section_changes'], report['value_changes'] = [], []
        report['summary'] = blank_report()['summary']
        record = {'code': error.code}
        if active_side is not None:
            record['side'] = active_side
        if getattr(error, 'line', None) is not None:
            record['line'] = error.line
        report['errors'].append(record)
    return report, target


def encode_report(report):
    data = bytearray()
    for piece in json.JSONEncoder(ensure_ascii=True, indent=2).iterencode(report):
        block = piece.encode('utf-8')
        if len(data) + len(block) + 1 > REPORT_LIMIT:
            raise Failure('report_byte_limit')
        data.extend(block)
    data.extend(b'\n')
    return data


def parser():
    result = Parser(description=__doc__)
    result.add_argument('--version', action='version', version=VERSION)
    result.add_argument('--before', required=True, help='Existing ordinary local before file')
    result.add_argument('--after', required=True, help='Existing ordinary local after file; may be the same file')
    result.add_argument('--dialect', choices=('ini', 'ltx'), required=True,
                        help='Explicit literal grammar; no format detection or engine evaluation')
    result.add_argument('--case', choices=('sensitive', 'insensitive'), default='sensitive',
                        help='Name comparison; insensitive lowercases ASCII section/key/parent names')
    result.add_argument('--duplicate-keys', choices=('reject', 'last'), default='reject',
                        help='Reject duplicates or retain the final assignment and report its duplicate count')
    result.add_argument('--inline-comments', choices=('none', 'semicolon'),
                        help='Default ini:none, ltx:semicolon; semicolon strips outside balanced double quotes')
    for side in ('before', 'after'):
        result.add_argument('--' + side + '-encoding', choices=('utf-8-sig', 'cp1251', 'utf-16'),
                            default='utf-8-sig', help=f'Strict {side} decoding; utf-16 requires a BOM (default utf-8-sig)')
    result.add_argument('--include-values', action='store_true',
                        help='Expose actual parsed changed values; default emits only lengths and SHA-256')
    result.add_argument('--output', help='New JSON file with an existing parent; refuses input paths and existing outputs')
    descriptions = {'max_file_bytes': 'Raw bytes per input file', 'max_lines': 'Physical CR/LF/CRLF lines per input',
                    'max_records': 'Section headers plus all assignments, including duplicates, per input',
                    'max_changes': 'Combined section/value change rows'}
    for name, default in DEFAULT_LIMITS.items():
        result.add_argument('--' + name.replace('_', '-'), type=positive(name), default=default,
                            help=f'{descriptions[name]} (default {default}; hard maximum {HARD_LIMITS[name]})')
    return result


def main(argv=None):
    report = blank_report()
    try:
        args = parser().parse_args(argv)
        report, target = compare(args)
        write_report(encode_report(report), target)
        if not report['complete']:
            return 1
        return 2 if report['section_changes'] or report['value_changes'] else 0
    except (Failure, OSError, ValueError, OverflowError, RecursionError) as error:
        fallback = blank_report(report['policy'], report['limits'])
        fallback['errors'].append({'code': error.code if isinstance(error, Failure) else 'operation_failed'})
        try:
            sys.stdout.write(encode_report(fallback).decode('utf-8'))
        except (Failure, OSError, ValueError):
            pass
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
