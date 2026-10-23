# .NET Assembly Inspector

Read one managed `.dll` or `.exe` as a PE file and print a JSON metadata report. This
tool uses `PEReader` and `System.Reflection.Metadata`; it does **not** load the
assembly into a runtime, resolve its dependencies, or execute its entry point,
module initializers or other code.

Version **1.0.0**. MIT licensed as part of Outlands Game Tools; see the repository
[LICENSE](../../LICENSE) and [source origin](ORIGIN.md).

## Requirements and build

- The .NET 9 SDK, retaining the original tool's `net9.0` baseline.
- Windows or Linux with that SDK available. The tool itself uses only the .NET
  framework libraries, with no NuGet package dependencies.
- Python 3.12 or newer is needed only for the integration tests.

Use a currently patched SDK. The published [.NET support policy](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)
lists .NET 9 support ending **November 10, 2026**; the retained target is the
reviewed original baseline, and a future target update needs its own build/test pass.

From the repository root:

```text
dotnet build tools/dotnet-assembly-inspector/Inspector.csproj --configuration Release --artifacts-path .audit/assembly-inspector
dotnet .audit/assembly-inspector/bin/Inspector/release/Outlands.AssemblyInspector.dll --help
```

Build products go beneath `.audit/assembly-inspector`, not into the source tool
folder. Run this standalone project; no game, mod, inspected project or plugin
needs to be started or built.

## Inspect an assembly you are allowed to inspect

```text
dotnet .audit/assembly-inspector/bin/Inspector/release/Outlands.AssemblyInspector.dll path/to/YourAssembly.dll
```

There is exactly one positional input. Quote a path containing spaces. A filename
starting with `--` can be passed through a relative or absolute path such as
`./--example.dll`. `--help` and `--version` are also available.

Use an ordinary stable file, not a device, pipe or special stream. The tool reads
a bounded in-memory snapshot using read-only file access. It never
writes the input. It does not emit the command-line input path or debug-directory
file paths. On systems that permit concurrent writes, a same-size mutation during
the snapshot read cannot be ruled out; choose a stable, closed build artifact.

To save a report, redirect stdout to a **new location outside your inspected
project**, for example from PowerShell or a Linux shell:

```text
dotnet .audit/assembly-inspector/bin/Inspector/release/Outlands.AssemblyInspector.dll path/to/YourAssembly.dll > .audit/assembly-inspection.json
```

Shell redirection creates or overwrites its destination even when inspection
fails. Check the exit status before consuming or sharing it: PowerShell exposes
`$LASTEXITCODE`; a POSIX shell exposes `$?`. A failed inspection is not a clean bill
of health.

## What the report contains

| Field | Contents |
| --- | --- |
| `schemaVersion`, `toolVersion`, `inspection` | Format/tool identifiers and static inspection label |
| `assembly`, `module` | Names, versions, culture, public key bytes/flags and module MVID |
| `refs`, `typeRefs`, `memberRefs` | Assembly, type and member references |
| `types`, `fields` | Names, tokens, attributes, bases/interfaces, signatures, offsets and constant tokens |
| `methods` | Raw IL hex, signature hex, flags, locals token, stack limit and exception regions |
| `attrs`, `standalone` | Custom-attribute blobs and standalone-signature blobs |
| `userStrings` | Decoded user-string heap entries and offsets |
| `debug` | Debug-directory entry type/size/stamp/version, without reading PDB files |

Metadata tokens are uppercase eight-character hexadecimal strings; a nil handle is
an empty string. Blob and IL fields are uppercase hexadecimal. An abstract or
external method with no body has `il: ""` and null body properties. An exception
region has `filterOffset: null` unless it is a filter, and `catchType: ""` unless
it is a catch region. Token references and signature blobs are not resolved into
decompiled source. Types/members are listed in metadata order, not API ownership
groups.

An identity excerpt from the included synthetic fixture looks like this:

```json
{
  "schemaVersion": "1.0",
  "toolVersion": "1.0.0",
  "inspection": "static-managed-metadata",
  "assembly": {
    "name": "Outlands.SyntheticFixture",
    "version": "1.0.0.0",
    "culture": "",
    "publicKey": "",
    "flags": "0"
  }
}
```

The full report also contains the arrays described above. Compiler/SDK versions
can change emitted attributes, IL, tokens, MVIDs and debug entries; this is not a
byte-for-byte reproducibility or semantic comparison tool.

## Bounds, errors and supported scope

| Limit | Fixed maximum |
| --- | --- |
| Input snapshot | 32 MiB |
| Total metadata table rows | 100,000 |
| User-string entries or debug-directory entries | 100,000 each |
| One decoded string/blob/IL value | 1 MiB charged representation |
| Combined charged decoded values/tokens | 8 MiB |
| Serialized JSON including final newline | 16 MiB |

The decoded-value budget counts UTF-16 string storage, four bytes per blob/IL
source byte for its hex representation, and 16 bytes per visited metadata token.
It is an intentional rejection threshold, not a process-memory measurement. The
individual bound therefore permits at most 262,144 raw bytes in one hex field.
Strings are decoded by the framework before their decoded bound is checked;
the input bound still applies. These bounds do not impose a wall-clock timeout
or OS memory sandbox.

- Exit **0**: complete selected-field JSON report, help or version.
- Exit **2**: invalid arguments, unreadable file, malformed/unsupported input, or
  an exceeded limit. A short error goes to stderr without private exception text.
- No JSON is emitted for argument, parsing or limit failures. Reports are
  serialized into a bounded buffer before stdout is written. A later downstream
  I/O failure can still truncate a redirected stream.

The initial scope is managed PE **assemblies**. Native-only files and standalone
managed netmodules are rejected. Mixed/native method bodies and unusual formats
are not promised compatible. A successful report means these selected metadata
fields were readable within the bounds. It does not verify all PE structures,
IL correctness, runtime compatibility, signing, trust, safety or game behavior.
Resources, native code, dependency binaries and separate/embedded PDB contents
are not extracted or analyzed. Framework parser errors cause failure; malformed
user-string entries are not silently skipped.

## Generated reports and publication

**Treat reports as private until reviewed.** Assembly names, namespace/member
names, GUIDs, IL, attribute blobs and decoded strings may reveal private source
details, paths, URLs, embedded credentials or other data from the inspected
assembly. The absence of the command-line path does not sanitize its contents.
MIT covers this tool and its original synthetic fixtures; it does not grant
rights to redistribute an inspected assembly, its strings, its code or a report
derived from it. No real game assembly or generated game report is included here.

## Tests and synthetic examples

```text
python tools/dotnet-assembly-inspector/tests/test_inspector.py
```

The test harness builds only this inspector and the self-authored fixture under
`tests/fixtures`, using a temporary artifacts directory. It checks identities,
interfaces, constants/field offsets, raw IL, bodyless methods, filter/finally
regions, escaped Unicode strings, references/attributes/debug entries, malformed
and oversized inputs, a malformed user-string heap, well-formed decoded-value and
JSON-expansion limits, CLI behavior, unchanged input hashes and a module-initializer
execution sentinel. It invokes the inspector against the fixture; it never runs
the fixture assembly itself. There are no external test packages.

For an environment where the default temporary directory cannot be used by the
.NET SDK, set `OUTLANDS_TEST_TEMP` to an existing writable scratch directory.
For example in PowerShell:

```powershell
$env:OUTLANDS_TEST_TEMP = (Resolve-Path .audit).Path
python tools/dotnet-assembly-inspector/tests/test_inspector.py
```

To inspect the authored example manually, build it and pass its resulting DLL:

```text
dotnet build tools/dotnet-assembly-inspector/tests/fixtures/Fixture.csproj --configuration Release --artifacts-path .audit/assembly-inspector
dotnet .audit/assembly-inspector/bin/Inspector/release/Outlands.AssemblyInspector.dll .audit/assembly-inspector/bin/Fixture/release/Outlands.SyntheticFixture.dll
```

## Suggestions and issues

[Suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
or [report a problem](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml).
Include the tool/SDK version, OS, exit status and a small original synthetic
reproducer when possible. Review and remove private data before attaching reports;
do not upload proprietary/game binaries or credentials. Existing project
[contribution guidance](../../CONTRIBUTING.md) applies.
