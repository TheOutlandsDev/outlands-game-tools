# Source origin and license scope

The initial implementation was an original, AI-assisted, standalone C# metadata
inspection helper authored for a private project. Its basic approach used the
framework's `PEReader` and `System.Reflection.Metadata` APIs to read an assembly's
metadata and emit JSON. It did not contain copied game implementations, vendor
source, package code or embedded game files.

The public version preserves that static inspection scope and adds argument/error
handling, explicit resource/output bounds, complete-or-failed reporting and
original synthetic tests/documentation. The original private source remains
unchanged. This tool, documentation and synthetic fixture source are offered
under the repository's [MIT license](../../LICENSE).

The .NET framework and SDK retain their own upstream terms. Inspecting or reporting
another assembly does not change its license or establish permission to publish
its code, identifiers, literals or derived report. No inspected third-party/game
assembly or private generated report is distributed with this tool.
