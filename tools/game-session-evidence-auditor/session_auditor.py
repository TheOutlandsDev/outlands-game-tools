#!/usr/bin/env python3
"""Audit explicitly selected session evidence and generic receipts. Original MIT, Python 3.12+."""
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
MIB = 1024 * 1024
PATH_LIMIT, FILE_LIMIT, JSON_DEPTH = 1024, 2 * MIB, 8
CAPTURE_LIMIT, RECEIPT_LIMIT, TOTAL_LIMIT = 256 * MIB, 64 * 1024, 1024 * MIB
CAPTURE_COUNT, DEPTH_LIMIT, CHUNK = 1000, 32, MIB
REPORT_LIMIT, METADATA_LIMIT = 8 * MIB, 32 * MIB
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)
LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
STAMP = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z')


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


def reject_constant(unused):
    raise Failure('invalid_json_number')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Failure('duplicate_json_key')
        result[key] = value
    return result


def json_document(data):
    if len(data) > FILE_LIMIT:
        raise Failure('file_byte_limit')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError:
        raise Failure('unsupported_encoding') from None
    # Bound nesting before invoking the standard decoder; brackets in strings do not count.
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > JSON_DEPTH:
                raise Failure('json_depth_limit')
        elif char in ']}':
            depth -= 1
            if depth < 0:
                raise Failure('invalid_json')
    try:
        return json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, RecursionError):
        raise Failure('invalid_json') from None


def object_schema(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise Failure('invalid_or_unknown_fields')


def version_one(value):
    if type(value) is not int or value != 1:
        raise Failure('unsupported_schema_version')


def label(value):
    if type(value) is not str or not LABEL.fullmatch(value):
        raise Failure('invalid_label')


def relative_path(value):
    if type(value) is not str or not value.isascii() or not 1 <= len(value) <= PATH_LIMIT:
        raise Failure('unsafe_relative_path')
    parts = value.split('/')
    if len(parts) > DEPTH_LIMIT or any(not component(part) for part in parts):
        raise Failure('unsafe_relative_path')
    return parts


def manifest_document(data, budget):
    document = json_document(data)
    object_schema(document, ('schema_version', 'session_id', 'captures', 'receipts'))
    version_one(document['schema_version'])
    label(document['session_id'])
    if type(document['captures']) is not list:
        raise Failure('invalid_capture_list')
    if len(document['captures']) > CAPTURE_COUNT:
        raise Failure('capture_count_limit')
    object_schema(document['receipts'], ('launch', 'exit'))
    selected = [(row, 'capture') for row in document['captures']]
    selected += [(document['receipts'][role], role) for role in ('launch', 'exit') if document['receipts'][role] is not None]
    paths, total = set(), 0
    for number, (row, role) in enumerate(selected, 1):
        try:
            object_schema(row, ('path', 'bytes', 'sha256'))
            relative_path(row['path'])
            key = row['path'].lower()
            if key in paths:
                raise Failure('duplicate_or_case_colliding_path')
            paths.add(key)
            if type(row['bytes']) is not int or row['bytes'] < 0:
                raise Failure('invalid_declared_size')
            maximum = CAPTURE_LIMIT if role == 'capture' else RECEIPT_LIMIT
            if row['bytes'] > maximum:
                raise Failure('declared_file_byte_limit')
            total += row['bytes']
            if total > TOTAL_LIMIT:
                raise Failure('declared_total_byte_limit')
            if type(row['sha256']) is not str or not DIGEST.fullmatch(row['sha256']):
                raise Failure('invalid_sha256')
            budget.charge({'reference': row, 'role': role, 'key': key})
        except Failure as error:
            error.reference = number
            raise
    for path in paths:
        parts = path.split('/')
        if any('/'.join(parts[:index]) in paths for index in range(1, len(parts))):
            raise Failure('file_directory_path_collision')
    return document, selected


def receipt_document(data, role):
    if len(data) > RECEIPT_LIMIT:
        raise Failure('receipt_byte_limit')
    document = json_document(data)
    keys = ['schema_version', 'session_id', 'event', 'process_id', 'executable_id', 'timestamp_utc']
    if role == 'exit':
        keys.append('exit_code')
    object_schema(document, keys)
    version_one(document['schema_version'])
    label(document['session_id'])
    label(document['executable_id'])
    if document['event'] != role:
        raise Failure('unexpected_receipt_event')
    if type(document['process_id']) is not int or not 1 <= document['process_id'] <= 0x7FFFFFFF:
        raise Failure('invalid_process_id')
    stamp = document['timestamp_utc']
    if type(stamp) is not str or not STAMP.fullmatch(stamp):
        raise Failure('invalid_timestamp')
    try:
        instant = datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError:
        raise Failure('invalid_timestamp') from None
    if role == 'exit' and (type(document['exit_code']) is not int or not -0x80000000 <= document['exit_code'] <= 0xFFFFFFFF):
        raise Failure('invalid_exit_code')
    return document, instant


def observed(path):
    """A missing path is evidence; links, unsupported objects and I/O failures are refusals."""
    try:
        for part in [*reversed(path.parents), path]:
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise Failure('linked_path')
            if part != path and not stat.S_ISDIR(info.st_mode):
                raise Failure('invalid_parent')
        return info
    except FileNotFoundError:
        return None
    except OSError:
        raise Failure('unreadable_evidence') from None


def hash_evidence(path, reference, role, counter):
    info = observed(path)
    result = {'path': reference['path'], 'role': role, 'status': 'missing',
              'declared_bytes': reference['bytes'], 'expected_sha256': reference['sha256'],
              'actual_bytes': None, 'actual_sha256': None, 'size_matches': None, 'hash_matches': None}
    if info is None:
        return result, None, None
    if not stat.S_ISREG(info.st_mode):
        raise Failure('not_a_regular_file')
    maximum = CAPTURE_LIMIT if role == 'capture' else RECEIPT_LIMIT
    if info.st_size > maximum:
        raise Failure('evidence_file_byte_limit')
    if counter[0] + info.st_size > TOTAL_LIMIT:
        raise Failure('evidence_total_byte_limit')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    digest, chunks, total = hashlib.sha256(), [], 0
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(info):
            raise Failure('input_changed')
        while True:
            block = stream.read(min(CHUNK, maximum - total + 1))
            if not block:
                break
            total += len(block)
            counter[0] += len(block)
            if total > maximum or counter[0] > TOTAL_LIMIT:
                raise Failure('evidence_byte_limit_during_read')
            digest.update(block)
            if role != 'capture':
                chunks.append(block)
        if total != info.st_size or identity(os.fstat(stream.fileno())) != identity(info):
            raise Failure('input_changed')
    after = observed(path)
    if after is None or identity(after) != identity(info):
        raise Failure('input_changed')
    result.update(actual_bytes=total, actual_sha256=digest.hexdigest(),
                  size_matches=total == reference['bytes'], hash_matches=digest.hexdigest() == reference['sha256'])
    result['status'] = 'verified' if result['size_matches'] and result['hash_matches'] else 'changed'
    return result, b''.join(chunks) if role != 'capture' else None, info


def within(path, root):
    left, right = str(path).casefold(), str(root).casefold()
    return left == right or left.startswith(right.rstrip('/\\') + os.sep)


def session_summary():
    return {'launch_status': 'missing', 'exit_status': 'missing',
            'launch_session_matches': None, 'exit_session_matches': None,
            'same_process': None, 'same_executable': None, 'duration_seconds': None,
            'receipt_pair_consistent': None, 'exit_code': None}


def blank():
    return {'schema_version': 1, 'kind': 'game-session-evidence-auditor', 'tool_version': VERSION,
            'complete': False, 'review_required': None, 'session_id': None, 'manifest': None,
            'policy': {'selection': 'explicit_manifest_only', 'unlisted_files_inspected': False,
            'receipt_format': 'original_generic_schema_1', 'pid_executable_timestamps_exported': False,
            'authenticity_or_gameplay_attested': False},
            'limits': {'manifest_bytes': FILE_LIMIT, 'receipt_bytes': RECEIPT_LIMIT,
            'capture_bytes': CAPTURE_LIMIT, 'total_evidence_bytes': TOTAL_LIMIT, 'captures': CAPTURE_COUNT,
            'relative_path_characters': PATH_LIMIT, 'relative_path_components': DEPTH_LIMIT,
            'json_depth': JSON_DEPTH, 'hash_chunk_bytes': CHUNK,
            'metadata_accounting_bytes': METADATA_LIMIT, 'report_bytes': REPORT_LIMIT},
            'files': [], 'session': None, 'summary': {}, 'findings': [], 'errors': []}


def inspect(args):
    report, target = blank(), None
    try:
        root, manifest_path = local_path(args.root), local_path(args.manifest)
        if not stat.S_ISDIR(checked(root).st_mode):
            raise Failure('invalid_evidence_root')
        candidate = new_output(args.output, [manifest_path])
        if candidate is not None and within(candidate, root):
            raise Failure('output_inside_evidence_root')
        target = candidate
        budget, states, counter = Budget(), [], [0]
        data, manifest_info = read_file(manifest_path)
        document, selected = manifest_document(data, budget)
        files, findings, receipts, session = [], [], {}, session_summary()
        if not document['captures']:
            findings.append({'code': 'no_captures'})
        for role in ('launch', 'exit'):
            if document['receipts'][role] is None:
                findings.append({'code': 'missing_receipt', 'receipt': role})
        for reference, role in selected:
            path = root.joinpath(*relative_path(reference['path']))
            if str(path).casefold() == str(manifest_path).casefold():
                raise Failure('manifest_overlaps_evidence')
            row, content, info = hash_evidence(path, reference, role, counter)
            budget.charge(row)
            files.append(row)
            states.append((path, info))
            if row['status'] == 'missing':
                findings.append({'code': 'missing_file', 'path': reference['path'], 'role': role})
            else:
                if not row['size_matches']:
                    findings.append({'code': 'size_mismatch', 'path': reference['path'], 'role': role})
                if not row['hash_matches']:
                    findings.append({'code': 'hash_mismatch', 'path': reference['path'], 'role': role})
            if role == 'capture':
                continue
            if row['status'] != 'verified':
                session[role + '_status'] = 'missing' if row['status'] == 'missing' else 'unverified'
                continue
            try:
                receipt, instant = receipt_document(content, role)
                receipts[role] = (receipt, instant)
                session[role + '_status'] = 'valid'
                matches = receipt['session_id'] == document['session_id']
                session[role + '_session_matches'] = matches
                if not matches:
                    findings.append({'code': 'session_id_mismatch', 'receipt': role})
            except Failure as error:
                if error.code in ('file_byte_limit', 'receipt_byte_limit', 'json_depth_limit'):
                    raise
                session[role + '_status'] = 'invalid'
                findings.append({'code': 'invalid_receipt', 'receipt': role, 'reason': error.code})
        if 'exit' in receipts:
            session['exit_code'] = receipts['exit'][0]['exit_code']
            if session['exit_code'] != 0:
                findings.append({'code': 'nonzero_exit_code'})
        if 'launch' in receipts and 'exit' in receipts:
            launch, launch_time = receipts['launch']
            exit_receipt, exit_time = receipts['exit']
            session.update(same_process=launch['process_id'] == exit_receipt['process_id'],
                           same_executable=launch['executable_id'] == exit_receipt['executable_id'],
                           duration_seconds=int((exit_time - launch_time).total_seconds()))
            for field, code in (('same_process', 'process_id_mismatch'), ('same_executable', 'executable_id_mismatch')):
                if not session[field]:
                    findings.append({'code': code})
            if session['duration_seconds'] < 0:
                findings.append({'code': 'exit_before_launch'})
            session['receipt_pair_consistent'] = all((session['launch_session_matches'], session['exit_session_matches'],
                                                      session['same_process'], session['same_executable'],
                                                      session['duration_seconds'] >= 0))
        if identity(checked(manifest_path)) != identity(manifest_info):
            raise Failure('input_changed')
        for path, before in states:
            after = observed(path)
            if (before is None) != (after is None) or (before is not None and identity(before) != identity(after)):
                raise Failure('input_changed')
        report.update(complete=True, review_required=bool(findings), session_id=document['session_id'],
                      manifest={'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()},
                      files=files, session=session, findings=findings,
                      summary={'selected_files': len(files), 'captures': len(document['captures']),
                               'verified_files': sum(row['status'] == 'verified' for row in files),
                               'changed_files': sum(row['status'] == 'changed' for row in files),
                               'missing_files': sum(row['status'] == 'missing' for row in files),
                               'evidence_bytes_read': counter[0], 'findings': len(findings)})
    except Failure as error:
        row = {'code': error.code}
        if getattr(error, 'reference', None) is not None:
            row['reference'] = error.reference
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
    result.add_argument('--root', required=True, help='Ordinary local evidence folder; only manifest references are read')
    result.add_argument('--manifest', required=True, help='Explicit JSON manifest, original schema 1')
    result.add_argument('--output', help='New JSON report outside evidence root, existing ordinary parent')
    result.add_argument('--version', action='version', version=VERSION)
    return result


def main(argv=None):
    try:
        report, target = inspect(parser().parse_args(argv))
        write(encode(report), target)
        return (2 if report['review_required'] else 0) if report['complete'] else 1
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
