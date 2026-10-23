#!/usr/bin/env python3
"""Check explicit offline mod presence, conflict and order rules. Original MIT, Python 3.12+."""
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
PATH_LIMIT, FILE_LIMIT = 1024, 2 * MIB
MOD_LIMIT, RULE_LIMIT, NODE_LIMIT, JSON_DEPTH = 10000, 10000, 20000, 8
REPORT_LIMIT, METADATA_LIMIT = 8 * MIB, 32 * MIB
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)
RULE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
TYPES = ('requires', 'conflicts', 'load_before')
RESULTS = ('satisfied', 'not_applicable', 'missing_requirement', 'active_conflict', 'load_order_violation')


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


def mod_name(value):
    if type(value) is not str or not component(value) or value != value.strip():
        raise Failure('invalid_mod_name')
    return value.casefold()


def inventory_document(data, budget):
    document = json_document(data)
    object_schema(document, ('schema_version', 'load_order'))
    version_one(document['schema_version'])
    rows = document['load_order']
    if type(rows) is not list:
        raise Failure('invalid_load_order')
    if len(rows) > MOD_LIMIT:
        raise Failure('mod_count_limit')
    names = set()
    for number, name in enumerate(rows, 1):
        key = mod_name(name)
        if key in names:
            raise Failure('duplicate_or_case_colliding_mod')
        names.add(key)
        budget.charge({'name': name, 'key': key, 'position': number})
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'load_order': rows}


def rules_document(data, budget):
    document = json_document(data)
    object_schema(document, ('schema_version', 'rules'))
    version_one(document['schema_version'])
    rows = document['rules']
    if type(rows) is not list:
        raise Failure('invalid_rule_list')
    if len(rows) > RULE_LIMIT:
        raise Failure('rule_count_limit')
    ids, semantics, nodes = set(), set(), set()
    for number, row in enumerate(rows, 1):
        try:
            object_schema(row, ('id', 'type', 'mod', 'target'))
            if type(row['id']) is not str or not RULE_ID.fullmatch(row['id']):
                raise Failure('invalid_rule_id')
            if row['id'].lower() in ids:
                raise Failure('duplicate_rule_id')
            ids.add(row['id'].lower())
            if type(row['type']) is not str or row['type'] not in TYPES:
                raise Failure('unsupported_rule_type')
            source, target = mod_name(row['mod']), mod_name(row['target'])
            nodes.update((source, target))
            if len(nodes) > NODE_LIMIT:
                raise Failure('graph_node_limit')
            pair = tuple(sorted((source, target))) if row['type'] == 'conflicts' else (source, target)
            key = (row['type'], *pair)
            if key in semantics:
                raise Failure('duplicate_rule_relation')
            semantics.add(key)
            budget.charge({'rule': row, 'relation': key})
        except Failure as error:
            error.rule = number
            raise
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'rules': rows}


def cycle_witness(members, graph):
    allowed, color = set(members), {}
    for root in members:
        if root in color:
            continue
        color[root] = 1
        stack, positions = [(root, 0, None)], {root: 0}
        while stack:
            node, index, incoming = stack[-1]
            if index == len(graph[node]):
                color[node] = 2
                positions.pop(node)
                stack.pop()
                continue
            target, rule = graph[node][index]
            stack[-1] = (node, index + 1, incoming)
            if target not in allowed:
                continue
            if color.get(target) == 1:
                start = positions[target]
                return ([frame[0] for frame in stack[start:]] + [target],
                        [frame[2] for frame in stack[start+1:]] + [rule])
            if target not in color:
                color[target] = 1
                positions[target] = len(stack)
                stack.append((target, 0, rule))
    raise Failure('graph_analysis_failed')


def catalog_cycles(rules, names, active, budget):
    cycles = []
    for kind in ('requires', 'load_before'):
        graph, reverse = {}, {}
        for row in rules:
            if row['type'] != kind:
                continue
            source, target = row['mod'].casefold(), row['target'].casefold()
            graph.setdefault(source, []).append((target, row['id']))
            graph.setdefault(target, [])
            reverse.setdefault(target, []).append(source)
            reverse.setdefault(source, [])
        for edges in graph.values():
            edges.sort()
        visited, finished = set(), []
        for root in sorted(graph):
            if root in visited:
                continue
            visited.add(root)
            stack = [(root, 0)]
            while stack:
                node, index = stack[-1]
                if index == len(graph[node]):
                    finished.append(node)
                    stack.pop()
                    continue
                stack[-1] = (node, index + 1)
                target = graph[node][index][0]
                if target not in visited:
                    visited.add(target)
                    stack.append((target, 0))
        assigned, components = set(), []
        for root in reversed(finished):
            if root in assigned:
                continue
            assigned.add(root)
            members, pending = [], [root]
            while pending:
                node = pending.pop()
                members.append(node)
                for target in reverse[node]:
                    if target not in assigned:
                        assigned.add(target)
                        pending.append(target)
            members.sort()
            if len(members) > 1 or any(target == root for target, unused in graph[root]):
                components.append(members)
        for members in sorted(components):
            member_set = set(members)
            witness, edge_ids = cycle_witness(members, graph)
            row = {'type': kind, 'members': [names[key] for key in members],
                   'active_members': [names[key] for key in members if key in active],
                   'rule_ids': sorted(rule for node in members for target, rule in graph[node] if target in member_set),
                   'witness': {'mods': [names[key] for key in witness], 'rule_ids': edge_ids}}
            budget.charge(row)
            cycles.append(row)
    return cycles


def evaluate(inventory, catalog, budget):
    positions = {name.casefold(): index for index, name in enumerate(inventory['load_order'], 1)}
    names = {name.casefold(): name for name in inventory['load_order']}
    evaluations, findings = [], []
    for rule in catalog['rules']:
        source, target = rule['mod'].casefold(), rule['target'].casefold()
        names.setdefault(source, rule['mod'])
        names.setdefault(target, rule['target'])
        first, second = positions.get(source), positions.get(target)
        if rule['type'] == 'requires':
            result = 'not_applicable' if first is None else ('satisfied' if second else 'missing_requirement')
        elif rule['type'] == 'conflicts':
            result = 'active_conflict' if first and second else 'not_applicable'
        else:
            result = 'not_applicable' if first is None or second is None else ('satisfied' if first < second else 'load_order_violation')
        row = {**rule, 'mod_position': first, 'target_position': second, 'result': result}
        budget.charge(row)
        evaluations.append(row)
        if result not in ('satisfied', 'not_applicable'):
            findings.append({'rule_id': rule['id'], 'code': result})
    cycles = catalog_cycles(catalog['rules'], names, positions, budget)
    return evaluations, findings, cycles


def blank():
    return {'schema_version': 1, 'kind': 'offline-mod-dependency-rule-checker', 'tool_version': VERSION,
            'complete': False, 'review_required': None,
            'policy': {'names': 'casefold_no_normalization', 'inventory': 'explicit_active_earliest_to_latest',
            'requires_implies_order': False, 'cycles': 'catalog_SCCs_one_witness_each',
            'compatibility_certified': False, 'installation_scanned': False},
            'limits': {'file_bytes': FILE_LIMIT, 'mods': MOD_LIMIT, 'rules': RULE_LIMIT,
            'graph_nodes_per_rule_catalog': NODE_LIMIT, 'json_depth': JSON_DEPTH,
            'metadata_accounting_bytes': METADATA_LIMIT, 'report_bytes': REPORT_LIMIT},
            'inventory': None, 'rule_catalog': None, 'evaluations': [], 'findings': [],
            'catalog_cycles': [], 'summary': {}, 'errors': []}


def inspect(args):
    report, target, active = blank(), None, None
    try:
        paths = [local_path(args.inventory), local_path(args.rules)]
        target = new_output(args.output, paths)
        budget, documents, states = Budget(), [], []
        for active, path, parse in zip(('inventory', 'rules'), paths, (inventory_document, rules_document)):
            data, info = read_file(path)
            documents.append(parse(data, budget))
            states.append((path, info))
        active = None
        evaluations, findings, cycles = evaluate(*documents, budget)
        summary = {'active_mods': len(documents[0]['load_order']), 'rules': len(evaluations),
                   'results': {result: sum(row['result'] == result for row in evaluations) for result in RESULTS},
                   'catalog_cycles': {kind: sum(row['type'] == kind for row in cycles) for kind in ('requires', 'load_before')}}
        for active, (path, info) in zip(('inventory', 'rules'), states):
            if identity(checked(path)) != identity(info):
                raise Failure('input_changed')
        report.update(complete=True, review_required=bool(findings or cycles), inventory=documents[0],
                      rule_catalog=documents[1], evaluations=evaluations, findings=findings,
                      catalog_cycles=cycles, summary=summary)
    except Failure as error:
        row = {'code': error.code}
        if active:
            row['input'] = active
        if getattr(error, 'rule', None) is not None:
            row['rule'] = error.rule
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
    result.add_argument('--inventory', required=True, help='JSON active mod names in earliest-to-latest order')
    result.add_argument('--rules', required=True, help='JSON rule catalog, schema 1')
    result.add_argument('--output', help='New JSON report; existing ordinary parent directory')
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
