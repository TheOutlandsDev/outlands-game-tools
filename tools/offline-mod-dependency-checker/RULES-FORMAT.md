# Inventory and rule format, schema 1

Both files are UTF-8 JSON with an optional initial BOM. JSON comments, duplicate
object keys, non-finite constants, trailing documents and unknown fields are
refused. Schema versions must be the integer `1`, not a boolean, string or float.
All listed fields are mandatory and no other fields are accepted.

## Inventory

```json
{"schema_version": 1, "load_order": ["Core", "Addon", "Patch"]}
```

`load_order` is an array of unique active names, in the earliest-to-latest order
to check. The array may be empty. Names are logical user assertions, not paths
that the checker resolves. The tool does not check installed presence, content,
versions or whether the manager actually uses this order.

Names are nonempty strings of at most 255 characters, with no leading/trailing
whitespace, trailing dot, slash/backslash, colon, forbidden Windows punctuation,
control character, surrogate, dot/parent component or reserved Windows device
name. This conservative single-component policy is shared with the collection.
Unicode names are allowed. Matching uses casefold with no normalization; for
example `Straße` and `STRASSE` collide, while precomposed/decomposed accents can
remain distinct. Duplicate/casefold-colliding names make input invalid.

## Catalog

```json
{
  "schema_version": 1,
  "rules": [
    {"id": "addon-needs-core", "type": "requires", "mod": "Addon", "target": "Core"},
    {"id": "patch-conflict", "type": "conflicts", "mod": "Patch", "target": "Alternative"},
    {"id": "core-first", "type": "load_before", "mod": "Core", "target": "Addon"}
  ]
}
```

`rules` is an array, possibly empty. Each object contains:

| Field | Contract |
|---|---|
| `id` | 1–64 ASCII letters/digits/`_.-`, starting with a letter/digit; unique ignoring ASCII case |
| `type` | Exactly `requires`, `conflicts` or `load_before` |
| `mod` | Source name using the same validation/matching as inventory names |
| `target` | Target name under the same policy |

Relations are checked only as written. `requires` requires target presence when
the source is active, with no implied order. `load_before` checks a strict
earlier position only when both names are active, with no implied presence.
`conflicts` checks mutual active presence symmetrically. Duplicate relations
after name matching are invalid; reversing a conflict is also a duplicate.
Different types between the same names are allowed and checked separately.
Opposite directed requirements/order edges are allowed and may create cycles.

Self rules are accepted explicitly: an active mod requiring itself satisfies the
direct presence check but creates an advisory catalog cycle; an active mod
loading before itself violates strict order and creates an order cycle; an
active self-conflict is a direct conflict. An inactive self relation has no
direct finding, but requirements/order catalog cycles still request review.

Rules may mention names absent from the inventory. Missing active requirements
are findings; inactive rules can be not applicable. Catalog cycle analysis still
includes those absent names. The checker does not fetch a missing catalog,
infer aliases or author additional/transitive rules.

Rule strings are data. There are no expressions, regular expressions, scripts,
shell commands, includes, URLs, callbacks, downloads or installation actions in
schema 1. Version constraints, alternatives and manager import formats require
a separately specified future schema; unknown fields are never silently ignored.

Hard limits are documented in [the report guide](REPORT-FORMAT.md). A valid
document can still exceed a combined metadata/report limit; that produces an
incomplete result rather than a partial success.
