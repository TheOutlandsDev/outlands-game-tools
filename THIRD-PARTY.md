# Dependency and license scope

The root MIT license applies to this collection's original tool and mod source,
documentation, and synthetic tests. The public copies were prepared from local,
assistant-assisted projects for Connor O'Shea (TheOutlandsDev). Existing metadata
in several server mods already selected MIT. The publication review found no
third-party implementation headers or bundled dependencies in the selected source;
this is a bounded source review, not a proof of originality of every expression.

External dependencies retain their own terms. This repository does not contain
Escape from Tarkov, SPT, Fika, Unity, BepInEx, Harmony, a game installation, game
assemblies, mods from other authors, downloaded installers, artwork, or real saves.
Build references point to dependencies supplied by the user on their own machine.
The MIT license here does not relicense those dependencies or their assets.

Obtain the game and dependencies through their respective maintainers:

- [Escape from Tarkov](https://www.escapefromtarkov.com/)
- [SPT server source and its license](https://github.com/sp-tarkov/server-csharp)
- [Fika](https://github.com/project-fika)
- [BepInEx](https://github.com/BepInEx/BepInEx)
- [Harmony](https://github.com/pardeike/Harmony)
- [Unity](https://unity.com/)

This collection is unofficial and is not endorsed by those projects or companies.
Runtime names, API names, identifiers, and references describe interoperability.
Review the relevant dependency versions and terms before distributing a compiled
package. Preserve applicable dependency notices if a future distribution includes
anything beyond this original source collection.

The separate GAMMA Clear Sky Warfare repository remains outside this collection
and retains its existing license. No source from that AGPL publication is copied
into this MIT collection. The generic process observer is adapted from an earlier
locally authored diagnostic helper, not from that publication tree.

The MO2 Conflict Inspector is an independent Python standard-library tool,
adapted from an unpublished, locally authored profile-audit script. No source
from MO2, GAMMA, their published AGPL companion, or inspected mods is bundled.
MO2's public source/documentation was consulted for file-format and priority
semantics; the inspector does not import or incorporate its implementation.
Its toy profiles and script/configuration examples are original synthetic data.
The collection's MIT license covers this original code and documentation;
MO2, games, and the files a user inspects retain their own terms.

The Lua Syntax Checker is original integration code adapted from a separate,
unpublished local compile-only audit. It contains no inspected game/mod source,
engine implementation, bytecode, or code from the AGPL GAMMA companion. Its
source/examples/tests/docs use this collection's MIT license. Lupa 2.8 is a
separately installed dependency, declared in the tool's requirements file;
its wheels and Lua/LuaJIT implementations are not bundled in this repository.
Preserve the applicable upstream notices when redistributing those components.
See [Lupa and its license](https://github.com/scoder/lupa),
[the reviewed PyPI version](https://pypi.org/project/lupa/2.8/),
[Lua's license](https://www.lua.org/license.html), and
[LuaJIT's license](https://luajit.org/ext_copyright.html).

The Audio Integrity Checker is original integration code adapted from a separate,
unpublished local sound audit. Its source, generated examples, tests and docs
are MIT; it includes no game audio, decoder implementation or source from the
AGPL GAMMA companion. The separately installed SoundFile 0.13.1 and NumPy 2.2.6
dependencies use BSD-style licenses. SoundFile uses CFFI and libsndfile; normal
platform wheels can include a native libsndfile build with its own LGPL terms.
These dependencies and their binaries are not part of this source repository.
Preserve the applicable notices and obligations if distributing them separately.
See [SoundFile's documentation and license](https://python-soundfile.readthedocs.io/en/0.13.1/),
[NumPy's reviewed version and license](https://pypi.org/project/numpy/2.2.6/),
[CFFI's license](https://cffi.readthedocs.io/en/stable/license.html), and
[libsndfile's licensing](https://libsndfile.github.io/libsndfile/).

The Save Snapshot Verifier is original Python standard-library integration code
adapted from an unpublished local backup helper. Its code, generated examples,
tests and docs are MIT. No source from the AGPL GAMMA companion is incorporated.
Actual files a user chooses to copy, including saves/configuration, retain their
own rights and privacy requirements; the tool's license does not relicense them.

The MO2 Baseline Profile Builder is original Python standard-library integration
code based on an unpublished local comparison-profile helper. Its original
source, tests, generated examples and docs are MIT. It does not incorporate MO2
implementation, inspected mod source or code from the AGPL GAMMA companion.
Files the user supplies retain their own terms. It is an independent limited
profile workflow, not an official MO2 profile clone or game compatibility layer.

The X-Ray Log Summary is original Python standard-library source with original
generated log fixtures. It uses text patterns to describe interoperability and
contains no engine code, raw player logs or implementation from the AGPL GAMMA
companion. Source, docs, tests and examples are MIT. The tool's license does not
grant redistribution rights to logs, scripts, game assets or inspected material.

The LTX Definition Inspector is original Python standard-library code with
fictional generated configuration fixtures. A local unpublished item-index
helper informed the problem; no surrounding barter/engine/mod implementation
was incorporated. Primary OpenXRay loader source was consulted for syntax, not
copied. This is a narrow structural checker, not that loader or a DLTX engine.
Its original code/docs/tests/examples are MIT. Inspected configuration and
external engines/mods retain their own terms; no AGPL companion source is copied.

Mod Content Manifest & Diff is new original Python standard-library source built
within this MIT collection. The use case overlaps the separate co-op content
preflight, but no AGPL launcher implementation, import or serialized fingerprint
format is incorporated. The AGPL companion keeps its own license. This tool's
code/docs/tests/examples are MIT; selected file contents are only read for hashing
and do not become licensed or distributable through a generated manifest.

The Verified Source Release Builder is original standard-library integration
code based on an unpublished source bundling helper. Its source/docs/tests and
fictional manifest examples are MIT. A manifest declaring MIT and a matching
LICENSE/hash do not establish ownership of every selected file; a maintainer
must separately review provenance, privacy and dependency terms before release.
The collection's tagged custom source ZIP contains only reviewed records and
the manifest itself, with no game or dependency binaries.

XML Mod Configuration Diff is fresh original Python standard-library integration
code, with original XML example generators and synthetic tests. A prior local
State of Decay comparison identified the use case; its private implementation,
baseline XML, downloaded mods and reports are not copied. This module includes
no lxml, game, mod-manager or AGPL companion implementation. Its original code,
documentation, tests and generated examples use the root MIT license.

XML parsing uses the separately installed Python runtime's Expat binding, with
Expat 2.7.2 or newer required for parsing. Python and Expat retain their own terms;
their implementations/binaries are not bundled. Primary Python documentation
informed API and security requirements, not copied implementation. Inspected XML
and values retain their own terms and privacy requirements. See
[Python XML security](https://docs.python.org/3/library/xml.html#xml-security),
[Expat API documentation](https://docs.python.org/3/library/pyexpat.html),
[Python licensing](https://docs.python.org/3/license.html) and
[Expat licensing](https://github.com/libexpat/libexpat/blob/master/expat/COPYING).

The Mod Asset Reference Checker is fresh original Python standard-library source
with original example generators, tests and documentation under the root MIT
license. Earlier private model/ammunition checks identified the use case only;
their surrounding native-script harnesses, game configuration, upstream patches,
asset payloads and implementation are not included. No source from the separate
AGPL companion is incorporated. Python retains its own runtime license.

Primary [OpenXRay configuration-loader source](https://github.com/OpenXRay/xray-16/blob/dev/src/xrCore/xr_ini.cpp)
and [weapon configuration source](https://github.com/OpenXRay/xray-16/blob/dev/src/xrGame/Weapon.cpp)
were consulted for format context, not copied. The checker implements its own
documented literal subset and file-rule mappings; it does not reproduce that
loader, apply DLTX, inspect packed archives or establish engine compatibility.
Files and path indexes supplied by a user retain their own rights and privacy
requirements. Listing a path or finding a loose file does not grant permission
to redistribute its content or prove it is a valid asset.

INI/LTX Configuration Value Diff is fresh original Python standard-library
source within this MIT collection. Its code, documentation, tests and generated
toy examples use the root MIT license. Existing collection path/report patterns
informed safeguards; no third-party parser, game configuration, private patch
implementation or separate AGPL companion source is incorporated.

Primary [Python configuration-parser documentation](https://docs.python.org/3/library/configparser.html)
and [OpenXRay loader source](https://github.com/OpenXRay/xray-16/blob/dev/src/xrCore/xr_ini.cpp)
were consulted for format context. Their implementation is not copied. The tool
uses an explicitly documented literal parser, with no ConfigParser default
inheritance, interpolation or engine value resolution. Inspected files and
exported values retain their own terms and privacy requirements. Python remains
a separately installed runtime under its own license.

Unreal PAK Index & Conflict Inspector is fresh original Python standard-library
source under the root MIT license, including its tests, documentation and original
toy fixture generator. Existing collection filesystem/report patterns informed
guards. Format research used the primary
[Epic version enumeration](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/PakFile/FPakInfo_2),
[Epic entry API](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/PakFile/FPakEntry),
[u4pak author's format description](https://github.com/panzi/u4pak#file-format)
and [repak field-layout reference](https://github.com/trumank/repak/blob/master/repak/src/entry.rs).
Only format facts were used; their parser implementations, engine source/headers,
licenses and binaries are not incorporated or relicensed here.

No game archives, assets, keys, proprietary codecs or separate AGPL companion code
are included. Python remains separately installed under its own license. Index
checksums are corruption checks, not authenticity guarantees; listed payload
digests are unverified assertions. Reports and inspected archives retain their
own rights/privacy requirements. The inspector grants no right to redistribute
third-party assets and performs no extraction or decryption.

Mod Package ZIP Layout Inspector is original Python standard-library source,
including its tests, documentation and toy fixture generator, under the root MIT
license. It reuses original collection filesystem/report guards. Format facts
were checked against [PKWARE APPNOTE 6.3.10](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT)
and [Python 3.12 ZIP documentation](https://docs.python.org/3.12/library/zipfile.html).
Neither specification text nor any third-party parser implementation is bundled.
Python remains separately installed under its own license; stdlib zipfile is used
only to generate original toy fixtures, not to parse untrusted selected archives.
No game/mod archives, payloads, keys or separate AGPL implementation are included.
Archive content and report member names retain their own rights/privacy terms.

MO2 Profile Change Report is original Python standard-library source, tests,
documentation and fictional profile generation under the root MIT license.
Existing collection modlist/name and filesystem/report safeguards informed the
implementation. Saved marker/order facts were checked against
[MO2 profile format handling](https://github.com/ModOrganizer2/modorganizer/blob/4ba22f0d8b6f9e08e44008b8395cd774551b4ebe/src/profile.cpp).
No upstream MO2/Qt implementation or license is copied or relicensed, and no
real profile, game/mod payload or separate AGPL companion code is included.
Python remains separately installed under its own license. Inspected modlist
names and report hashes retain their own privacy and rights requirements;
comparisons do not authenticate an installation or grant asset redistribution.

Offline Mod Dependency Rule Checker is original Python standard-library source,
tests, documentation and fictional JSON example generation under the root MIT
license. Existing collection filesystem/read/report guards are reused. Inventory
and rule schemas, direct checking and iterative cycle-group/witness analysis are
original implementations; no third-party graph/parser library, compatibility
database, game/mod data, real profile or separate AGPL source is incorporated.
JSON behavior was checked against [Python 3.12 documentation](https://docs.python.org/3.12/library/json.html).
Python remains separately installed under its own license. Authored rules and
names retain their own rights/privacy requirements; an offline check does not
verify those assertions or establish actual game/asset compatibility.

Game Session Evidence Auditor is fresh original Python standard-library source,
tests, documentation and fictional evidence generation under the root MIT
license. Existing original collection filesystem, bounded JSON and report guards
are reused. Generic manifest/receipt contracts, streaming verification and
redacted consistency checks are original; no separate AGPL launcher/crash-audit
implementation, upstream collector, real session receipt, private log or game
payload is copied or bundled. Standard-library behavior was checked against
[Python SHA-256/streaming hashing](https://docs.python.org/3.12/library/hashlib.html)
and [UTC datetime handling](https://docs.python.org/3.12/library/datetime.html).
Python remains separately installed under its own license. Evidence files,
manifest assertions and relative report names retain their own rights/privacy
requirements. Hash agreement does not authenticate a collector or attest gameplay.
