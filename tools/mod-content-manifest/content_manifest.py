#!/usr/bin/env python3
"""Read-only, bounded loose-file manifests and strict manifest comparisons.

Original MIT source; see ../../LICENSE. Python 3.12+, standard library only.
No game discovery, archive extraction, file repair, playback, or network access.
"""
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
CHUNK = 1024 * 1024
MAX_MANIFEST = 32 * CHUNK
MAX_MODLIST = 2 * CHUNK
MAX_DEPTH = 128
DEFAULT_FILE = 1024 * CHUNK
DEFAULT_TOTAL = 8 * 1024 * CHUNK
DEFAULT_FILES = 100000
DEFAULT_ENTRIES = 200000
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)
EXTENSION = re.compile(r'\.[a-z0-9][a-z0-9_-]{0,31}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')
EXCLUDED_DIRS = sorted({'.agents', '.aws', '.cache', '.codex', '.git', '.ssh', '.venv',
    '__pycache__', 'backup', 'backups', 'cache', 'caches', 'crash_reports', 'crashlogs',
    'dumps', 'logs', 'node_modules', 'profiles', 'saved games', 'savedgames', 'savegames',
    'saves', 'screenshots', 'temp', 'tmp'})
EXCLUDED_FILES = sorted({'.env', '.env.*', '.git-credentials', '.netrc', 'authorized_keys',
    'credentials', 'credentials.json', 'id_dsa', 'id_ecdsa', 'id_ed25519', 'id_rsa',
    'known_hosts', 'secrets.json'})
EXCLUDED_SUFFIXES = ['.key', '.p12', '.pem', '.pfx']


class Failure(Exception):
    """Sanitized failure: never store an operating-system exception or source text."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def safe_name(name):
    return (isinstance(name, str) and 0 < len(name) <= 255 and name not in ('.', '..')
            and not name.endswith((' ', '.')) and not INVALID.search(name)
            and not DEVICE.match(name))


def relative_path(value):
    return (isinstance(value, str) and 0 < len(value) <= 32767
            and value.count('/') < MAX_DEPTH
            and all(safe_name(part) for part in value.split('/')))


def absolute(value):
    raw = os.fspath(value)
    if (not isinstance(raw, str) or not raw or '\x00' in raw
            or raw.startswith(('\\\\', '//'))
            or re.match(r'^[A-Za-z]:(?:$|[^\\/])', raw)):
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
    info = checked(path)
    if not stat.S_ISDIR(info.st_mode):
        raise Failure('not_a_directory')
    return info


def within(path, root):
    a, b = str(path).casefold(), str(root).casefold().rstrip('/\\')
    return a == b or a.startswith(b + os.sep)


def same_path(a, b):
    return str(a).casefold() == str(b).casefold()


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def readonly(path, limit):
    before = checked(path)
    if not stat.S_ISREG(before.st_mode):
        raise Failure('not_a_regular_file')
    if before.st_size > limit:
        raise Failure('file_byte_limit')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        stream = os.fdopen(os.open(path, flags), 'rb')
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


def read_bounded(path, limit):
    with readonly(path, limit) as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise Failure('file_byte_limit')
        unchanged(path, stream, before)
        if len(raw) != before.st_size:
            raise Failure('input_changed')
    return raw, identity(before)


def digest(path, limit, expected):
    with readonly(path, limit) as stream:
        before = os.fstat(stream.fileno())
        if identity(before) != expected:
            raise Failure('input_changed')
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


def integer(value):
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('must be a positive bounded integer') from None
    if result < 1 or result >= sys.maxsize:
        raise argparse.ArgumentTypeError('must be a positive bounded integer')
    return result


def extension(value):
    value = value.lower()
    if not EXTENSION.fullmatch(value):
        raise argparse.ArgumentTypeError('extensions must be simple suffixes such as .ltx')
    return value


def selection(mode, extensions):
    return {'mode': mode, 'extensions': sorted(set(extensions or [])),
            'excluded_directories': EXCLUDED_DIRS.copy(),
            'excluded_files': EXCLUDED_FILES.copy(),
            'excluded_suffixes': EXCLUDED_SUFFIXES.copy()}


def excluded(name, is_directory):
    folded = name.casefold()
    if is_directory:
        return folded in EXCLUDED_DIRS
    return (folded in EXCLUDED_FILES or folded.startswith('.env.')
            or Path(folded).suffix in EXCLUDED_SUFFIXES)


def blank_manifest(policy, limits):
    return {'schema_version': 1, 'kind': 'mod-content-manifest', 'tool_version': VERSION,
            'complete': False, 'hash_algorithm': 'sha256', 'selection': policy,
            'limits': limits, 'providers': [], 'files': [], 'file_conflicts': [],
            'summary': {'files': 0, 'bytes': 0, 'conflicts': 0, 'excluded_entries': 0},
            'errors': []}


def output_path(value, roots, input_files):
    if value is None:
        return None
    path = absolute(value)
    directory(path.parent)
    if any(within(path, root) for root in roots) or any(same_path(path, f) for f in input_files):
        raise Failure('output_overlaps_input')
    try:
        path.lstat()
    except FileNotFoundError:
        return path
    except OSError:
        raise Failure('unsafe_output') from None
    raise Failure('output_exists')


def parse_modlist(path):
    raw, stamp = read_bounded(path, MAX_MODLIST)
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError:
        raise Failure('invalid_modlist_encoding') from None
    names, seen = [], set()
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        if line[0] not in '+-' or len(line) < 2:
            raise Failure('unsupported_modlist_entry')
        name = line[1:]
        if not safe_name(name):
            raise Failure('unsafe_mod_name')
        if line[0] == '-' or name.casefold().endswith('_separator'):
            continue
        if name.casefold() in seen:
            raise Failure('duplicate_enabled_mod')
        seen.add(name.casefold())
        names.append(name)
    return names, stamp


def disjoint(roots):
    for index, root in enumerate(roots):
        for other in roots[index + 1:]:
            if within(root, other) or within(other, root):
                raise Failure('overlapping_input_roots')


def mod_roots(mods, names, max_entries):
    """Resolve actual child spelling and reject case-colliding mod directories."""
    found, visited = {}, 0
    try:
        with os.scandir(mods) as entries:
            for entry in entries:
                visited += 1
                if visited > max_entries:
                    raise Failure('entry_count_limit')
                key = entry.name.casefold()
                if key in found:
                    raise Failure('ambiguous_mod_name')
                found[key] = entry.name
    except OSError:
        raise Failure('unreadable_mods_directory') from None
    result = []
    for name in names:
        actual = found.get(name.casefold())
        if actual is None:
            raise Failure('missing_enabled_mod')
        if actual != name:
            raise Failure('ambiguous_mod_name')
        root = mods / actual
        directory(root)
        result.append(('mod:' + name, root))
    return result


def inventory(providers, policy, limits):
    """Snapshot entry identities, choose effective files, and enforce bounded work."""
    snapshot, effective, sources, spelling, kinds = {}, {}, {}, {}, {}
    entries_count = excluded_count = selected_count = metadata_bytes = 0
    mo2 = policy['mode'] == 'mo2'
    for provider, root in providers:
        pending = [(root, '')]
        while pending:
            folder, rel_folder = pending.pop()
            info = directory(folder)
            snapshot[(provider, rel_folder)] = ('directory', identity(info))
            try:
                with os.scandir(folder) as entries:
                    local_seen = set()
                    for entry in entries:
                        entries_count += 1
                        if entries_count > limits['max_entries']:
                            raise Failure('entry_count_limit')
                        name = entry.name
                        if not safe_name(name):
                            raise Failure('unsafe_entry_name')
                        folded = name.casefold()
                        if folded in local_seen:
                            raise Failure('ambiguous_path_case')
                        local_seen.add(folded)
                        path = folder / name
                        # Path.lstat is consistent with fstat identity on Windows;
                        # DirEntry.stat can expose a different cached identity.
                        info = checked(path)
                        # Reject links even if their names match privacy filters.
                        if linked(info):
                            raise Failure('linked_path')
                        is_dir = stat.S_ISDIR(info.st_mode)
                        if not is_dir and not stat.S_ISREG(info.st_mode):
                            raise Failure('unsupported_entry_type')
                        relative = (rel_folder + '/' if rel_folder else '') + name
                        if not relative_path(relative):
                            raise Failure('unsafe_relative_path')
                        # Bound retained path metadata independently of entry count.
                        metadata_bytes += len(json.dumps([provider, relative], ensure_ascii=True)) + 96
                        if metadata_bytes > MAX_MANIFEST:
                            raise Failure('metadata_byte_limit')
                        stamp = ('directory' if is_dir else 'file', identity(info))
                        snapshot[(provider, relative)] = stamp
                        if (excluded(name, is_dir) or (mo2 and
                                ((not is_dir and not rel_folder and folded == 'meta.ini')
                                 or folded.endswith('.mohidden')))):
                            excluded_count += 1
                            continue
                        if not is_dir and policy['extensions'] and Path(folded).suffix not in policy['extensions']:
                            excluded_count += 1
                            continue
                        key = relative.casefold()
                        if key in spelling and spelling[key] != relative:
                            raise Failure('ambiguous_path_case')
                        spelling[key] = relative
                        kind = 'directory' if is_dir else 'file'
                        if key in kinds and kinds[key] != kind:
                            raise Failure('conflicting_virtual_paths')
                        kinds[key] = kind
                        if is_dir:
                            pending.append((path, relative))
                            continue
                        selected_count += 1
                        if selected_count > limits['max_files']:
                            raise Failure('file_count_limit')
                        sources.setdefault(key, []).append(provider)
                        if key not in effective:
                            effective[key] = (relative, provider, path, identity(info))
            except OSError:
                raise Failure('unreadable_directory') from None
    return snapshot, effective, sources, excluded_count


def scan(args):
    mode = 'directory' if args.source_dir else 'mo2'
    policy = selection(mode, args.extensions)
    limits = {'max_file_bytes': args.max_file_bytes, 'max_total_bytes': args.max_total_bytes,
              'max_files': args.max_files, 'max_entries': args.max_entries}
    report = blank_manifest(policy, limits)
    destination = None
    try:
        if len(args.extensions or []) > 1000:
            raise Failure('extension_count_limit')
        inputs, modlist, modlist_stamp = [], None, None
        if mode == 'directory':
            if args.mods_dir or args.modlist or args.base_dir or args.overwrite_dir:
                raise Failure('conflicting_scan_inputs')
            root = absolute(args.source_dir)
            directory(root)
            providers, roots = [('source', root)], [root]
        else:
            if not args.mods_dir or not args.modlist:
                raise Failure('mods_and_modlist_required')
            mods, modlist = absolute(args.mods_dir), absolute(args.modlist)
            directory(mods)
            names, modlist_stamp = parse_modlist(modlist)
            if len(names) > args.max_entries:
                raise Failure('entry_count_limit')
            providers = mod_roots(mods, names, args.max_entries)
            roots = [mods]
            if args.overwrite_dir:
                overwrite = absolute(args.overwrite_dir)
                directory(overwrite)
                providers.insert(0, ('overwrite', overwrite))
                roots.append(overwrite)
            if args.base_dir:
                base = absolute(args.base_dir)
                directory(base)
                providers.append(('base', base))
                roots.append(base)
            disjoint(roots)
            if any(within(modlist, root) for root in roots):
                raise Failure('modlist_overlaps_input_root')
            inputs.append(modlist)
        destination = output_path(args.output, roots, inputs)
        report['providers'] = [provider for provider, _ in providers]
        before, effective, sources, omitted = inventory(providers, policy, limits)
        if not effective:
            raise Failure('no_candidate_files')
        total = 0
        for key in sorted(effective):
            relative, provider, path, stamp = effective[key]
            if stamp[2] > limits['max_file_bytes']:
                raise Failure('file_byte_limit')
            if total + stamp[2] > limits['max_total_bytes']:
                raise Failure('total_byte_limit')
            size, sha = digest(path, min(limits['max_file_bytes'], limits['max_total_bytes'] - total), stamp)
            total += size
            report['files'].append({'path': relative, 'provider': provider, 'bytes': size, 'sha256': sha})
            if len(sources[key]) > 1:
                report['file_conflicts'].append({'path': relative, 'winner': provider, 'providers': sources[key]})
        after, effective_after, sources_after, omitted_after = inventory(providers, policy, limits)
        if (before != after or effective != effective_after or sources != sources_after
                or omitted != omitted_after):
            raise Failure('input_tree_changed')
        if modlist is not None:
            _, current_stamp = read_bounded(modlist, MAX_MODLIST)
            if modlist_stamp != current_stamp:
                raise Failure('modlist_changed')
            current_providers = mod_roots(mods, names, args.max_entries)
            if current_providers != [(p, r) for p, r in providers if p.startswith('mod:')]:
                raise Failure('mods_directory_changed')
        report['summary'] = {'files': len(report['files']), 'bytes': total,
                             'conflicts': len(report['file_conflicts']), 'excluded_entries': omitted}
        report['complete'] = True
    except Failure as error:
        report['errors'].append({'code': error.code})
        report['summary']['files'] = len(report['files'])
        report['summary']['bytes'] = sum(item['bytes'] for item in report['files'])
        report['summary']['conflicts'] = len(report['file_conflicts'])
    return report, destination, 0 if report['complete'] else 1


def exact_keys(value, expected):
    return isinstance(value, dict) and set(value) == set(expected)


def nonnegative(value, maximum=sys.maxsize - 1):
    return type(value) is int and 0 <= value <= maximum


def valid_provider(value):
    return value in ('source', 'base', 'overwrite') or (
        isinstance(value, str) and value.startswith('mod:') and safe_name(value[4:]))


def validate_manifest(document):
    """Validate every imported field before comparison; no arbitrary report echo."""
    keys = {'schema_version', 'kind', 'tool_version', 'complete', 'hash_algorithm',
            'selection', 'limits', 'providers', 'files', 'file_conflicts', 'summary', 'errors'}
    if not exact_keys(document, keys):
        raise Failure('invalid_manifest_schema')
    if (type(document['schema_version']) is not int or document['schema_version'] != 1
            or document['kind'] != 'mod-content-manifest' or document['tool_version'] != VERSION
            or document['complete'] is not True or document['hash_algorithm'] != 'sha256'
            or document['errors'] != []):
        raise Failure('unsupported_or_incomplete_manifest')
    policy = document['selection']
    policy_keys = {'mode', 'extensions', 'excluded_directories', 'excluded_files', 'excluded_suffixes'}
    if not exact_keys(policy, policy_keys) or policy['mode'] not in ('directory', 'mo2'):
        raise Failure('invalid_manifest_selection')
    extensions = policy['extensions']
    if (not isinstance(extensions, list) or len(extensions) > 1000
            or any(not isinstance(value, str) or not EXTENSION.fullmatch(value) for value in extensions)
            or extensions != sorted(set(extensions)) or policy != selection(policy['mode'], extensions)):
        raise Failure('invalid_manifest_selection')
    limits = document['limits']
    if not exact_keys(limits, {'max_file_bytes', 'max_total_bytes', 'max_files', 'max_entries'}):
        raise Failure('invalid_manifest_limits')
    if any(not nonnegative(value) or value == 0 for value in limits.values()):
        raise Failure('invalid_manifest_limits')
    providers = document['providers']
    if (not isinstance(providers, list) or not providers or len(providers) > DEFAULT_ENTRIES
            or any(not valid_provider(value) for value in providers)
            or len(set(value.casefold() for value in providers)) != len(providers)):
        raise Failure('invalid_manifest_providers')
    if policy['mode'] == 'directory' and providers != ['source']:
        raise Failure('invalid_manifest_providers')
    if policy['mode'] == 'mo2':
        if ('source' in providers
                or ('overwrite' in providers and providers[0] != 'overwrite')
                or ('base' in providers and providers[-1] != 'base')):
            raise Failure('invalid_manifest_providers')
    provider_set = set(providers)
    provider_priority = {name: index for index, name in enumerate(providers)}
    records = document['files']
    if not isinstance(records, list) or not records or len(records) > limits['max_files']:
        raise Failure('invalid_manifest_files')
    file_map, total = {}, 0
    for record in records:
        if (not exact_keys(record, {'path', 'provider', 'bytes', 'sha256'})
                or not relative_path(record['path']) or not isinstance(record['provider'], str)
                or record['provider'] not in provider_set
                or not nonnegative(record['bytes'], limits['max_file_bytes'])
                or not isinstance(record['sha256'], str) or not HASH.fullmatch(record['sha256'])):
            raise Failure('invalid_manifest_file')
        key = record['path'].casefold()
        if key in file_map:
            raise Failure('duplicate_manifest_path')
        parts = record['path'].split('/')
        if (any(excluded(part, True) for part in parts[:-1]) or excluded(parts[-1], False)
                or (extensions and Path(parts[-1].lower()).suffix not in extensions)
                or (policy['mode'] == 'mo2' and (any(part.casefold().endswith('.mohidden') for part in parts)
                    or (len(parts) == 1 and parts[-1].casefold() == 'meta.ini')))):
            raise Failure('file_violates_manifest_selection')
        file_map[key] = record
        total += record['bytes']
        if total > limits['max_total_bytes']:
            raise Failure('invalid_manifest_total_bytes')
    # A component trie avoids quadratic repeated prefix joins on deep imports.
    # Retain spelling too, so differently cased parent names cannot hide ambiguity.
    tree = {}
    for record in records:
        node = tree
        for part in record['path'].split('/'):
            if None in node:
                raise Failure('conflicting_manifest_paths')
            folded = part.casefold()
            if folded in node:
                spelling, child = node[folded]
                if spelling != part:
                    raise Failure('ambiguous_manifest_case')
            else:
                child = {}
                node[folded] = (part, child)
            node = child
        if node:
            raise Failure('conflicting_manifest_paths')
        node[None] = True
    conflicts = document['file_conflicts']
    if not isinstance(conflicts, list) or len(conflicts) > len(records):
        raise Failure('invalid_manifest_conflicts')
    conflict_seen = set()
    for conflict in conflicts:
        if (not exact_keys(conflict, {'path', 'winner', 'providers'})
                or not relative_path(conflict['path'])):
            raise Failure('invalid_manifest_conflict')
        key = conflict['path'].casefold()
        order = conflict['providers']
        if (key not in file_map or key in conflict_seen or file_map[key]['path'] != conflict['path']
                or not isinstance(order, list) or len(order) < 2
                or any(not isinstance(p, str) or p not in provider_set for p in order)
                or len(set(order)) != len(order)
                or any(provider_priority[a] >= provider_priority[b] for a, b in zip(order, order[1:]))
                or conflict['winner'] != order[0] or conflict['winner'] != file_map[key]['provider']):
            raise Failure('invalid_manifest_conflict')
        conflict_seen.add(key)
    summary = document['summary']
    if (not exact_keys(summary, {'files', 'bytes', 'conflicts', 'excluded_entries'})
            or any(not nonnegative(value) for value in summary.values())
            or summary['files'] != len(records) or summary['bytes'] != total
            or summary['conflicts'] != len(conflicts)
            or summary['excluded_entries'] > limits['max_entries']):
        raise Failure('invalid_manifest_summary')
    return document


def load_manifest(path):
    raw, stamp = read_bounded(path, MAX_MANIFEST)
    def duplicate_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Failure('duplicate_json_key')
            result[key] = value
        return result
    try:
        document = json.loads(raw.decode('utf-8'), object_pairs_hook=duplicate_pairs,
                              parse_constant=lambda _: (_ for _ in ()).throw(Failure('invalid_json_number')))
    except (UnicodeError, ValueError, RecursionError):
        raise Failure('invalid_manifest_json') from None
    return validate_manifest(document), stamp


def blank_diff():
    return {'schema_version': 1, 'kind': 'mod-content-diff', 'tool_version': VERSION,
            'complete': False, 'selection': None, 'added': [], 'removed': [], 'changed': [],
            'provider_changes': [], 'summary': {'baseline_files': 0, 'candidate_files': 0,
            'identical_files': 0, 'added': 0, 'removed': 0, 'changed': 0, 'provider_changes': 0},
            'errors': []}


def metadata(record):
    return {key: record[key] for key in ('provider', 'bytes', 'sha256')}


def diff(args):
    report, destination = blank_diff(), None
    try:
        baseline_path, candidate_path = absolute(args.baseline), absolute(args.candidate)
        destination = output_path(args.output, [], [baseline_path, candidate_path])
        baseline, baseline_stamp = load_manifest(baseline_path)
        candidate, candidate_stamp = load_manifest(candidate_path)
        if baseline['selection'] != candidate['selection']:
            raise Failure('selection_mismatch')
        a = {record['path'].casefold(): record for record in baseline['files']}
        b = {record['path'].casefold(): record for record in candidate['files']}
        report['selection'] = baseline['selection']
        identical = 0
        for key in sorted(a.keys() | b.keys()):
            if key not in a:
                report['added'].append(b[key])
            elif key not in b:
                report['removed'].append(a[key])
            else:
                old, new = a[key], b[key]
                item = {'path': new['path'], 'baseline': metadata(old), 'candidate': metadata(new)}
                if old['bytes'] != new['bytes'] or old['sha256'] != new['sha256']:
                    report['changed'].append(item)
                else:
                    identical += 1
                    if old['provider'] != new['provider']:
                        report['provider_changes'].append(item)
        if (identity(checked(baseline_path)) != baseline_stamp
                or identity(checked(candidate_path)) != candidate_stamp):
            raise Failure('input_manifest_changed')
        report['summary'] = {'baseline_files': len(a), 'candidate_files': len(b),
            'identical_files': identical, 'added': len(report['added']), 'removed': len(report['removed']),
            'changed': len(report['changed']), 'provider_changes': len(report['provider_changes'])}
        report['complete'] = True
    except Failure as error:
        report['errors'].append({'code': error.code})
    different = any(report[key] for key in ('added', 'removed', 'changed', 'provider_changes'))
    return report, destination, (2 if different else 0) if report['complete'] else 1


def emit(report, destination):
    encoded = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=True, indent=2)
    for chunk in encoder.iterencode(report):
        block = chunk.encode('utf-8')
        if len(encoded) + len(block) + 1 > MAX_MANIFEST:
            raise Failure('report_byte_limit')
        encoded.extend(block)
    encoded.extend(b'\n')
    if destination is None:
        sys.stdout.write(encoded.decode('utf-8'))
        return
    directory(destination.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        with os.fdopen(os.open(destination, flags, 0o600), 'wb') as stream:
            stream.write(encoded)
    except OSError:
        raise Failure('new_output_creation_failed') from None


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse can otherwise echo private input arguments into its errors.
        raise Failure('invalid_arguments')


def parser():
    result = Parser(description=__doc__)
    result.add_argument('--version', action='version', version=VERSION)
    commands = result.add_subparsers(dest='command', required=True)
    scan_parser = commands.add_parser('scan', help='Hash selected loose content without modifying it')
    scan_parser.add_argument('--source-dir')
    scan_parser.add_argument('--mods-dir')
    scan_parser.add_argument('--modlist')
    scan_parser.add_argument('--base-dir')
    scan_parser.add_argument('--overwrite-dir')
    scan_parser.add_argument('--extensions', action='append', type=extension)
    scan_parser.add_argument('--max-file-bytes', type=integer, default=DEFAULT_FILE)
    scan_parser.add_argument('--max-total-bytes', type=integer, default=DEFAULT_TOTAL)
    scan_parser.add_argument('--max-files', type=integer, default=DEFAULT_FILES)
    scan_parser.add_argument('--max-entries', type=integer, default=DEFAULT_ENTRIES)
    scan_parser.add_argument('--output')
    diff_parser = commands.add_parser('diff', help='Compare two complete, compatible manifests')
    diff_parser.add_argument('--baseline', required=True)
    diff_parser.add_argument('--candidate', required=True)
    diff_parser.add_argument('--output')
    return result


def main(argv=None):
    report, destination = blank_diff(), None
    try:
        args = parser().parse_args(argv)
        report, destination, code = scan(args) if args.command == 'scan' else diff(args)
        emit(report, destination)
        return code
    except (Failure, OSError, ValueError, OverflowError, RecursionError) as error:
        # A failed output is reported to stdout, never attempted at a different destination.
        safe = error.code if isinstance(error, Failure) else 'operation_failed'
        fallback = blank_diff() if report['kind'] == 'mod-content-diff' else blank_manifest(report['selection'], report['limits'])
        fallback['errors'].append({'code': safe})
        try:
            sys.stdout.write(json.dumps(fallback, ensure_ascii=True, indent=2) + '\n')
        except (OSError, ValueError):
            pass
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
