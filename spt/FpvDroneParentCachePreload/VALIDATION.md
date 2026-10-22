# Release preparation validation

Date: 2026-10-22.

- PowerShell scripts parsed successfully using the PowerShell AST parser.
- Project XML parsed successfully.
- Release configuration compiled against locally installed matching references: **0 warnings, 0 errors**.
- Build used .NET SDK 9.0.310 and offline package feeds (`nuget.config` with cleared sources).
- Game/mod reference baseline: SPT 4.0.13; client baseline where applicable: Escape from Tarkov 0.16.9.40087, BepInEx 5.4.23.2.
- Source release excludes compiled binaries, intermediate outputs, captures, installed configuration, profiles, and third-party dependencies.

The restricted preparation shell could not discover the Windows SDK through the registry. Validation supplied the installed Windows SDK location through `TargetPlatformSdkPath` and the value `Windows` through `TargetPlatformDisplayName` as environment variables. This changed only the validation process environment. Normal unrestricted Windows builds may not need these overrides.

No game, server, raid, drone, UI flow, or co-op runtime was exercised. Compilation verifies API/type compatibility with the named local references; it does not verify live behavior or performance.
