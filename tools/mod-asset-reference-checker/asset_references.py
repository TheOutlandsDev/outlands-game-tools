#!/usr/bin/env python3
"""Check explicit literal LTX references against selected loose files and declarations.

Original MIT source; see ../../LICENSE. Python 3.12+, standard library only.
No archive opening, asset decoding, MO2 overlay, game execution, or network access.
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
INDEX_LIMIT, REPORT_LIMIT, METADATA_LIMIT = 8 * MIB, 8 * MIB, 16 * MIB
MAX_INDEX_PATHS, MAX_LINE, MAX_PATH, MAX_PARTS = 100000, 65536, 1024, 128
DEFAULT_LIMITS = {'max_files': 1000, 'max_file_bytes': 2 * MIB, 'max_total_bytes': 16 * MIB,
                  'max_depth': 64, 'max_references': 10000, 'max_directory_entries': 100000}
HARD_LIMITS = {'max_files': 10000, 'max_file_bytes': 16 * MIB, 'max_total_bytes': 128 * MIB,
               'max_depth': 128, 'max_references': 100000, 'max_directory_entries': 1000000}
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)
SECTION = re.compile(r'[A-Za-z_][A-Za-z0-9_.-]{0,255}\Z')
KEY = re.compile(r'[A-Za-z_$][A-Za-z0-9_.$-]{0,255}\Z')
EXTENSION = re.compile(r'\.[a-z0-9][a-z0-9_-]{0,31}\Z')
HEADER = re.compile(r'^\[([^\]]+)\]\s*(?::\s*(.+))?$')
INCLUDE = re.compile(r'^#include\s+"([^"]+)"\s*$')
NUMERIC = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')
SENTINELS = {'none', 'nil', 'null', 'false', 'true'}
EXPRESSION = re.compile(r'[{}()\[\],=+*?|<>!&%$]')
STATUSES = ('empty_reference', 'found_loose', 'listed_in_index', 'declared_in_selection',
            'unresolved_coverage', 'missing_in_declared_coverage')


class Failure(Exception):
    """Controlled codes and already validated relative context only."""
    def __init__(self, code, file=None, line=None, key=None):
        self.code, self.file, self.line, self.key = code, file, line, key
        super().__init__(code)

    def record(self):
        result = {'code': self.code}
        for name in ('file', 'line', 'key'):
            if getattr(self, name) is not None:
                result[name] = getattr(self, name)
        return result


def safe_name(value):
    return (isinstance(value, str) and 0 < len(value) <= 255 and value not in ('.', '..')
            and not value.endswith((' ', '.')) and not INVALID.search(value)
            and not DEVICE.match(value))


def relative(value, *, include=False, parent=()):
    """Normalize separators; only include paths may use contained parent traversal."""
    if (not isinstance(value, str) or not value or len(value) > MAX_PATH
            or value.startswith(('/', '\\')) or ':' in value or '\x00' in value):
        raise Failure('unsafe_relative_path')
    raw_parts = value.replace('\\', '/').split('/')
    if len(raw_parts) > MAX_PARTS or any(not part or part == '.' for part in raw_parts):
        raise Failure('unsafe_relative_path')
    parts = list(parent) if include else []
    for part in raw_parts:
        if part == '..' and include:
            if not parts:
                raise Failure('include_outside_root')
            parts.pop()
        elif not safe_name(part):
            raise Failure('unsafe_relative_path')
        else:
            parts.append(part)
    result = '/'.join(parts)
    if not result or len(result) > MAX_PATH or len(parts) > MAX_PARTS:
        raise Failure('unsafe_relative_path')
    return result


def absolute(value):
    raw = os.fspath(value)
    if (not isinstance(raw, str) or not raw or '\x00' in raw
            or raw.startswith(('\\\\', '//'))
            or re.match(r'^[A-Za-z]:(?:$|[^\\/])', raw)):
        raise Failure('invalid_local_path')
    path = Path(os.path.abspath(raw))
    if str(path).startswith(('\\\\', '//')):
        raise Failure('invalid_local_path')
    if len(str(path)) > MAX_PATH or len(path.parts) > MAX_PARTS:
        raise Failure('local_path_limit')
    if any(not safe_name(part) for part in path.parts if part != path.anchor):
        raise Failure('unsafe_path_name')
    return path


def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def checked(path):
    if len(str(path)) > MAX_PATH or len(path.parts) > MAX_PARTS:
        raise Failure('local_path_limit')
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
    info = checked(path)
    if not stat.S_ISDIR(info.st_mode):
        raise Failure('not_a_directory')
    return info


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def object_id(info):
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def within(path, root):
    source, base = str(path).casefold(), str(root).casefold().rstrip('/\\')
    return source == base or source.startswith(base + os.sep)


def read_bounded(path, limit):
    before = checked(path)
    if not stat.S_ISREG(before.st_mode):
        raise Failure('not_a_regular_file')
    if before.st_size > limit:
        raise Failure('file_byte_limit')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            if identity(os.fstat(stream.fileno())) != identity(before):
                raise Failure('input_changed')
            data = bytearray()
            while block := stream.read(min(CHUNK, limit - len(data) + 1)):
                data.extend(block)
                if len(data) > limit:
                    raise Failure('file_byte_limit')
            if (len(data) != before.st_size or identity(os.fstat(stream.fileno())) != identity(before)
                    or identity(checked(path)) != identity(before)):
                raise Failure('input_changed')
    except OSError:
        raise Failure('unreadable_file') from None
    return bytes(data), before


class Budget:
    def __init__(self):
        self.used = 0

    def charge(self, value):
        # Count canonical escaped metadata and bookkeeping, not unselected source values.
        size = 0
        for part in json.JSONEncoder(ensure_ascii=True, separators=(',', ':')).iterencode(value):
            size += len(part.encode('utf-8'))
            if self.used + size > METADATA_LIMIT:
                raise Failure('metadata_byte_limit')
        self.used += size + 64
        if self.used > METADATA_LIMIT:
            raise Failure('metadata_byte_limit')


class Directories:
    """Cache each visited directory once; never recursively enumerate asset roots."""
    def __init__(self, limit, budget):
        self.limit, self.budget, self.visited = limit, budget, 0
        self.cache, self.targets = {}, {}

    def entries(self, path):
        key = str(path).casefold()
        if key in self.cache:
            cached_path, before, unused = self.cache[key]
            if identity(directory(path)) != before:
                if object_id(directory(path)) != object_id(directory(cached_path)):
                    raise Failure('ambiguous_case_alias')
                raise Failure('input_directory_changed')
            return self.cache[key][2]
        before = directory(path)
        names = {}
        self.budget.charge(str(path))
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    self.visited += 1
                    if self.visited > self.limit:
                        raise Failure('directory_entry_limit')
                    if not safe_name(entry.name):
                        raise Failure('unsafe_directory_entry')
                    folded = entry.name.casefold()
                    if folded in names:
                        raise Failure('ambiguous_path_case')
                    self.budget.charge(entry.name)
                    names[folded] = entry.name
        except OSError:
            raise Failure('unreadable_directory') from None
        if identity(directory(path)) != identity(before):
            raise Failure('input_directory_changed')
        self.cache[key] = (path, identity(before), names)
        return names

    def find(self, root, name, *, config=False):
        parts, actual, current = name.split('/'), [], root
        for index, part in enumerate(parts):
            match = self.entries(current).get(part.casefold())
            if match is None:
                return None, False
            current = current / match
            actual.append(match)
            info = checked(current)
            if index < len(parts) - 1:
                if not stat.S_ISDIR(info.st_mode):
                    raise Failure('path_component_is_file')
            elif not stat.S_ISREG(info.st_mode):
                raise Failure('reference_target_not_file' if not config else 'config_target_not_file')
        key = str(current).casefold()
        if key in self.targets and identity(info) != self.targets[key][1]:
            raise Failure('ambiguous_case_alias')
        if key not in self.targets:
            self.budget.charge(str(current))
            self.targets[key] = (current, identity(info))
        found = '/'.join(actual)
        self.budget.charge(found)
        return (current, found, info), found != name

    def stable(self):
        for path, before, unused in self.cache.values():
            if identity(directory(path)) != before:
                raise Failure('input_directory_changed')
        for path, before in self.targets.values():
            if identity(checked(path)) != before:
                raise Failure('input_target_changed')


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Failure('duplicate_index_json_key')
        result[key] = value
    return result


def load_index(path, budget):
    data, state = read_bounded(path, INDEX_LIMIT)
    try:
        document = json.loads(data.decode('utf-8'), object_pairs_hook=strict_pairs,
                              parse_constant=lambda unused: (_ for _ in ()).throw(Failure('invalid_index_number')))
    except (UnicodeError, ValueError, RecursionError):
        raise Failure('invalid_index_json') from None
    if (not isinstance(document, dict) or set(document) != {'schema_version', 'kind', 'paths'}
            or type(document['schema_version']) is not int or document['schema_version'] != 1
            or document['kind'] != 'asset-path-index' or not isinstance(document['paths'], list)
            or len(document['paths']) > MAX_INDEX_PATHS):
        raise Failure('invalid_index_schema')
    paths, tree = {}, {}
    for value in document['paths']:
        name = relative(value)
        if name != value:
            raise Failure('noncanonical_index_path')
        folded = name.casefold()
        if folded in paths:
            raise Failure('duplicate_index_path')
        budget.charge(name)
        paths[folded] = name
        node = tree
        for part in name.split('/'):
            if None in node:
                raise Failure('index_file_directory_collision')
            key = part.casefold()
            if key in node:
                spelling, child = node[key]
                if spelling != part:
                    raise Failure('ambiguous_index_case')
            else:
                budget.charge(part)
                child = {}
                node[key] = (part, child)
            node = child
        if node:
            raise Failure('index_file_directory_collision')
        node[None] = True
    details = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'paths': len(paths)}
    return paths, details, state


def file_rule(value):
    try:
        key, equals, rest = value.partition('=')
        subdir, colon, extension = rest.rpartition(':')
        if not equals or not colon or not KEY.fullmatch(key) or not EXTENSION.fullmatch(extension):
            raise Failure('invalid_file_rule')
        subdir = relative(subdir)
        return {'key': key, 'subdir': subdir, 'extension': extension}
    except Failure:
        raise argparse.ArgumentTypeError('expected KEY=SUBDIR:.ext with portable literal names') from None


def section_key(value):
    if not KEY.fullmatch(value):
        raise argparse.ArgumentTypeError('a literal key name is required')
    return value


def positive(name):
    def parse(value):
        try:
            result = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError('positive bounded integer required') from None
        if not 1 <= result <= HARD_LIMITS[name]:
            raise argparse.ArgumentTypeError('positive bounded integer required')
        return result
    return parse


def settings(args):
    rules = args.file_rule if args.file_rule is not None else [file_rule('visual=meshes:.ogf')]
    keys = args.section_key if args.section_key is not None else ['ammo_class']
    if len(rules) > 64 or len(keys) > 64:
        raise Failure('rule_count_limit')
    names = [rule['key'] for rule in rules]
    if len(set(names)) != len(names) or len(set(keys)) != len(keys) or set(names) & set(keys):
        raise Failure('duplicate_rule_key')
    return {'file_rules': rules, 'section_keys': keys, 'encoding': args.encoding,
            'assume_complete_assets': args.assume_complete_assets,
            'assume_complete_sections': args.assume_complete_sections}


def blank_report(policy=None, limits=None):
    return {'schema_version': 1, 'kind': 'mod-asset-reference-checker', 'tool_version': VERSION,
            'complete': False, 'policy': {} if policy is None else policy,
            'limits': DEFAULT_LIMITS.copy() if limits is None else limits,
            'inputs': {'configs': [], 'index': None},
            'summary': {'config_files': 0, 'config_bytes': 0, 'file_references': 0,
                'section_references': 0, 'empty_references': 0, 'found_loose': 0,
                'listed_in_index': 0, 'declared_in_selection': 0, 'unresolved_coverage': 0,
                'missing_in_declared_coverage': 0, 'case_mismatches': 0},
            'references': [], 'context': {'includes': [], 'sections': []}, 'errors': []}


def uncomment(line):
    quoted = False
    for index, character in enumerate(line):
        if character == '"':
            quoted = not quoted
        elif character == ';' and not quoted:
            return line[:index]
    if quoted:
        raise Failure('unterminated_quote')
    return line


def literal_path(value, rule):
    if value.startswith("'") or value.endswith("'"):
        raise Failure('unsupported_file_reference')
    if value.startswith('"') or value.endswith('"'):
        if len(value) < 2 or not (value.startswith('"') and value.endswith('"')) or '"' in value[1:-1]:
            raise Failure('unsupported_file_reference')
        value = value[1:-1]
    if (not value or value.strip() != value or value.casefold() in SENTINELS
            or NUMERIC.fullmatch(value) or EXPRESSION.search(value)):
        raise Failure('unsupported_file_reference')
    name = relative(value)
    extension = Path(name).suffix
    if not extension:
        name += rule['extension']
    elif extension.casefold() != rule['extension']:
        raise Failure('unsupported_file_extension')
    return relative(rule['subdir'] + '/' + name)


class Graph:
    def __init__(self, root, report, dirs, budget):
        self.root, self.report, self.dirs, self.budget = root, report, dirs, budget
        self.limits, self.policy = report['limits'], report['policy']
        self.rules = {rule['key']: rule for rule in self.policy['file_rules']}
        self.section_keys = set(self.policy['section_keys'])
        self.declarations, self.states, self.documents = {}, {}, {}
        self.total, self.reference_count = 0, 0

    def add_reference(self, kind, file, line, section, key, target):
        self.reference_count += 1
        if self.reference_count > self.limits['max_references']:
            raise Failure('reference_count_limit', file, line, key)
        row = {'kind': kind, 'file': file, 'line': line, 'section': section, 'key': key,
               'target': target, 'status': 'empty_reference' if target is None else 'unresolved_coverage',
               'found_case_mismatch': False}
        if kind == 'file':
            row['loose_file'] = None
        self.budget.charge(row)
        self.report['references'].append(row)

    def parse(self, relative_file, actual_path):
        if len(self.documents) >= self.limits['max_files']:
            raise Failure('config_file_count_limit', relative_file)
        remaining = self.limits['max_total_bytes'] - self.total
        if remaining < 0:
            raise Failure('config_total_byte_limit', relative_file)
        raw, before = read_bounded(actual_path, min(self.limits['max_file_bytes'], remaining))
        self.total += len(raw)
        try:
            text = raw.decode(self.policy['encoding'])
        except UnicodeError:
            raise Failure('unsupported_config_encoding', relative_file) from None
        record = {'path': relative_file, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        self.budget.charge(record)
        self.report['inputs']['configs'].append(record)
        self.documents[relative_file.casefold()] = (actual_path, identity(before))
        current, keys, includes = None, set(), []
        for number, raw_line in enumerate(io.StringIO(text, newline=None), 1):
            key = None
            if len(raw_line.rstrip('\r\n')) > MAX_LINE:
                raise Failure('line_character_limit', relative_file, number)
            if any(ord(char) < 32 and char not in '\t\r\n' for char in raw_line):
                raise Failure('unsupported_control_character', relative_file, number)
            try:
                line = uncomment(raw_line).strip()
                if not line:
                    continue
                if line.startswith('#'):
                    match = INCLUDE.fullmatch(line)
                    if match is None:
                        raise Failure('unsupported_directive')
                    target = relative(match[1], include=True, parent=tuple(relative_file.split('/')[:-1]))
                    if Path(target).suffix.casefold() not in ('.ltx', '.ini'):
                        raise Failure('unsupported_config_extension')
                    context = {'file': relative_file, 'line': number, 'target': target}
                    self.budget.charge(context)
                    self.report['context']['includes'].append(context)
                    includes.append(target)
                    continue
                if line.startswith('['):
                    match = HEADER.fullmatch(line)
                    if match is None or not SECTION.fullmatch(match[1]):
                        raise Failure('unsupported_section_header')
                    current = match[1]
                    parents = [] if match[2] is None else [item.strip() for item in match[2].split(',')]
                    if any(not SECTION.fullmatch(item) for item in parents) or len(set(parents)) != len(parents):
                        raise Failure('unsupported_parent_declaration')
                    if current in self.declarations:
                        raise Failure('duplicate_section')
                    context = {'name': current, 'file': relative_file, 'line': number, 'parents': parents}
                    self.budget.charge(context)
                    self.report['context']['sections'].append(context)
                    self.declarations[current] = context
                    keys = set()
                    continue
                key, equals, value = line.partition('=')
                key, value = key.strip(), value.strip()
                if not equals or not KEY.fullmatch(key) or current is None:
                    raise Failure('unsupported_assignment')
                if key in keys:
                    raise Failure('duplicate_key')
                keys.add(key)
                self.budget.charge(key)
                if key not in self.rules and key not in self.section_keys:
                    continue
                kind = 'file' if key in self.rules else 'section'
                if value in ('', '""'):
                    self.add_reference(kind, relative_file, number, current, key, None)
                elif kind == 'file':
                    self.add_reference(kind, relative_file, number, current, key, literal_path(value, self.rules[key]))
                else:
                    targets = [part.strip() for part in value.split(',')]
                    if any(not SECTION.fullmatch(item) or item.casefold() in SENTINELS
                           or NUMERIC.fullmatch(item) for item in targets):
                        raise Failure('unsupported_section_reference')
                    for target in targets:
                        self.add_reference(kind, relative_file, number, current, key, target)
            except Failure as error:
                raise Failure(error.code, relative_file, number,
                              key if isinstance(key, str) and KEY.fullmatch(key) else None) from None
        return includes

    def scan(self, entries):
        pending = [('enter', name, 1) for name in reversed(entries)]
        while pending:
            operation, name, depth = pending.pop()
            if operation == 'leave':
                self.states[name.casefold()] = 2
                continue
            if depth > self.limits['max_depth']:
                raise Failure('include_depth_limit', name)
            result, mismatch = self.dirs.find(self.root, name, config=True)
            if result is None:
                raise Failure('missing_config_file', name)
            path, actual, unused = result
            state = self.states.get(actual.casefold(), 0)
            if mismatch:
                self.report['summary']['case_mismatches'] += 1
            if state == 1:
                raise Failure('include_cycle', actual)
            if state == 2:
                continue
            self.states[actual.casefold()] = 1
            includes = self.parse(actual, path)
            pending.append(('leave', actual, depth))
            pending.extend(('enter', child, depth + 1) for child in reversed(includes))

    def stable(self):
        for path, before in self.documents.values():
            if identity(checked(path)) != before:
                raise Failure('config_changed')


def resolve(report, graph, asset_root, dirs, index):
    for row in report['references']:
        if row['target'] is None:
            continue
        if row['kind'] == 'section':
            if row['target'] in graph.declarations:
                row['status'] = 'declared_in_selection'
            elif report['policy']['assume_complete_sections']:
                row['status'] = 'missing_in_declared_coverage'
        else:
            found, mismatch = dirs.find(asset_root, row['target'])
            if found is not None:
                unused, actual, info = found
                row['status'] = 'found_loose'
                row['loose_file'] = {'path': actual, 'bytes': info.st_size}
                row['found_case_mismatch'] = mismatch
            elif row['target'].casefold() in index:
                row['status'] = 'listed_in_index'
                row['found_case_mismatch'] = index[row['target'].casefold()] != row['target']
            elif report['policy']['assume_complete_assets']:
                row['status'] = 'missing_in_declared_coverage'


def summarize(report):
    summary = report['summary']
    summary['config_files'] = len(report['inputs']['configs'])
    summary['config_bytes'] = sum(record['bytes'] for record in report['inputs']['configs'])
    for row in report['references']:
        summary['file_references' if row['kind'] == 'file' else 'section_references'] += 1
        if row['status'] == 'empty_reference':
            summary['empty_references'] += 1
        else:
            summary[row['status']] += 1
        summary['case_mismatches'] += int(row['found_case_mismatch'])


def destination(value, roots, index):
    if value is None:
        return None
    path = absolute(value)
    directory(path.parent)
    if any(within(path, root) for root in roots) or (index is not None and str(path).casefold() == str(index).casefold()):
        raise Failure('output_overlaps_input')
    try:
        path.lstat()
    except FileNotFoundError:
        return path
    except OSError:
        raise Failure('unsafe_output') from None
    raise Failure('output_exists')


def inspect(args):
    report, target = blank_report(), None
    try:
        policy = settings(args)
        limits = {name: getattr(args, name) for name in DEFAULT_LIMITS}
        report = blank_report(policy, limits)
        config_root, asset_root = absolute(args.config_root), absolute(args.asset_root)
        directory(config_root)
        directory(asset_root)
        if (str(config_root).casefold() == str(asset_root).casefold()
                and object_id(directory(config_root)) != object_id(directory(asset_root))):
            raise Failure('ambiguous_case_alias')
        entries, entry_seen = [], set()
        if len(args.entry) > limits['max_files']:
            raise Failure('config_file_count_limit')
        for item in args.entry:
            name = relative(item)
            if Path(name).suffix.casefold() not in ('.ltx', '.ini'):
                raise Failure('unsupported_config_extension')
            if name.casefold() in entry_seen:
                raise Failure('duplicate_entry_path')
            entry_seen.add(name.casefold())
            entries.append(name)
        index_path = absolute(args.packed_index) if args.packed_index else None
        target = destination(args.output, [config_root, asset_root], index_path)
        budget = Budget()
        dirs = Directories(limits['max_directory_entries'], budget)
        index, index_state = {}, None
        if index_path is not None:
            index, report['inputs']['index'], index_state = load_index(index_path, budget)
        graph = Graph(config_root, report, dirs, budget)
        graph.scan(entries)
        resolve(report, graph, asset_root, dirs, index)
        graph.stable()
        dirs.stable()
        if index_path is not None and identity(checked(index_path)) != identity(index_state):
            raise Failure('index_changed')
        report['complete'] = True
    except Failure as error:
        report['errors'].append(error.record())
    summarize(report)
    return report, target


def encode_report(report):
    output = bytearray()
    for piece in json.JSONEncoder(ensure_ascii=True, indent=2).iterencode(report):
        data = piece.encode('utf-8')
        if len(output) + len(data) + 1 > REPORT_LIMIT:
            raise Failure('report_byte_limit')
        output.extend(data)
    output.extend(b'\n')
    return output


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


def parser():
    result = Parser(description=__doc__)
    result.add_argument('--version', action='version', version=VERSION)
    result.add_argument('--config-root', required=True, help='Existing local root containing explicitly selected LTX/INI files')
    result.add_argument('--entry', required=True, action='append', help='Repeat for canonical config-root-relative .ltx/.ini entry files')
    result.add_argument('--asset-root', required=True, help='Existing local virtual asset root; default visual targets are under meshes/')
    result.add_argument('--file-rule', action='append', type=file_rule, help='Repeat KEY=SUBDIR:.ext; any rules replace default visual=meshes:.ogf')
    result.add_argument('--section-key', action='append', type=section_key, help='Repeat literal comma-list property keys; replaces default ammo_class')
    result.add_argument('--packed-index', help='Optional bounded asset-path-index JSON; a data claim, never archive validation')
    result.add_argument('--assume-complete-assets', action='store_true', help='Declare selected loose root/index complete for this check; unresolved file paths become declared-coverage findings')
    result.add_argument('--assume-complete-sections', action='store_true', help='Declare selected config graph complete for section references')
    result.add_argument('--encoding', choices=('utf-8-sig', 'cp1251'), default='utf-8-sig', help='Strict config decoding (default utf-8-sig); no automatic fallback')
    result.add_argument('--output', help='New JSON report outside input roots and separate from index; existing files refused')
    descriptions = {'max_files': 'Unique selected/include config files', 'max_file_bytes': 'Bytes per config file',
        'max_total_bytes': 'Combined config bytes', 'max_depth': 'Include depth with each entry counted as 1',
        'max_references': 'File/section references, including empty selections',
        'max_directory_entries': 'Global entries across cached visited directories'}
    for name, default in DEFAULT_LIMITS.items():
        result.add_argument('--' + name.replace('_', '-'), type=positive(name), default=default,
                            help=f'{descriptions[name]} (default {default}; hard maximum {HARD_LIMITS[name]})')
    return result


def main(argv=None):
    report = blank_report()
    try:
        args = parser().parse_args(argv)
        report, target = inspect(args)
        write_report(encode_report(report), target)
        if not report['complete']:
            return 1
        summary = report['summary']
        return 2 if any(summary[key] for key in ('unresolved_coverage', 'missing_in_declared_coverage', 'case_mismatches')) else 0
    except (Failure, OSError, ValueError, OverflowError, RecursionError) as error:
        fallback = blank_report(report['policy'], report['limits'])
        fallback['errors'].append(error.record() if isinstance(error, Failure) else {'code': 'operation_failed'})
        try:
            sys.stdout.write(encode_report(fallback).decode('utf-8'))
        except (Failure, OSError, ValueError):
            pass
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
