# JSON comparison report

Schema version **1**, tool version **1.0.0**, kind `xml-config-diff`. Reports
describe structural observations under an explicit matching policy, not a patch
or game-schema validation. See the [README](README.md) for commands and scope.

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | Integer format version, currently `1`. |
| `kind` | `xml-config-diff`. |
| `tool_version` | Producing tool version. |
| `complete` | Whether parsing, identity validation, comparison, stability and output checks completed. |
| `policy` | Keys, unkeyed matching, namespace/text handling and disclosure options. |
| `limits` | Positive byte/depth/element/attribute/change limits. |
| `inputs` | `baseline` and `candidate`, each `null` when unavailable or `{bytes, sha256}` for observed source bytes. No filenames. |
| `summary` | Parsed/matched element counts and change-record counts. |
| `changes` | Deterministically ordered structured changes. |
| `errors` | Controlled `{code}` failures without original XML or raw exception text. |

The source hashes cover original file bytes. Parsed value hashes cover the
UTF-8 encoding of the parsed string. These can differ for lexical variants
that parse identically, such as CDATA and escaped text. A report does not
authenticate its inputs or guarantee they stayed unchanged after the scan.

## Policy and limits

`policy.key_attributes` is the precedence list. Defaults are `id`, `Id`, `ID`,
`name`, `Name`, `Label`; repeated `--key-attribute` arguments replace them.
`policy.unkeyed` is `reject` by default or explicit `ordinal`.
`policy.include_values` records the boolean disclosure flag.

The remaining policy fields are `leaf_text: "exact"`,
`element_whitespace: "ignored"`, `comments: "ignored"`,
`processing_instructions: "ignored"` and `namespaces: "expanded"`.
Nonwhitespace mixed content is unsupported. These recorded choices are needed
to interpret equality; ignored comments, prefix spelling and indentation are
not reported as differences.

`limits` contains `max_bytes`, `max_depth`, `max_elements`, `max_attributes`,
`max_changes`. Defaults and hard ceilings appear in the [README](README.md).
The encoded report is also capped at 8 MiB. An incomplete report's counters
and change list are partial observations, not an exhaustive comparison.

## Structural paths and values

Every change has `kind`, `baseline_path` and `candidate_path`. A missing side
is `null`. A present path is an array of `{tag, occurrence}` objects from root
to element. `tag` is the expanded Clark name (`{namespace-uri}local`) or the
plain unnamespaced name. `occurrence` is one-based among same-expanded-tag
siblings; the root occurrence is `1`. Locator paths deliberately omit raw key
values. Baseline and candidate locators can differ after reordering.

A value descriptor is `{characters, sha256}` by default; `--include-values`
adds `value` with the exact parsed string. `characters` is Python string length,
not file-byte length. SHA-256 uses UTF-8 bytes and lowercase hex. An absent
attribute side is `null`, while an empty present value has zero characters and
the normal SHA-256 digest of an empty string.

Element changes can include an `identity` descriptor. It is `null` for an
unkeyed element, or `{attribute, value}` where `attribute` is the selected
expanded key-attribute name and `value` is the descriptor above. It identifies
only the unmatched subtree root, without exporting its descendants' values.

## Change kinds

| `kind` | Additional fields and meaning |
|---|---|
| `element_added` | Candidate-only subtree root: `subtree_elements`, `identity`; baseline path is `null`. |
| `element_removed` | Baseline-only subtree root: `subtree_elements`, `identity`; candidate path is `null`. |
| `attribute_added` | `attribute`, `before: null`, `after` value descriptor. |
| `attribute_removed` | `attribute`, `before` descriptor, `after: null`. |
| `attribute_changed` | `attribute`, `before` and `after` descriptors. |
| `text_changed` | `before` and `after` parsed leaf-text descriptors. |
| `children_reordered` | `common_children`: count of shared matched child identities whose sequence was compared. |

No rename guess is made. A root/tag or selected child identity change is represented
by removal/addition as appropriate. Same-tag document roots pair without key
matching, so a changed root key attribute is an attribute change. Added/removed descendants are summarized
under their unmatched subtree root rather than each being emitted separately.
Reorder records compare the sequence after filtering to common identities;
an insertion alone does not create a reorder record.

## Summary and exits

`summary.baseline_elements` and `candidate_elements` count parsed elements,
including each document root. `matched_elements` counts paired elements under
the policy. `summary.changes` is the number of emitted records.

The remaining summary fields count records of each kind: `element_added`,
`element_removed`, `attribute_added`, `attribute_removed`, `attribute_changed`,
`text_changed`, `children_reordered`. Element-added/removed record counts are
**not** counts of every descendant in the reported subtrees. Use
`subtree_elements` to understand those sizes.

A complete equality returns exit **0**; a complete report with changes returns
**2**. Any invalid/unsupported/incomplete operation or output failure returns
**1**. Input/parser errors can prevent fingerprints or counts from being
available. A command-line failure may occur before JSON exists. Check the exit
code together with `complete`; never infer equality from an incomplete empty
change list.

## Sharing reports

Absolute roots, source filenames, source XML and raw exception text are omitted.
Tag names, attribute names, namespace URIs, counts and hashes remain potentially
private, and opt-in `value` fields disclose parsed content. Guessable values
can be identified by comparing hashes. Review every report before sharing;
fingerprints are not anonymization, signatures, licensing evidence or proof of
runtime compatibility.
