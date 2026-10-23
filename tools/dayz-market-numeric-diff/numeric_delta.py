"""Original, in-memory numeric DayZ market edit recovery; no filesystem writes.

Copyright (c) 2026 TheOutlandsDev. SPDX-License-Identifier: MIT
The MIT grant covers this implementation, not input templates or recipe data.
"""
import copy
import hashlib
import json
import math
import re

MAX_INPUT_BYTES = 1_000_000
MAX_DEPTH = 64
MAX_NODES = 100_000
MAX_OPERATIONS = 20_000
TOP_FIELDS = ('InitStockPercent', 'IsExchange')
ITEM_FIELDS = ('MaxPriceThreshold', 'MinPriceThreshold', 'SellPricePercent',
               'MaxStockThreshold', 'MinStockThreshold', 'QuantityPercent')
POINTER = re.compile(r'/(InitStockPercent|IsExchange)$|/Items/(0|[1-9][0-9]*)/('
                     + '|'.join(ITEM_FIELDS) + r')$')

def numeric(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))

def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result

def _finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise ValueError('Non-finite JSON number')
    return value

def _validate_json(value):
    """Bound parsed/object API trees; reject cycles and non-JSON values."""
    nodes = 0
    text_chars = 0
    active = set()
    def visit(current, depth):
        nonlocal nodes, text_chars
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('JSON tree resource limit')
        kind = type(current)
        if kind is str:
            text_chars += len(current)
        elif current is None or kind is bool or kind is int:
            pass
        elif kind is float:
            if not math.isfinite(current):
                raise ValueError('Non-finite JSON number')
        elif kind in (dict, list):
            identity = id(current)
            if identity in active:
                raise ValueError('Cyclic object is not JSON')
            active.add(identity)
            if kind is dict:
                for key, child in current.items():
                    if type(key) is not str:
                        raise ValueError('JSON object key must be text')
                    text_chars += len(key)
                    visit(child, depth + 1)
            else:
                for child in current:
                    visit(child, depth + 1)
            active.remove(identity)
        else:
            raise ValueError('Unsupported JSON value type')
        if text_chars > MAX_INPUT_BYTES:
            raise ValueError('JSON text resource limit')
    visit(value, 0)

def _json_equal(left, right):
    """JSON booleans are distinct from numbers; int/float are JSON numbers."""
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if numeric(left) or numeric(right):
        return numeric(left) and numeric(right) and left == right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_json_equal(left[k],right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_json_equal(a,b) for a,b in zip(left,right))
    return left == right

def load_market(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_INPUT_BYTES:
        raise ValueError('Expected bounded JSON bytes')
    def bad_constant(value):
        raise ValueError('Non-finite JSON number')
    try:
        obj = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_object,
                         parse_constant=bad_constant, parse_float=_finite_float)
    except RecursionError:
        raise ValueError('JSON tree resource limit') from None
    _validate_json(obj)
    if not isinstance(obj, dict) or not isinstance(obj.get('Items'), list):
        raise ValueError('Expected a market category with Items array')
    return obj

def _location(obj, pointer):
    if not isinstance(pointer, str) or POINTER.fullmatch(pointer) is None:
        raise ValueError('Pointer outside allowed scalar fields')
    parts = pointer.split('/')[1:]
    if len(parts) == 1:
        return obj, parts[0]
    try:
        parent = obj['Items'][int(parts[1])]
    except (KeyError, IndexError, TypeError):
        raise ValueError('Missing item index') from None
    if not isinstance(parent, dict):
        raise ValueError('Item is not an object')
    return parent, parts[2]

def derive_numeric_changes(before, after):
    """Only emit changed finite scalars, never inherited ClassName/item lists.

    Positional item changes require matching ClassName at that position in both
    observations. A recipe must bind its positions to the exact before-byte hash.
    Other changes are reported as a boolean, without copying their contents.
    """
    _validate_json(before)
    _validate_json(after)
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError('Expected objects')
    left, right = before.get('Items'), after.get('Items')
    if not isinstance(left, list) or not isinstance(right, list):
        raise ValueError('Expected Items arrays')
    operations = []
    def compare(a, b, key, pointer):
        if key in a and key in b and numeric(a[key]) and numeric(b[key]) and a[key] != b[key]:
            operations.append({'op':'set_existing_numeric_field', 'pointer':pointer,
                               'before':a[key], 'after':b[key]})
    for key in TOP_FIELDS:
        compare(before, after, key, '/' + key)
    held_positions = abs(len(left)-len(right))
    for index, (a, b) in enumerate(zip(left, right)):
        if (not isinstance(a, dict) or not isinstance(b, dict)
                or not isinstance(a.get('ClassName'), str)
                or a.get('ClassName') != b.get('ClassName')):
            held_positions += 1
            continue
        for key in ITEM_FIELDS:
            compare(a, b, key, f'/Items/{index}/{key}')
    if len(operations) > MAX_OPERATIONS:
        raise ValueError('Operation resource limit')
    reconstructed = copy.deepcopy(before)
    for operation in operations:
        parent, key = _location(reconstructed, operation['pointer'])
        parent[key] = operation['after']
    equal = _json_equal(reconstructed, after)
    return {'operations':operations, 'held_identity_or_added_removed_positions':held_positions,
            'unselected_differences_present':not equal,
            'numeric_replay_matches_complete_observation':equal}

def preview_exact_baseline(raw, expected_sha256, operations):
    """Return a preview object only; hash and old values are mandatory guards."""
    if not isinstance(raw, bytes) or len(raw) > MAX_INPUT_BYTES:
        raise ValueError('Expected bounded JSON bytes')
    if not isinstance(expected_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('Expected lowercase SHA-256')
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Different baseline bytes')
    obj = load_market(raw)
    if not isinstance(operations, list) or len(operations) > MAX_OPERATIONS:
        raise ValueError('Invalid bounded operation list')
    seen = set()
    for operation in operations:
        if not isinstance(operation, dict) or set(operation) != {'op','pointer','before','after'}:
            raise ValueError('Unknown operation fields')
        if operation['op'] != 'set_existing_numeric_field':
            raise ValueError('Unsupported operation')
        pointer = operation['pointer']
        if not isinstance(pointer, str) or pointer in seen:
            raise ValueError('Duplicate or invalid pointer')
        seen.add(pointer)
        if not numeric(operation['before']) or not numeric(operation['after']):
            raise ValueError('Expected finite numeric values')
        parent, key = _location(obj, pointer)
        if key not in parent or not numeric(parent[key]) or parent[key] != operation['before']:
            raise ValueError('Observed baseline scalar differs')
        parent[key] = operation['after']
    return obj
