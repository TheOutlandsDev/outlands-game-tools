# Generated comparison-profile example

These examples use original synthetic text. They do not use an installed game,
real mod, save, or MO2 configuration. Generate fixtures **outside the downloaded
repository** in a new directory with an existing local parent:

```powershell
py -3.12 -B examples\create_example.py 'D:\MO2-Builder-Example'
```

Replace the sample drive/path with an available location. The generator refuses
existing destinations and linked parent paths. It creates `Original Profile`
with a BOM/CRLF modlist, synthetic `settings.ini` and `archives.txt`, plus a
`plugins.txt` file that demonstrates the deliberate copy exclusion. Nothing is
added to MO2 or selected automatically.

From the tool's directory, preview disabling one exact row:

```powershell
py -3.12 -B profile_builder.py `
  --source-profile 'D:\MO2-Builder-Example\Original Profile' `
  --destination 'D:\MO2-Builder-Example\Comparison Profile' `
  --disable 'Example Content Mod' `
  --output 'D:\MO2-Builder-Example\preview.json'
```

Expected: exit `0`, `status: "PREVIEW"`, three enabled mods before and two after.
The destination does not exist yet. The generated files are not game assets.

Apply to the synthetic data using a fresh report name:

```powershell
py -3.12 -B profile_builder.py `
  --source-profile 'D:\MO2-Builder-Example\Original Profile' `
  --destination 'D:\MO2-Builder-Example\Comparison Profile' `
  --disable 'Example Content Mod' `
  --apply --confirm-closed `
  --output 'D:\MO2-Builder-Example\applied.json'
```

Expected: exit `0`, `status: "APPLIED"`, unchanged original files, and three
copied files. Only `+Example Content Mod` changes to `-Example Content Mod`.
`plugins.txt` is **not** copied. BOM, CRLF, row order, other enabled/disabled
markers, and copied settings/archive bytes stay unchanged.

Try `--disable 'Missing Example Mod'` with another new destination to obtain
`requested_mod_missing` and exit `1`. Try applying again to the existing
`Comparison Profile` to obtain `destination_exists` without changing it. An
existing output filename is also refused, so use a fresh report name for each
invocation.

The equivalent Unix-style preview is:

```bash
python3 -B examples/create_example.py /tmp/mo2-builder-example
python3 -B profile_builder.py \
  --source-profile '/tmp/mo2-builder-example/Original Profile' \
  --destination '/tmp/mo2-builder-example/Comparison Profile' \
  --disable 'Example Content Mod' \
  --output /tmp/mo2-builder-example/preview.json
```

Choose a unique local directory if that example path exists. Read the main
[README](../README.md) before using a real profile: saves and game-specific files
are excluded, and the result is not an isolated game copy or proof of gameplay
compatibility.
