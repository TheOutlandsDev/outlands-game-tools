#!/usr/bin/env python3
"""Generate original fictional captured files, generic receipts and manifests. MIT."""
import argparse
import hashlib
import json
from pathlib import Path


def json_bytes(document):
    return (json.dumps(document, indent=2) + '\n').encode('utf-8')


def receipt(role, **changes):
    document = {'schema_version': 1, 'session_id': 'toy-session', 'event': role,
                'process_id': 1234, 'executable_id': 'toy-game',
                'timestamp_utc': '2026-01-01T12:00:00Z' if role == 'launch' else '2026-01-01T12:02:00Z'}
    if role == 'exit':
        document['exit_code'] = 0
    document.update(changes)
    return document


def file_reference(path, data):
    return {'path': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def create_session(root, mode='clean'):
    root.mkdir(parents=False, exist_ok=False)
    captures, receipts = root/'captures', root/'receipts'
    captures.mkdir(); receipts.mkdir()
    capture = b'Original fictional session capture. No real game was launched.\n'
    launch = json_bytes(receipt('launch'))
    changes = {'process_id': 4321, 'timestamp_utc': '2026-01-01T11:59:00Z', 'exit_code': 7} if mode == 'inconsistent' else {}
    exit_data = json_bytes(receipt('exit', **changes))
    (captures/'toy.log').write_bytes(capture)
    (receipts/'launch.json').write_bytes(launch)
    if mode != 'missing-exit':
        (receipts/'exit.json').write_bytes(exit_data)
    document = {'schema_version': 1, 'session_id': 'toy-session',
                'captures': [file_reference('captures/toy.log', capture)],
                'receipts': {'launch': file_reference('receipts/launch.json', launch),
                             'exit': None if mode == 'missing-exit' else file_reference('receipts/exit.json', exit_data)}}
    (root/'manifest.json').write_bytes(json_bytes(document))
    if mode == 'changed-capture':
        (captures/'toy.log').write_bytes(b'Changed fictional capture after manifest creation.\n')
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    destination = Path(args.destination)
    destination.mkdir(parents=False, exist_ok=False)
    for mode in ('clean', 'changed-capture', 'missing-exit', 'inconsistent'):
        create_session(destination/mode, mode)
    print('Created four original fictional session evidence folders.')


if __name__ == '__main__':
    main()
