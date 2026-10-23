<!-- SPDX-License-Identifier: MIT -->
# Bounded Evidence Manifest Verifier

A small Python example that checks a directory of files against expected sizes
and SHA-256 hashes. It rejects malformed manifests, unsafe filenames, symbolic
links and special files while keeping reads bounded. Target files are opened
for reading only. This is an educational verifier with an intentionally narrow
format, useful for learning about validation and checking stable captured copies.

The source, tests and fictional examples are available under [MIT](LICENSE).
See [provenance](PROVENANCE.md) for the existing sample's origin and publication
changes. No game installation is required.

## Requirements

- Linux with Python 3.10 or later; Python standard library only.
- POSIX descriptor-relative `open`/`stat`, no-follow flags and directory file
  descriptors. Other POSIX systems with those capabilities may work but are
  unverified until separately tested.
- **Native Windows verification is unsupported.** Both public Python entry
  points raise `ManifestError` before opening inputs when required APIs are
  unavailable. The CLI prints an `INVALID` explanation and exits with status 2.
  Use Linux, or an existing Linux environment such as WSL; this tool does not
  install or configure one.

## Quick start with the fictional example

From the repository root in a Linux terminal:

```sh
cd tools/bounded-evidence-manifest-verifier
python3 -B verify_manifest.py examples/manifest.json examples/files
```

Expected output:

```text
PASS: all manifest entries matched
```

The included text is `synthetic evidence` followed by a newline. The manifest
describes its exact 19 bytes. Both example files are original synthetic data.
Line-ending conversion changes the bytes and therefore correctly causes a
mismatch; Git should preserve this fixture's original LF bytes.

To check your own stable copies, create a manifest using the format below, then
pass the manifest path and the directory containing those files:

```sh
python3 -B verify_manifest.py selected-manifest.json captured-files
```

Manifest entries select exact flat filenames. Unlisted directory contents are
ignored: this tool does not establish that a directory contains no extra files.
It never repairs files or changes the manifest to make a mismatch pass.

## Manifest format and limits

```json
{
  "version": 1,
  "files": [
    {
      "name": "sample.txt",
      "size": 19,
      "sha256": "b781ca4e3efcbf31178927825de855f45b7e52f0d652af03cfb236785de2fe48"
    }
  ]
}
```

| Item | Rule |
| --- | --- |
| Encoding | UTF-8 JSON; unknown and duplicate keys rejected |
| Version | Integer `1`; booleans are rejected as integers |
| Entries | 1 to 100, each with exactly `name`, `size`, `sha256` |
| Filename | One ASCII component, 1–128 characters, starting with an alphanumeric character; remaining characters may also be `.`, `_` or `-` |
| Duplicate names | Rejected using exact, case-sensitive spelling |
| Digest | Exactly 64 lowercase hexadecimal characters |
| Manifest size | At most 64 KiB |
| Individual file | 0 to 16 MiB |
| Declared total | At most 64 MiB |
| Read chunk | At most 64 KiB; at most declared file size plus one byte |

No directory separators, nested paths or path traversal are accepted. The
manifest and selected files must be regular files. The final target directory
component, manifest and selected files cannot be symbolic links.

## Results and exit codes

| Exit | Meaning | Example output |
| --- | --- | --- |
| `0` | Every selected entry matched | `PASS: all manifest entries matched` |
| `1` | One or more selected files failed | `FAIL: sample.txt: SHA-256 mismatch` |
| `2` | Invalid manifest, unsuitable target directory, unsupported platform or CLI usage | `INVALID: duplicate JSON key` |

Missing selected files, different sizes, different digests, special files and
detected changes during verification cause entry failures. Ordinary filesystem
errors are reported without a Python traceback. CLI argument errors use Python's
standard argument-parser output on stderr. A successful check says nothing about
unlisted files or who created the supplied manifest.

## Security boundary and limitations

- A matching digest checks bytes against the **given manifest**. It does not
  authenticate the author, prove chain of custody or establish that evidence is
  trustworthy. Someone who can replace both files and manifest can make a new
  matching pair.
- The directory and its ancestor path are assumed to be chosen by a trusted
  operator. Final components are protected against symbolic links, but this is
  not a hardened solution for a tree actively controlled by an adversary. Hard
  links are not rejected.
- The directory is opened once. Listed entries are opened relative to that
  descriptor with `O_NOFOLLOW`, and identity/size/timestamp metadata is checked
  before and after hashing. These checks reduce accidental inconsistency; they
  do not provide a transactional snapshot or fully defeat concurrent writes.
  Use stable copies and a separate trust mechanism for consequential evidence.
- Reading may update filesystem access time according to the filesystem's mount
  policy, even though target files are never opened for writing.
- The format supports one directory of regular files only. It has no recursion,
  signature verification, archive extraction, network transfer, repair, process
  monitoring or game-launch integration.
- Failure messages can include selected filenames and operating-system error
  text. Review output before sharing it publicly.

## Reproduce the synthetic tests

From this tool directory on Linux:

```sh
python3 -B -m unittest discover -s tests -v
```

Alternatively, from the repository root:

```sh
python3 -B -m unittest discover -s tools/bounded-evidence-manifest-verifier/tests -v
```

The original 16 tests cover matching and empty files, hash/size failures, missing
files, malformed/duplicate inputs, byte limits and symbolic-link refusal. They
create their own temporary files. CLI regressions cover a large JSON integer
and a duplicate key containing a control character. Additional tests check that
unsupported-platform API calls refuse to open inputs, and that the CLI returns
status 2 without a traceback. Windows runs the platform checks and explicitly
skips POSIX file-verification fixtures; those skips do not validate hashing on
Windows. These tests are not a security audit or proof of production suitability.

## Suggestions and bug reports

[Suggest a feature](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
or [report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml).
Questions and suggestions are welcome without a code contribution. Include this
tool's name, OS/Python versions, expected and actual behavior, and a small
fictional manifest plus a recipe for synthetic input bytes. Review names and
paths before posting; do not attach private evidence, logs, credentials or game
assets. See the repository's [contributing guide](../../CONTRIBUTING.md).
