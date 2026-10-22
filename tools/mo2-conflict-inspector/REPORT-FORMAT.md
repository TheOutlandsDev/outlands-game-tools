# Report format and interpretation

The inspector writes one UTF-8 JSON object. Version 1 uses
`"schema_version": 1` and identifies the generator in `tool.name` and
`tool.version`. Treat future versions as potentially different formats; check
the schema version before processing a saved report in your own program.

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | JSON schema version, currently `1`. |
| `tool` | Tool name and version. |
| `summary` | Coverage and finding counts; start with `complete`. |
| `providers_priority_highest_first` | Participating providers, highest priority first, with `name`, `kind` (`mod` or `overwrite`), and numeric `priority` (0 is highest). Overwrite's report name is `<overwrite>`. |
| `file_conflicts` | Relative paths with multiple loose-file providers, ordered provider names, and winner. |
| `analysis.lua_function_repeats` | Qualified symbols declared in at least two effective Lua/script files. |
| `analysis.ltx_duplicate_keys` | Repeated section/key pairs within one effective LTX file. |
| `analysis.unlocalizer_duplicates` | Repeated supported unlocalizer declarations within or across effective files. |
| `warnings` / `errors` | Structured diagnostic codes and any associated safe relative references. Review both. |
| `limitations` | Boundaries of this analysis recorded with the report. |

The report avoids absolute input roots, source text, config values, and diffs.
It still includes mod names, relative paths, and declaration names. Review and
redact those before publishing a report. Structured errors avoid raw operating
system exception strings in JSON; your shell and terminal messages are not
automatically redacted.

## Summary

| Field | Meaning |
|---|---|
| `complete` | `false` if input validation or coverage failed. A partial report must not be read as a complete inventory. |
| `enabled_mods` | Count of enabled mod entries selected for inspection. |
| `scanned_providers` | Number of mod/Overwrite providers scanned. |
| `loose_files` | Number of inventoried loose-file instances across providers, including masked copies. |
| `effective_files` | Number of unique paths after priority selection. |
| `file_conflicts` | Number of paths with multiple providers. |
| `lua_function_repeats` | Number of repeated qualified Lua symbols. |
| `ltx_duplicate_keys` | Number of duplicate section/key groups within effective files. |
| `unlocalizer_duplicates` | Number of repeated unlocalizer symbols. |
| `findings` | Sum of the four finding counts above. Not a severity score. |

With `--fail-on-conflicts`, any complete report with `findings > 0` returns 2.
Without that switch it returns 0. Incomplete scans and input/write failures
return 1. Always check completeness before considering finding counts.

## File conflict example

This is a fragment of the generated toy-profile report:

```json
{
  "path": "gamedata/configs/toy.ltx",
  "providers_highest_first": ["Hotfix", "Base"],
  "winner": "Hotfix"
}
```

The path is normalized to lowercase for case-insensitive matching. The first
provider wins among the scanned loose files. This example does not say whether
the two copies have the same contents, whether Hotfix is compatible with Base,
or how a packed archive might affect the game. Those checks are outside the
tool's model.

## Declaration references

Text findings point at a provider, the file's relative `path`, and its
one-based `line`. For example:

```json
{
  "symbol": "ui.refresh_menu",
  "declarations": [
    {"provider": "Base", "path": "gamedata/scripts/menu.script", "line": 1},
    {"provider": "Hotfix", "path": "gamedata/scripts/settings.script", "line": 1}
  ]
}
```

This indicates a repeated qualified declaration in separate effective files.
It does not establish which declaration runs last or whether either executes.
Local declarations and two different qualified symbols are different cases;
read the README's heuristic limits before treating this as a runtime conflict.

LTX findings use `section`, `key`, and a `declarations` list. They group repeated
keys only within the same effective file. Unlocalizer findings use `symbol`
and declaration references, within or across effective files. No source
values or surrounding code are copied into these records.

## Interpreting incomplete reports

An incomplete scan can still show useful findings for the files it read, but
missing content can change winners and duplicate counts. Common causes include
missing enabled-mod folders, unsupported foreign modlist entries, ambiguous
case, links/reparse points, unreadable files, invalid UTF-8, or the text-size
limit. Keep the diagnostics with the report when reviewing it locally.

Use the [toy example](examples/README.md) to establish expected behavior before
investigating an unfamiliar real profile. For an issue, share only a minimal,
redacted reproduction you have the right to publish.
