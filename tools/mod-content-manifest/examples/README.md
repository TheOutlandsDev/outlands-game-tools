# Original generated example

`create_example.py` creates plain UTF-8 toy files authored for this MIT tool.
There are no game assets, actual saves, logs, copied mod implementations or
downloaded dependencies. Generate into a **new directory outside the repository
and your game folders**; binary fixtures and personal manifests should not be
committed to this source collection.

The tree contains:

- `baseline/` and `candidate/`: one changed `.ltx`, one removed `.ltx`, one added
  `.ltx`, and one unchanged `.script`.
- `mo2/mods/`: two enabled toy providers and one disabled provider.
- `mo2/modlist.txt`: a saved native-style list, highest enabled priority first.
- `mo2/base/` and `mo2/overwrite/`: matching virtual roots containing
  `gamedata/configs/`. Overwrite wins `shared.ltx`, while enabled mods and base
  also contribute unique paths.

Use the complete commands in the [main README](../README.md). Run the generator
with `--help` for its destination argument. It refuses an existing destination
and performs no automatic cleanup. Keep your manifests in the demo's parent
directory, outside every selected scan root. Files created by the generator are
deliberately tiny; the examples do not measure real mod-pack performance.
