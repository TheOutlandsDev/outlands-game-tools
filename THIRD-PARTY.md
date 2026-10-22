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
