#!/usr/bin/env python3
"""Generate original fictional JSON inventory/rule examples. MIT."""
import argparse
import json
from pathlib import Path


def rule(label, kind, mod, target):
    return {'id': label, 'type': kind, 'mod': mod, 'target': target}


CLEAN_RULES = [rule('addon-needs-core', 'requires', 'Addon', 'Core'),
               rule('patch-needs-addon', 'requires', 'Patch', 'Addon'),
               rule('alternative-conflict', 'conflicts', 'Patch', 'Alternative'),
               rule('core-before-addon', 'load_before', 'Core', 'Addon'),
               rule('addon-before-patch', 'load_before', 'Addon', 'Patch')]
REVIEW_RULES = CLEAN_RULES + [rule('addon-needs-patch', 'requires', 'Addon', 'Patch'),
                            rule('unused-a-before-b', 'load_before', 'Unused A', 'Unused B'),
                            rule('unused-b-before-a', 'load_before', 'Unused B', 'Unused A')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    destination = Path(args.destination)
    destination.mkdir(parents=False, exist_ok=False)
    documents = {'inventory-clean.json': {'schema_version': 1, 'load_order': ['Core', 'Addon', 'Patch']},
                 'inventory-review.json': {'schema_version': 1, 'load_order': ['Patch', 'Addon', 'Alternative']},
                 'rules-clean.json': {'schema_version': 1, 'rules': CLEAN_RULES},
                 'rules-review.json': {'schema_version': 1, 'rules': REVIEW_RULES}}
    for filename, document in documents.items():
        with (destination / filename).open('xb') as stream:
            stream.write((json.dumps(document, indent=2) + '\n').encode('utf-8'))
    print('Created four original fictional JSON example files.')


if __name__ == '__main__':
    main()
