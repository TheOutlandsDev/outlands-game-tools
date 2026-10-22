# MO2 Baseline Profile Builder

Preview a separate Mod Organizer 2 comparison profile with selected mods disabled.
Apply only after reviewing the changes and closing MO2 and the game. The original
profile stays unchanged; the destination must be new. No game is launched, stopped,
or tested by this utility.

Python **3.12 or newer**, standard library only. There are no packages to install,
network requests, administrator requirements, or executable dependencies. Original
source, documentation, tests, and generated examples use the collection's
[MIT license](../../LICENSE). This independent utility is not an official MO2 or
game project.

**This is a deliberately limited comparison-profile builder.** It copies
`modlist.txt` and up to four documented saved-profile files. It does **not** clone a
complete profile for every MO2-supported game. In particular, `plugins.txt`,
`loadorder.txt`, game-specific INI files, saves, mod content, and all other files
are excluded. Games that need those files require separate manual preparation.
Read the exclusions and shared-settings caveats before using the new profile.

## Get started

Download the repository with GitHub's **Code → Download ZIP**, extract it outside
your installed game and MO2 folders, and open PowerShell in
`tools\mo2-profile-builder`. Git users can clone the repository instead.

```powershell
py -3.12 --version
py -3.12 -B profile_builder.py --help
py -3.12 -B profile_builder.py --version
```

If you use `python`, check `python --version` and replace `py -3.12` accordingly.
On Linux and macOS the command may be `python3`; Python 3.12 or newer is required.
`-B` prevents Python bytecode caches beside the downloaded source.

## Find the profile and choose a destination

In MO2, identify the active instance's configured **Profiles** directory, then the
saved profile folder containing `modlist.txt`. Use MO2's configured path rather
than assuming that profiles are installed beside the executable. The
[official MO2 Paths documentation](https://github.com/ModOrganizer2/modorganizer/wiki/Settings-window#paths)
explains where these settings live.

Create the new profile beside your existing profiles so that MO2 can discover it.
Supply a **new folder name** whose parent already exists. A destination inside the
source profile, a parent of the source, an existing destination, and case variants
of existing destinations are refused. The utility never overwrites a profile.

The tool reads the saved modlist in its native order. It changes only an exact
`+Mod Name` row to `-Mod Name`; it does not reverse priority or reorder entries.
Copy each requested name exactly, including capitalization, without the `+`.
Already disabled entries, missing names, duplicate requests or rows, separator
requests, unsupported foreign entries, and unsafe names are refused. No mods
directory is inspected, so the tool does not establish whether a requested mod
is actually installed or compatible.

## Preview first

The default mode reads inputs and prints a JSON preview without creating the
destination. Substitute your own local paths and exact mod names:

```powershell
py -3.12 -B profile_builder.py `
  --source-profile 'D:\MO2\profiles\Main Profile' `
  --destination 'D:\MO2\profiles\Baseline Comparison' `
  --disable 'Example Content Mod' `
  --disable 'Example Balance Mod' `
  --output 'D:\MO2-Reports\baseline-preview-01.json'
$LASTEXITCODE
```

`D:\MO2-Reports` must already exist, and the report filename must be new. Omit
`--output` to print JSON to the terminal. The report lists only the reviewed
profile filenames, sizes, hashes, requested mod names, and planned changes.
It omits absolute source/destination paths and settings contents. Read the
[report format](REPORT-FORMAT.md) for field details.

Use `--output` to save a report. Avoid shell redirection such as `> report.json`:
the shell may truncate an existing file before this utility validates anything.
Reports must be outside both source and destination; linked output parents,
Windows device names, alternate data stream syntax, network paths, and existing
files are refused. Report parents must exist.

## Apply the reviewed change

1. Save the profile in MO2. Close MO2, the game, and any other profile writers.
2. Review the preview and confirm the intended exact mod names and destination.
3. Repeat the same inputs with `--apply --confirm-closed` and a fresh report name.

```powershell
py -3.12 -B profile_builder.py `
  --source-profile 'D:\MO2\profiles\Main Profile' `
  --destination 'D:\MO2\profiles\Baseline Comparison' `
  --disable 'Example Content Mod' `
  --disable 'Example Balance Mod' `
  --apply --confirm-closed `
  --output 'D:\MO2-Reports\baseline-applied-01.json'
$LASTEXITCODE
```

`--confirm-closed` is your explicit attestation that the relevant programs are
closed. It does not detect running processes. The tool will not close programs
or launch MO2 for you. It rereads and verifies the source during this invocation;
a previously saved preview is informational and is not an authorization file.

On success, check `status: "APPLIED"`, `complete: true`,
`source_verified_unchanged: true`, and `destination_verified: true`. Only then
open MO2, select the new profile, and review its settings before using it. The
program does not automatically select the new profile.

The tool stages and verifies the bytes in a new private sibling directory,
rechecks the source, creates the destination exclusively, copies and verifies
the planned files, and rechecks the source again. The source directory and file
identity, bounded file bytes, and relevant filename inventory must remain stable.
The source modlist's UTF-8 BOM, native row order, line endings, comments, and absent
final newline are preserved. Optional files are copied byte for byte.

Destination creation is **not an atomic directory transaction**: files appear
one at a time. Keep writers closed and do not use the destination until success.
On failure, cleanup removes only identity-matching files created by this run and
then tries to remove its empty new directories. It never recursively removes a
directory or deletes a pre-existing profile. Unexpected or changed files are
preserved and produce `rollback_incomplete`; review the destination manually
before retrying. A power loss or forced termination may leave a staging or
partial destination directory. There is no automatic recovery or destructive
restore command.

The report path is checked and reserved before profile creation. Disk failure
or interruption can still prevent the final report from being written after a
profile was created. In that case the utility exits with an error and tells you
to check the destination before retrying. It does not claim that an already
verified profile was undone.

## Exactly what gets copied

| Saved profile file | Behavior |
| --- | --- |
| `modlist.txt` | Required UTF-8 with optional BOM. Only requested `+` markers change. |
| `archives.txt` | Optional regular file; copied unchanged. |
| `initweaks.ini` | Optional regular file; copied unchanged. |
| `lockedorder.txt` | Optional regular file; copied unchanged. |
| `settings.ini` | Optional regular file; copied unchanged, without editing values. |

Every file is limited to **2 MiB**. The source and parent directory scans are
limited to **4,096 immediate entries**. There is no recursive scan. Linked files,
symlinks, junctions, Windows reparse points in selected paths or ancestors,
nonregular selected files, and case-ambiguous allowlisted filenames are refused.
Unknown files and directories are ignored, including `saves`; the tool does not
inspect or copy their contents. Paths use conservative Windows-compatible naming
rules on all platforms. Matching uses Python Unicode casefold to reject ambiguous
names; it does not reproduce every filesystem's collation rules.

## Shared saves and settings matter

An MO2 profile is **not an isolated copy of the game**. The new profile references
the same installed mods and can share saves, game configuration, MCM values,
Overwrite, and application data. Copying `settings.ini` does not change save/INI
isolation options. The tool does not interpret those settings, copy local saves,
or copy game-specific INI files. Other copied files can still refer to disabled
mods. Review the new profile in MO2 and the game's documentation.

Disabling content or scripted mods can break existing saves. Use an appropriate
new game or a disposable test save for comparison. This utility does not verify
dependency requirements, plugin order, archive behavior, script state, or actual
gameplay. Neither a successful copy nor a clean hash report proves the reduced
mod setup will work. Keep your existing save backup separately.

## Exit codes and errors

| Exit code | Meaning |
| --- | --- |
| `0` | Complete preview, or complete verified apply. Read `mode` and `status`. |
| `1` | Command-line usage, validation, filesystem, incomplete rollback, or report-writing failure. |

Before output reservation, errors go to standard output as sanitized JSON even
if `--output` was requested. After reservation, an apply failure goes to that new
report. A final report-writing failure writes a short message to standard error.
Raw operating-system messages, input settings, and absolute paths are not added
to JSON. Invalid command-line arguments return `invalid_arguments` without
echoing the supplied values; parsing-error reports use the default preview mode
because a complete invocation was not accepted. Drive-relative paths such as
`F:profile` or `F:` are refused instead of resolving against an ambient drive
directory. Reports can still expose private mod names, filenames, and hashes, so
review them before posting publicly.

Common errors include `closed_attestation_required`, `requested_mod_missing`,
`requested_mod_case_mismatch`, `requested_mod_already_disabled`,
`destination_exists`, `output_overlaps_inputs`, and `linked_path`. Choose a new
destination after success; existing profiles are always refused. Do not delete
anything simply to bypass an error without reviewing its contents.

## Try the generated example and tests

The [example instructions](examples/README.md) generate original synthetic profile
text in a new directory you choose. No game files, saves, or upstream mod code are
included. Try preview and apply there before supplying real MO2 paths.

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Tests generate their own inputs and cover unchanged originals, exact output
bytes, allowlist exclusions, BOM/newline preservation, invalid requests, size
limits, output guards, native links where supported, interrupted creation, source
changes, and preservation of unexpected files during rollback. Native link tests
report explicit skips where OS permissions prevent link creation. CI exercises
Windows and Ubuntu with Python 3.12 and 3.13; this is source/filesystem validation,
not gameplay testing.

## Bugs, suggestions, and contributions

[Suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
or [report a bug](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=bug_report.yml).
Include the tool version, Python/OS versions, a sanitized command with sample
paths, the error code, and a minimal synthetic modlist when possible. Do not post
actual saves, account details, private paths, settings contents, or game assets.

Useful contributions include generated examples for additional MO2 profile
formats, documentation corrections, portability reports, and better refusal
messages. Propose an expanded copy allowlist before implementing it; save copying,
automatic profile selection, and game launching are outside this tool's current
scope. See the collection's [contribution guide](../../CONTRIBUTING.md).
