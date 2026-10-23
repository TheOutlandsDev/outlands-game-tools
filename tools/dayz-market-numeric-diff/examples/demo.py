"""Fictional in-memory numeric diff example. MIT; no file inputs or outputs."""
import copy
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from numeric_delta import load_market, derive_numeric_changes, preview_exact_baseline

raw = b'{"Items":[{"ClassName":"Synthetic_A","MaxStockThreshold":1},{"ClassName":"Synthetic_B","MaxStockThreshold":1}]}'
before = load_market(raw)
after = copy.deepcopy(before)
after['Items'][0]['MaxStockThreshold'] = 50
result = derive_numeric_changes(before, after)
preview = preview_exact_baseline(raw, hashlib.sha256(raw).hexdigest(), result['operations'])
assert preview == after
assert preview['Items'][1]['MaxStockThreshold'] == 1
assert len(result['operations']) == 1
print(json.dumps(result, indent=2))
