# Fika repair and recovery review — 26 October 2026

This extends the existing [Game Tools Fika module](../spt/FikaHeadless/README.md).
The historical local transfer-repair input overlaps the published repair command;
it is not released as a second application. Owner confirmation covers their
original work, including AI assistance. See [provenance](../spt/FikaHeadless/PROVENANCE.md)
and the repository [MIT license](../LICENSE). No upstream implementation, private
configuration, profile, game data, installer, binary or runtime is included.

## Change and compatibility

The existing command names and core parameters are retained. Repair adds
preservation of unrelated JSON text and an optional fourth main-client core
configuration. Original bytes are backed up, hashed and verified before changes;
configuration writes are flushed and checked. New preview-first restore verifies
the fixed path allowlist and hashes before restoring original bytes or removing
only unchanged files newly created by the repair. Existing backup directories
are never replaced. The new private manifest is versioned; old-format backups
still require manual recovery.

The parser accepts a bounded conservative subset of strict UTF-8 JSON. Comments,
trailing commas, duplicate keys, unsupported encodings and excessive input are
rejected rather than rewritten. Selected launch properties are top-level only;
unrelated numbers, nested keys, formatting and existing StartMinimized booleans
are retained. Core INI keys must be unique across the selected file.

Repair/restore support fixed local NTFS volumes on Windows. Linked paths and
hard-linked files are rejected. These are stopped-installation operations,
not hostile concurrent-filesystem boundaries. Exclusive existing-file handles
reduce accidental concurrent writes. No service management, network access,
installer invocation, profile-content reading or gameplay test is performed.

## Validation scope

Local Windows native checks exercise both Windows PowerShell 5.1.26100.9711 and
PowerShell 7.6.5. The original wrapper regression suite passes in both editions.
The new repair suite exercises preview/WhatIf, byte-exact recovery, missing-file
restoration, existing JSON/BOM preservation, idempotence, selected main-client
edits, duplicate/escaped keys, malformed JSON, depth/token/size/encoding limits,
invalid network/profile inputs, stale plans, locks, real hard links/junctions,
changed targets, corrupt backups, manifest traversal/root mismatches, backup I/O
failure and the actual fictional demo generator. Exact final counts and CI
results are recorded after the final source run, not inferred from test names.

CI adds two Windows jobs, one for each PowerShell edition, running both suites.
The collection's source inventory, publication gate tests and archive check
remain enabled. No paid service, dependency installation or uploaded test
artifact is needed by these new jobs.

## Practical limits

No installed SPT/Fika/EFT files were read or changed in these tests. The existing
SPT 4.0.x-shaped paths inform interoperability; current game/Fika schema acceptance,
VPN connections, headless launch, shared raids and end-to-end installer behavior
remain unverified. No blanket version compatibility is implied.

Multi-file repair and restoration are not atomic and do not guarantee recovery
from power loss. Verified backups and the manifest remain available after an I/O
failure, but restore rejects unknown partial contents; manual reviewed recovery
can be necessary. Hashes are integrity checks, not backup authentication. Use
only your own trusted backups. Backup/restore covers unnamed file bytes, not
ACLs, alternate streams, timestamps or complete filesystem metadata. Inherited
Windows permissions and actual volume behavior remain relevant.

Public examples are fictional. Runtime previews/errors/manifests and original
backup bytes are private and may contain identifiers or configuration values.
Do not publish them. Use the [dedicated feedback form](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=fika_repair.yml)
for bugs, documentation fixes and suggestions with small invented examples.
Existing installer/pruning helpers are unchanged and retain their earlier
documented limitations; they do not use the new repair recovery engine.

Final local result: **37 repair checks passed in each edition (74 total, no skips)**.
The original wrapper regression suite also passed once in each edition.
Native link cases ran outside the restricted filesystem sandbox against only
disposable generated files. Publication/CI results are separate from these local results.

Publication gate: seven regression checks passed. Existing source-release builder:
57 discovered, 53 passed and four platform-specific skips; the initial sandbox
temporary-directory restriction was resolved with an isolated writable fixture root.
Workflow and feedback-form YAML parsed successfully. The collection inventory
contains reviewed text source only; no game, installer or runtime payload.
