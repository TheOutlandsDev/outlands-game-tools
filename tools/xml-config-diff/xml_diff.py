#!/usr/bin/env python3
"""Compare two XML configuration files without changing either input.

Original MIT source; see ../../LICENSE. Python 3.12+, standard library only.
Requires Expat 2.7.2+ for parsing. No game discovery, XML inclusion, or network.
"""
from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from xml.parsers import expat

VERSION = '1.0.0'
MIN_EXPAT = (2, 7, 2)
CHUNK = 64 * 1024
REPORT_LIMIT = 8 * 1024 * 1024
RETAINED_LIMIT = 8 * 1024 * 1024
NAME_LIMIT = 4096
DEFAULT_KEYS = ['id', 'Id', 'ID', 'name', 'Name', 'Label']
DEFAULT_LIMITS = {'max_bytes': 2 * 1024 * 1024, 'max_depth': 64, 'max_elements': 10000,
                  'max_attributes': 50000, 'max_changes': 10000}
HARD_LIMITS = {'max_bytes': 16 * 1024 * 1024, 'max_depth': 128, 'max_elements': 100000,
              'max_attributes': 200000, 'max_changes': 100000}
KINDS = ('element_added', 'element_removed', 'attribute_added', 'attribute_removed',
         'attribute_changed', 'text_changed', 'children_reordered')
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f\ud800-\udfff]')
DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\.|$)', re.I)
XML_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_.-]*\Z')


class Failure(Exception):
    """Only controlled codes, never native errors or source text."""
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
    # Use the same Path.lstat/fstat identity on Windows; omit its inconsistent ctime.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def object_id(info):
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def readonly(path, limit):
    before = checked(path)
    if not stat.S_ISREG(before.st_mode):
        raise Failure('not_a_regular_file')
    if before.st_size > limit:
        raise Failure('input_byte_limit')
    try:
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        stream = os.fdopen(os.open(path, flags), 'rb')
        if identity(os.fstat(stream.fileno())) != identity(before):
            stream.close()
            raise Failure('input_changed')
        return stream, before
    except OSError:
        raise Failure('unreadable_file') from None


def unchanged(path, stream, before):
    if (identity(os.fstat(stream.fileno())) != identity(before)
            or identity(checked(path)) != identity(before)):
        raise Failure('input_changed')


def new_output(value, inputs):
    if value is None:
        return None
    path = absolute(value)
    directory(path.parent)
    if any(str(path).casefold() == str(source).casefold() for source in inputs):
        raise Failure('output_overlaps_input')
    try:
        path.lstat()
    except FileNotFoundError:
        return path
    except OSError:
        raise Failure('unsafe_output') from None
    raise Failure('output_exists')


def bounded_integer(name):
    def parse(value):
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise argparse.ArgumentTypeError('positive bounded integer required') from None
        if not 1 <= number <= HARD_LIMITS[name]:
            raise argparse.ArgumentTypeError('positive bounded integer required')
        return number
    return parse


def key_attribute(value):
    if not isinstance(value, str) or len(value.encode('utf-8')) > NAME_LIMIT:
        raise argparse.ArgumentTypeError('invalid key attribute')
    if value.startswith('{'):
        uri, separator, local = value[1:].rpartition('}')
        if (not separator or not uri or any(ord(char) <= 32 for char in uri)
                or not XML_NAME.fullmatch(local)):
            raise argparse.ArgumentTypeError('invalid key attribute')
    elif not XML_NAME.fullmatch(value):
        raise argparse.ArgumentTypeError('invalid key attribute')
    return value


def policy(keys=None, unkeyed='reject', include_values=False):
    return {'key_attributes': list(DEFAULT_KEYS if keys is None else keys),
            'unkeyed': unkeyed, 'include_values': include_values, 'leaf_text': 'exact',
            'element_whitespace': 'ignored', 'comments': 'ignored',
            'processing_instructions': 'ignored', 'namespaces': 'expanded'}


def blank_report(settings=None, limits=None):
    summary = {'baseline_elements': 0, 'candidate_elements': 0, 'matched_elements': 0,
               'changes': 0, **{kind: 0 for kind in KINDS}}
    return {'schema_version': 1, 'kind': 'xml-config-diff', 'tool_version': VERSION,
            'complete': False, 'policy': policy() if settings is None else settings,
            'limits': DEFAULT_LIMITS.copy() if limits is None else limits,
            'inputs': {'baseline': None, 'candidate': None}, 'summary': summary,
            'changes': [], 'errors': []}


class Node:
    """Retain parent references, not a copied full locator for every XML node."""
    __slots__ = ('tag', 'attrs', 'children', 'parts', 'text', 'parent', 'occurrence',
                 'key_attribute', 'match_id', 'subtree_elements', 'child_counts')
    def __init__(self, tag, attrs, parent, occurrence, keys, unkeyed):
        self.tag, self.attrs, self.parent, self.occurrence = tag, attrs, parent, occurrence
        self.children, self.parts, self.text, self.child_counts = [], [], '', {}
        self.key_attribute = next((name for name in keys if name in attrs), None)
        if self.key_attribute is not None:
            self.match_id = ('key', tag, self.key_attribute, attrs[self.key_attribute])
        elif unkeyed == 'ordinal':
            self.match_id = ('ordinal', tag, occurrence)
        else:
            self.match_id = ('singleton', tag)
        self.subtree_elements = 1


class Reader:
    def __init__(self, settings, limits):
        self.settings, self.limits = settings, limits
        self.stack, self.root = [], None
        self.elements = self.attributes = self.retained = 0
        self.parser = expat.ParserCreate(namespace_separator='\x1f')
        self.parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
        self.parser.UseForeignDTD(False)
        self.parser.StartElementHandler = self.start
        self.parser.EndElementHandler = self.end
        self.parser.CharacterDataHandler = self.characters
        self.parser.StartDoctypeDeclHandler = self.forbidden_doctype
        self.parser.EntityDeclHandler = self.forbidden_entity
        self.parser.ExternalEntityRefHandler = self.forbidden_entity
        self.parser.XmlDeclHandler = self.declaration

    def charge(self, value):
        self.retained += len(value.encode('utf-8'))
        if self.retained > RETAINED_LIMIT:
            raise Failure('retained_metadata_limit')

    def expanded(self, value):
        if '\x1f' in value:
            namespace, local = value.split('\x1f', 1)
            value = '{' + namespace + '}' + local
        if len(value.encode('utf-8')) > NAME_LIMIT:
            raise Failure('expanded_name_limit')
        self.charge(value)
        return value

    @staticmethod
    def forbidden_doctype(*unused):
        raise Failure('unsupported_doctype')

    @staticmethod
    def forbidden_entity(*unused):
        raise Failure('unsupported_entity')

    @staticmethod
    def declaration(version, encoding, standalone):
        if version != '1.0':
            raise Failure('unsupported_xml_version')
        if encoding is not None and encoding.lower() not in ('utf-8', 'utf8'):
            raise Failure('unsupported_xml_encoding')

    def start(self, tag, attributes):
        self.elements += 1
        self.attributes += len(attributes)
        if self.elements > self.limits['max_elements']:
            raise Failure('element_count_limit')
        if self.attributes > self.limits['max_attributes']:
            raise Failure('attribute_count_limit')
        if len(self.stack) + 1 > self.limits['max_depth']:
            raise Failure('depth_limit')
        tag = self.expanded(tag)
        if tag.startswith('{http://www.w3.org/2001/XInclude}'):
            raise Failure('unsupported_xinclude')
        attrs = {}
        for name, value in attributes.items():
            name = self.expanded(name)
            self.charge(value)
            attrs[name] = value
        if attrs.get('{http://www.w3.org/XML/1998/namespace}space', 'default') != 'default':
            # Whitespace in preserve scopes is meaningful even around child elements.
            raise Failure('unsupported_xml_space')
        parent = self.stack[-1] if self.stack else None
        occurrence = 1
        if parent is not None:
            if any(part.strip() for part in parent.parts):
                raise Failure('unsupported_mixed_content')
            parent.parts.clear()
            occurrence = parent.child_counts.get(tag, 0) + 1
            parent.child_counts[tag] = occurrence
        node = Node(tag, attrs, parent, occurrence, self.settings['key_attributes'], self.settings['unkeyed'])
        if parent is not None:
            parent.children.append(node)
        else:
            self.root = node
        self.stack.append(node)

    def characters(self, value):
        if not self.stack:
            return
        node = self.stack[-1]
        if node.children:
            if value.strip():
                raise Failure('unsupported_mixed_content')
            return
        self.charge(value)
        node.parts.append(value)

    def end(self, unused):
        node = self.stack.pop()
        node.text = ''.join(node.parts) if not node.children else ''
        node.parts.clear()
        node.child_counts.clear()
        seen = set()
        for child in node.children:
            if child.match_id in seen:
                if child.key_attribute is not None:
                    raise Failure('duplicate_keyed_siblings')
                raise Failure('ambiguous_unkeyed_siblings')
            seen.add(child.match_id)
            node.subtree_elements += child.subtree_elements


def read_xml(path, settings, limits):
    if tuple(expat.version_info) < MIN_EXPAT:
        raise Failure('unsupported_expat_version')
    reader = Reader(settings, limits)
    digest, count = hashlib.sha256(), 0
    decoder = codecs.getincrementaldecoder('utf-8')('strict')
    stream, before = readonly(path, limits['max_bytes'])
    try:
        with stream:
            while block := stream.read(min(CHUNK, limits['max_bytes'] - count + 1)):
                count += len(block)
                if count > limits['max_bytes']:
                    raise Failure('input_byte_limit')
                # Expat otherwise autodetects BOM-less UTF-16, whose zero bytes
                # are valid UTF-8 code points but forbidden in UTF-8 XML itself.
                if b'\0' in block:
                    raise Failure('unsupported_xml_encoding')
                decoder.decode(block)
                digest.update(block)
                reader.parser.Parse(block, False)
            decoder.decode(b'', final=True)
            reader.parser.Parse(b'', True)
            unchanged(path, stream, before)
            if count != before.st_size:
                raise Failure('input_changed')
    except UnicodeError:
        raise Failure('unsupported_xml_encoding') from None
    except expat.ExpatError:
        raise Failure('invalid_xml') from None
    if reader.root is None:
        raise Failure('invalid_xml')
    return reader.root, {'bytes': count, 'sha256': digest.hexdigest()}, before


def locator(node):
    if node is None:
        return None
    result = []
    while node is not None:
        result.append({'tag': node.tag, 'occurrence': node.occurrence})
        node = node.parent
    result.reverse()
    return result


def value_record(value, settings):
    if value is None:
        return None
    record = {'characters': len(value), 'sha256': hashlib.sha256(value.encode('utf-8')).hexdigest()}
    if settings['include_values']:
        record['value'] = value
    return record


def json_size(value, limit):
    count = 0
    for piece in json.JSONEncoder(ensure_ascii=True, separators=(',', ':')).iterencode(value):
        count += len(piece.encode('utf-8'))
        if count > limit:
            raise Failure('report_byte_limit')
    return count


class Comparison:
    def __init__(self, report):
        self.report = report
        self.change_bytes = 0

    def add(self, kind, baseline=None, candidate=None, **fields):
        if len(self.report['changes']) >= self.report['limits']['max_changes']:
            raise Failure('change_count_limit')
        row = {'kind': kind, 'baseline_path': locator(baseline), 'candidate_path': locator(candidate), **fields}
        self.change_bytes += json_size(row, REPORT_LIMIT - self.change_bytes) + 1
        if self.change_bytes > REPORT_LIMIT:
            raise Failure('report_byte_limit')
        self.report['changes'].append(row)
        self.report['summary'][kind] += 1
        self.report['summary']['changes'] += 1

    def element(self, kind, node):
        descriptor = None
        if node.key_attribute is not None:
            descriptor = {'attribute': node.key_attribute,
                          'value': value_record(node.attrs[node.key_attribute], self.report['policy'])}
        self.add(kind, baseline=node if kind == 'element_removed' else None,
                 candidate=node if kind == 'element_added' else None,
                 subtree_elements=node.subtree_elements, identity=descriptor)

    def compare(self, baseline, candidate):
        if baseline.tag != candidate.tag:
            self.element('element_removed', baseline)
            self.element('element_added', candidate)
            return
        pending = [(baseline, candidate)]
        while pending:
            old, new = pending.pop()
            self.report['summary']['matched_elements'] += 1
            for name in sorted(old.attrs.keys() | new.attrs.keys()):
                before, after = old.attrs.get(name), new.attrs.get(name)
                if before == after:
                    continue
                kind = ('attribute_added' if name not in old.attrs else
                        'attribute_removed' if name not in new.attrs else 'attribute_changed')
                self.add(kind, old, new, attribute=name,
                         before=value_record(before, self.report['policy']),
                         after=value_record(after, self.report['policy']))
            if old.text != new.text:
                self.add('text_changed', old, new,
                         before=value_record(old.text, self.report['policy']),
                         after=value_record(new.text, self.report['policy']))
            old_index = {child.match_id: child for child in old.children}
            new_index = {child.match_id: child for child in new.children}
            common = old_index.keys() & new_index.keys()
            old_order = [child.match_id for child in old.children if child.match_id in common]
            new_order = [child.match_id for child in new.children if child.match_id in common]
            if old_order != new_order:
                self.add('children_reordered', old, new, common_children=len(common))
            for child in old.children:
                if child.match_id not in new_index:
                    self.element('element_removed', child)
            for child in new.children:
                if child.match_id not in old_index:
                    self.element('element_added', child)
            # Reverse-push yields deterministic baseline document order for matched descendants.
            for child in reversed(old.children):
                if child.match_id in common:
                    pending.append((child, new_index[child.match_id]))


def encode_report(report):
    encoded = bytearray()
    for piece in json.JSONEncoder(ensure_ascii=True, indent=2).iterencode(report):
        block = piece.encode('utf-8')
        if len(encoded) + len(block) + 1 > REPORT_LIMIT:
            raise Failure('report_byte_limit')
        encoded.extend(block)
    encoded.extend(b'\n')
    return encoded


def write_report(encoded, target):
    if target is None:
        sys.stdout.write(encoded.decode('utf-8'))
        return
    directory(target.parent)
    created = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(target, flags, 0o600), 'wb') as stream:
            created = os.fstat(stream.fileno())
            stream.write(encoded)
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


def compare_files(args):
    keys = list(dict.fromkeys(DEFAULT_KEYS if args.key_attribute is None else args.key_attribute))
    settings = policy(keys, args.unkeyed, args.include_values)
    limits = {name: getattr(args, name) for name in DEFAULT_LIMITS}
    report, target = blank_report(settings, limits), None
    try:
        if len(keys) > 64:
            raise Failure('key_attribute_count_limit')
        baseline_path, candidate_path = absolute(args.baseline), absolute(args.candidate)
        target = new_output(args.output, [baseline_path, candidate_path])
        baseline, details, baseline_state = read_xml(baseline_path, settings, limits)
        report['inputs']['baseline'] = details
        report['summary']['baseline_elements'] = baseline.subtree_elements
        candidate, details, candidate_state = read_xml(candidate_path, settings, limits)
        report['inputs']['candidate'] = details
        report['summary']['candidate_elements'] = candidate.subtree_elements
        Comparison(report).compare(baseline, candidate)
        if (identity(checked(baseline_path)) != identity(baseline_state)
                or identity(checked(candidate_path)) != identity(candidate_state)):
            raise Failure('input_changed')
        report['complete'] = True
    except Failure as error:
        report['errors'].append({'code': error.code})
    return report, target


class Parser(argparse.ArgumentParser):
    def error(self, unused):
        raise Failure('invalid_arguments')


def parser():
    result = Parser(description=__doc__)
    result.add_argument('--version', action='version', version=VERSION)
    result.add_argument('--baseline', required=True, help='Existing ordinary local UTF-8 XML baseline file')
    result.add_argument('--candidate', required=True, help='Existing ordinary local UTF-8 XML candidate file')
    result.add_argument('--output', help='New JSON file with an existing parent; refuses input paths and overwrites')
    result.add_argument('--key-attribute', action='append', type=key_attribute,
                        help='Repeat for identity-key precedence; replaces defaults. Use NAME or {URI}NAME')
    result.add_argument('--unkeyed', choices=('reject', 'ordinal'), default='reject',
                        help='Default rejects repeated unkeyed sibling tags; ordinal explicitly matches positions')
    result.add_argument('--include-values', action='store_true',
                        help='Expose actual changed values and added/removed key values in the report')
    descriptions = {'max_bytes': 'Maximum raw bytes per XML input file',
                    'max_depth': 'Maximum element depth per input file, counting the root as 1',
                    'max_elements': 'Maximum elements per input file',
                    'max_attributes': 'Maximum attributes summed across each input file',
                    'max_changes': 'Maximum change rows in the comparison report'}
    for name, default in DEFAULT_LIMITS.items():
        result.add_argument('--' + name.replace('_', '-'), type=bounded_integer(name), default=default,
                            help=f'{descriptions[name]} (default {default}; hard maximum {HARD_LIMITS[name]})')
    return result


def main(argv=None):
    report = blank_report()
    try:
        args = parser().parse_args(argv)
        report, target = compare_files(args)
        encoded = encode_report(report)
        write_report(encoded, target)
        if not report['complete']:
            return 1
        return 2 if report['changes'] else 0
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
