# Original generated source example

Run `create_example.py --destination NEW_FOLDER` with an existing local parent
outside the downloaded collection. It creates a new toy `source` directory,
three listed original files, a computed canonical manifest and one harmless
unlisted Markdown file. It copies the collection's MIT notice; no game assets,
actual logs, profiles, saves, third-party implementations or dependency binaries
are included.

The [main README](../README.md#try-the-generated-example) gives PowerShell
commands to build two deterministic ZIPs and compare their hashes. Linux:

```bash
demo="$(mktemp -d)/original-example"
python3 -B create_example.py --destination "$demo"
python3 -B ../source_release.py --source-root "$demo/source" \
  --output "$demo/demo-source.zip" --prefix example-v1.0.0
cd "$demo"
sha256sum -c demo-source.zip.sha256
```

Those commands assume the terminal starts in `tools/source-release-builder/examples`.
For PowerShell, start in the module folder as the main README describes. The
generator must receive a **new** destination; the temporary parent created by
`mktemp -d` is existing and the `original-example` child is new.

Expected builder result: exit 0, three source files, four ZIP members, and no
`unlisted.md` member. Changing a listed generated file while keeping its old
manifest should produce exit 1 and `source_manifest_mismatch`; no newly created
release outputs should remain after normal cleanup. Existing output files are
never replaced.

The generator is a fixture creator, not a secure content inventory generator.
If fixture creation fails after starting, inspect/remove only your generated
example folder with your usual file manager. It does not automatically clean
partial examples or modify any prior folder. Never use it with a real source,
game or save directory.
