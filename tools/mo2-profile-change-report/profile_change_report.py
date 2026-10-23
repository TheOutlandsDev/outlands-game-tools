#!/usr/bin/env python3
"""Compare two explicitly selected saved MO2 modlist files. Original MIT, Python 3.12+."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

VERSION = '1.0.0'
MIB = 1024 * 1024
PATH_LIMIT, FILE_LIMIT, LINE_LIMIT, ENTRY_LIMIT = 1024, 2 * MIB, 2048, 10000
LINE_COUNT_LIMIT, REPORT_LIMIT, METADATA_LIMIT = 50000, 8 * MIB, 32 * MIB
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)
GROUPS = ('mods', 'separators', 'foreign')


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


def read_file(path):
    info = checked(path)
    if not stat.S_ISREG(info.st_mode):
        raise Failure('not_a_regular_file')
    if info.st_size > FILE_LIMIT:
        raise Failure('file_byte_limit')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(info):
            raise Failure('input_changed')
        data = stream.read(FILE_LIMIT + 1)
        if len(data) > FILE_LIMIT:
            raise Failure('file_byte_limit')
        if identity(os.fstat(stream.fileno())) != identity(info) or identity(checked(path)) != identity(info):
            raise Failure('input_changed')
    return data, info


def parse_modlist(data, budget):
    if len(data) > FILE_LIMIT:
        raise Failure('file_byte_limit')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError:
        raise Failure('unsupported_encoding') from None
    if any(ord(char) < 32 and char not in '\r\n\t' for char in text) or '\x7f' in text:
        raise Failure('invalid_modlist_text')
    # Do not split on Unicode line/paragraph separators embedded in names.
    lines = re.split(r'\r\n|\n|\r', text)
    if len(lines) > LINE_COUNT_LIMIT:
        raise Failure('line_count_limit')
    entries, names = [], set()
    for number, body in enumerate(lines, 1):
        if len(body) > LINE_LIMIT:
            error = Failure('line_length_limit')
            error.line = number
            raise error
        if not body or body.startswith('#'):
            continue
        try:
            if body[0] not in '+-*':
                raise Failure('unsupported_modlist_entry')
            marker, name = body[0], body[1:]
            if not component(name) or name != name.strip():
                raise Failure('unsafe_mod_name')
            key = name.casefold()
            if key in names:
                raise Failure('duplicate_or_case_colliding_name')
            names.add(key)
            separator = name.endswith('_separator')
            if marker == '*' and separator:
                raise Failure('foreign_separator_ambiguous')
            group = 'separators' if separator else ('foreign' if marker == '*' else 'mods')
            if len(entries) >= ENTRY_LIMIT:
                raise Failure('entry_count_limit')
            row = {'name': name, 'group': group, 'marker': marker,
                   'enabled': marker == '+' if group == 'mods' else None,
                   'line': number, 'position': len(entries) + 1}
            budget.charge({'entry': row, 'key': key})
            entries.append(row)
        except Failure as error:
            error.line = number
            raise
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'bom': data.startswith(b'\xef\xbb\xbf'), 'entries': entries,
            'counts': {group: sum(row['group'] == group for row in entries) for group in GROUPS}}


def inversions(before, after):
    """All inversion participants with one witness, linear after shared filtering.

    Ranks describe the common subsequences, not physical lines or MO2 priorities.
    This does not select an arbitrary minimal set of presumed user moves.
    """
    common = set(before) & set(after)
    old = [key for key in before if key in common]
    new = [key for key in after if key in common]
    positions = {key: index for index, key in enumerate(old)}
    sequence = [positions[key] for key in new]
    suffix = [len(new)] * (len(new) + 1)
    for index in range(len(new) - 1, -1, -1):
        suffix[index] = min(sequence[index], suffix[index + 1])
    maximum, changed = -1, {}
    for index, rank in enumerate(sequence):
        witness = maximum if maximum > rank else suffix[index + 1]
        if maximum > rank or suffix[index + 1] < rank:
            changed[new[index]] = {'before_common_rank': rank + 1, 'after_common_rank': index + 1,
                                   'crossed_key': old[witness]}
        maximum = max(maximum, rank)
    return changed


def empty_changes(group):
    result = {name: [] for name in ('added', 'removed', 'name_spelling_changed', 'reordered')}
    if group == 'mods':
        result.update(enabled=[], disabled=[])
    if group == 'separators':
        result.update(marker_changed=[], relocated=[])
    return result


def compare(before, after, budget):
    output = {}
    for group in GROUPS:
        left = {row['name'].casefold(): row for row in before['entries'] if row['group'] == group}
        right = {row['name'].casefold(): row for row in after['entries'] if row['group'] == group}
        changes = empty_changes(group)
        order = inversions(list(left), list(right))
        def add(kind, value):
            budget.charge(value)
            changes[kind].append(value)
        for key, row in left.items():
            if key not in right:
                add('removed', row.copy())
        for key, row in right.items():
            if key not in left:
                add('added', row.copy())
                continue
            previous = left[key]
            pair = {'before': previous.copy(), 'after': row.copy()}
            if previous['name'] != row['name']:
                add('name_spelling_changed', pair)
            if group == 'mods' and previous['enabled'] != row['enabled']:
                add('enabled' if row['enabled'] else 'disabled', pair)
            if group == 'separators' and previous['marker'] != row['marker']:
                add('marker_changed', pair)
            if key in order:
                ranks = order[key]
                add('reordered', {**pair, **{k: v for k, v in ranks.items() if k != 'crossed_key'},
                                  'crossed_with': right[ranks['crossed_key']]['name']})
        output[group] = changes
    # Separator relocation also observes crossings of shared entries of other groups.
    left_all = {row['name'].casefold(): row for row in before['entries']}
    right_all = {row['name'].casefold(): row for row in after['entries']}
    stable = {key for key in left_all.keys() & right_all.keys()
              if left_all[key]['group'] == right_all[key]['group']}
    cross = inversions([key for key in left_all if key in stable], [key for key in right_all if key in stable])
    for key, row in right_all.items():
        if row['group'] != 'separators' or key not in cross:
            continue
        ranks = cross[key]
        result = {'before': left_all[key].copy(), 'after': row.copy(),
                  'before_common_rank': ranks['before_common_rank'],
                  'after_common_rank': ranks['after_common_rank'],
                  'crossed_with': right_all[ranks['crossed_key']]['name']}
        budget.charge(result)
        output['separators']['relocated'].append(result)
    return output


def blank():
    return {'schema_version': 1, 'kind': 'mo2-profile-change-report', 'tool_version': VERSION,
            'complete': False, 'policy': {'encoding': 'UTF-8_optional_BOM', 'name_comparison': 'casefold_no_normalization',
            'order': 'physical_file_order', 'reordered': 'all_common_inversion_participants_by_group',
            'separator_relocated': 'common_stable_entries_across_groups', 'load_order_inferred': False},
            'limits': {'file_bytes': FILE_LIMIT, 'line_characters': LINE_LIMIT,
            'split_lines': LINE_COUNT_LIMIT, 'entries_per_input': ENTRY_LIMIT,
            'metadata_accounting_bytes': METADATA_LIMIT, 'report_bytes': REPORT_LIMIT},
            'before': None, 'after': None, 'input_bytes_equal': None, 'semantic_changes': None,
            'changes': {group: empty_changes(group) for group in GROUPS}, 'summary': {}, 'errors': []}


def inspect(args):
    report, target, active = blank(), None, None
    try:
        paths = [local_path(args.before), local_path(args.after)]
        target = new_output(args.output, paths)
        budget, selected, states = Budget(), [], []
        for active, path in zip(('before', 'after'), paths):
            data, info = read_file(path)
            selected.append(parse_modlist(data, budget))
            states.append((path, info))
        active = None
        changes = compare(*selected, budget)
        summary = {group: {kind: len(rows) for kind, rows in values.items()} for group, values in changes.items()}
        for active, (path, info) in zip(('before', 'after'), states):
            if identity(checked(path)) != identity(info):
                raise Failure('input_changed')
        report.update(complete=True, before=selected[0], after=selected[1], changes=changes, summary=summary,
                      input_bytes_equal=selected[0]['sha256'] == selected[1]['sha256'],
                      semantic_changes=any(count for counts in summary.values() for count in counts.values()))
    except Failure as error:
        row = {'code': error.code}
        if active:
            row['input'] = active
        if getattr(error, 'line', None) is not None:
            row['line'] = error.line
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


def parser():
    result = Parser(description=__doc__)
    result.add_argument('--version', action='version', version=VERSION)
    result.add_argument('--before', required=True, help='Explicit earlier modlist.txt file')
    result.add_argument('--after', required=True, help='Explicit later modlist.txt file')
    result.add_argument('--output', help='New JSON report; existing ordinary parent directory')
    return result


def main(argv=None):
    try:
        report, target = inspect(parser().parse_args(argv))
        write(encode(report), target)
        return (2 if report['semantic_changes'] else 0) if report['complete'] else 1
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
