# Preparing a tagged source release

The collection is distributed as reviewed source. A tag identifies the exact
repository revision; module versions and the collection release version need
not be identical. The first collection tag is `v0.1.0`, labeled a pre-release
because SPT modules and engine integration retain experimental runtime limits.
See [the download quick start](QUICK-START.md).

The commands below prepare the local v0.2.0-rc.1 review candidate. Publication
is a separate owner decision after reviewing the package and exact-revision CI.
Preserve the published v0.1.0 and v0.1.1-rc.1 tags/assets; they identify earlier
snapshots. Never replace main with an older release branch.

## Review and validate source

Keep source, tests, documentation and original generated examples in the public
tree. Do not add game/SDK/mod binaries, dependency wheels, actual saves, raw logs,
profiles, private reports or distribution archives. Keep private audit receipts
outside the publication tree. Preserve existing module and dependency licenses;
the collection's MIT license does not relicense inspected files or upstream code.

After reviewing all changes, regenerate and verify the source inventory:

```powershell
py -3.12 -B tools\verify_source_release.py --write-manifest
py -3.12 -B tools\verify_source_release.py
```

Do not regenerate just to hide an unexplained mismatch. Run the meaningful
module regressions and publication-gate checks, parse workflow/configuration
changes, and wait for the exact published commit's CI results. Distinguish
executed checks, platform skips and untested engine/gameplay behavior.

## Build the selected archive

Use the [Verified Source Release Builder](../tools/source-release-builder/README.md),
which selects manifest records rather than copying a project/game directory.
Run from the reviewed repository root, after creating an external output folder:

```powershell
py -3.12 -B tools\source-release-builder\source_release.py `
  --source-root . `
  --prefix outlands-game-tools-v0.2.0-rc.1 `
  --output 'D:\ReleaseOutput\outlands-game-tools-v0.2.0-rc.1-source.zip'
```

The output and companion `.zip.sha256` must be new and outside the source tree.
The builder verifies source lengths/hashes, uses fixed ZIP metadata/member
ordering, and checks stored members before reporting success. Entries are stored
without compression to avoid compressor-version differences; this trades a
larger download for straightforward reproducibility in the tested environments.
Read its guide for limits and failed-output behavior.

## Publish and verify

Create the tag/release against the reviewed commit, with a clear title and
notes listing included tools, dependencies, actual validation and remaining
limits. Attach the verified custom source ZIP and its checksum. Label the
experimental collection release as a pre-release. No game files or compiled
dependency payloads belong in these assets.

Verify the public tag resolves to the intended commit, the release is visible,
both custom assets have the expected names/sizes/hashes, and documentation,
feedback links and the download quick start work. GitHub's automatic source
ZIP/tar assets are separate downloads; do not apply the custom ZIP's checksum
to them. Keep a private receipt of the exact revision and uploaded asset hashes.

No automatic release publication, signed provenance or binary distribution is
implemented by the source builder itself. Creating a GitHub release and
uploading assets are separate maintainer operations.
