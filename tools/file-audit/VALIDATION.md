# File Audit validation

## Local checks

- Compiled on Windows with Corretto JDK 17.0.12 using `--release 17`, explicit
  UTF-8, `-Xlint:all` and `-Werror`.
- The test suite contains **44 named cases**, including four Swing lifecycle/UI
  cases. The local run passed 38 and skipped six native symlink/junction/hard-link
  fixtures because this review environment did not permit their creation. A skip
  is not a successful platform test.
- Generated-filesystem checks cover known SHA-256 values, duplicate/empty-file
  semantics, unchanged inputs, metadata-only behavior, extension filters, file/
  entry/depth/hash/time limits, cancellation, disappearing/changed files, Unicode,
  JSON escaping, private-root omission, bounded issues, exclusive/outside-root
  reports and CLI behavior. Native link/identity checks run where supported.
- Swing tests cover idle startup/demo data, display-only filtering, plain-text
  rendering of untrusted labels and Start/Stop/result state with a controlled
  background worker. GUI tests require a real/virtual display when requested.
- A separate four-file generated example was audited through the CLI. Independent
  Python parsing and SHA-256 verification matched all four records, 51 hashed
  bytes and the expected single duplicate pair. This independent check is not an
  application dependency.
- The actual desktop window was visually inspected and its file-free demo was
  clicked, showing three fictional rows, a candidate-group count and an enabled
  report-save control. No real personal directory was scanned for qualification.

## CI and packaging

The source-check workflow runs JDK 17/21 on Windows and Ubuntu, using a virtual
display for Ubuntu Swing cases. Tests scan generated fixtures only; they do not
inspect a runner's real project/system folders as application inputs. Native
link fixtures may skip when setup is unavailable; the test output lists skips.
See repository Actions for actual run status rather than treating configuration
alone as evidence of passing CI.

The publication gate checks the exact text-source inventory, private-path/secret
indicators, declared file types and local documentation links. App Java sources
are explicitly allowlisted. Generated `bin` output, runtime/dependency binaries,
actual audit inventories and private preparation receipts are not distributed.

## Practical limits

This is a bounded, best-effort auditor on trusted local folders. It is not an
atomic point-in-time snapshot, adversarial link-race containment mechanism,
security detector or storage-space estimator. Filesystems can block native calls
beyond a cooperative cancellation/time check; mapped network storage is not
reliably identified. Silent same-size/mtime-preserving changes can escape the
metadata checks. Hard-link separation depends on provider file identity.

Huge/hostile/mutating trees, remote storage, alternate filesystem providers,
arbitrary reparse tags and long-running multi-million-file workloads have not
been qualified. Default limits intentionally make such captures partial.
macOS is not in this release's CI matrix. A disk error can leave an incomplete
new report; exclusive creation is not an all-or-nothing filesystem transaction.
