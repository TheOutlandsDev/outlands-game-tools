<!-- SPDX-License-Identifier: MIT -->
# Origin and publication changes

This package preserves and minimally prepares an existing educational Python
sample created with AI-assisted development on 2026-10-08. The sample's original
README explicitly recorded new original code and synthetic fixtures, with no
reused private reports, archived project implementations or third-party source.
It was previously supplied for owner review without a selected license. The
owner authorized public MIT publication of verified original tools on
2026-10-23. This copy is released under the included MIT license.

The reviewed source archive was named
`bounded-evidence-manifest-verifier-owner-review-20261008.zip`, with SHA-256:

```text
94e3d0fb963cce6ea169b1a93dee33d5b548aada9ec2b54a52b1969f83fae3a6
```

The archive contained exactly five files: `README.md`, `verify_manifest.py`,
`tests/test_verify_manifest.py`, `examples/manifest.json` and
`examples/files/sample.txt`. Source and fixture contents were reviewed before
preparation. Only Python standard-library imports are required; no external
source or dependencies are bundled.

Publication preparation retained the manifest format, hashing, bounded reads,
no-follow behavior, security limits and all original 16 test cases. Changes add:

- Explicit required-platform checks before either public API opens inputs.
- Deliberate native Windows rejection rather than unsupported flag exceptions.
- Test discovery from the collection root, POSIX fixture skips where unsupported
  and three additional platform-behavior regressions.
- SPDX headers, MIT license, expanded instructions and suggestion links.

Both fictional example files retain their original bytes. No real evidence,
private project paths, original development-session records or game data are
included. The original review archive remains unchanged.
