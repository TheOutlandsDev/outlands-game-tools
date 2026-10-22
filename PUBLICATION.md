# Publication review

Prepared 2026-10-22 at the owner's request to release selected SPT and game tools
under MIT. The installed copies remain separate and unchanged. This review copy
is ready for source review; it is not an end-to-end tested gameplay distribution.

## Source selection and provenance

| Group | Selected source | Publication changes |
|---|---|---|
| SPT diagnostics and telemetry | Locally authored client plugins and PowerShell summarizers | External dependency paths parameterized; builds no longer install by default; privacy and synthetic tests documented. |
| Small SPT server/client mods | Original local API-integration mods | Source/config only, external references, build-only defaults, compatibility and persistent-state effects documented. Several original server metadata records already selected MIT. |
| Scav Life | Original local framework, client and dashboard | Real IDs and machine paths removed; console narrowed to loopback, normal TLS, exact origin/host and per-run token; mutations/debug methods opt-in. |
| Fika wrappers | Original local installer/config/pruning glue | Explicit inputs and previews replace fixed profiles/addresses and automatic changes; apply operations preserve backups. No upstream installer included. |
| Folder inventory | Original local Python directory exporter | CLI-selected paths, filtered metadata, no link traversal, relative reports, explicit overwrite and CSV formula protection. |
| Process observer | Original local process-exit diagnostic helper | Exact executable/PID selection, portable output path, bounded observation and independent snapshots. No game implementation. |
| MO2 conflict inspector | Original unpublished local profile-audit script, rewritten as a standalone CLI | Explicit mods/profile inputs, relative reports without source text or config values, link/path checks, exclusive report output, original toy profiles and synthetic tests. No upstream implementation or assets. |
| Lua syntax checker | Original unpublished compile-only audit, rewritten as an independent CLI | Explicit tree or MO2 inputs, selected external Lua parser, bounded reads, rejected bytecode, sanitized error reports, original fixtures, and checks that inspected chunks are never invoked. No bundled parser/game binaries. |
| Audio integrity checker | Original unpublished local sound audit, rewritten as an independent CLI | Explicit tree or MO2 inputs, bounded streamed decoding through external dependencies, sanitized reports, optional hashes, guarded new report output and original generated audio fixtures. No game audio or native decoder binaries. |

Private audit receipts record the original source paths and hashes. They are kept
outside the publication tree because local paths are not useful public content.
The original code was assistant-assisted; existing namespaces and plugin IDs are
retained for compatibility. The root MIT license reflects the owner's publication
instruction. The source inspection found no conflicting copyright/license header
in the selected original files; external dependencies remain separately licensed.

## Excluded content

No game/SDK/mod binaries, third-party source bundle, installer, artwork, saves,
profile data, raw telemetry, private endpoints, credentials, or build output is
part of the source manifest. The separate existing AGPL GAMMA project and the
separately prepared MW2 project are outside this repository.

## Checks and release limits

See [VALIDATION.md](VALIDATION.md) for compilation, synthetic checks and remaining
runtime work. [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) records reviewed file
bytes and SHA-256 hashes. Regenerate it only after reviewing changed source:

```powershell
python -B tools/verify_source_release.py --write-manifest
python -B tools/verify_source_release.py
```

The initial preparation was local. Publication receipts are kept privately
outside this tree. The MO2 addition is reviewed as a separate source update;
see its module README and the validation record for its scope and checks.
