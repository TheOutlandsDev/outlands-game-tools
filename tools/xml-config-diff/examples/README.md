# Original toy XML

`create_example.py` creates two tiny XML files written for this MIT utility.
They contain no game data, copied mod settings, actual saves, logs or downloaded
content. Generate into a new local folder outside the downloaded repository
and game folders; no fixture XML files are bundled with the source release.

The files have a `settings` root with three `item` children each. Default `id`
matching pairs the `shared` and `unchanged` items. The candidate changes the
shared item's `slots` attribute and leaf text, removes the `removed` item and
adds an `added` item. Common matched children retain their order.

Follow the [complete Windows/Linux commands](../README.md). Expect a complete
comparison with exit **2**, four changes, four elements per document and three
matched elements. The four changes are `element_added`, `element_removed`,
`attribute_changed` and `text_changed`, one each. By default values are
fingerprints; `--include-values` adds explicit parsed values without exporting
whole added/removed subtrees.

The generator refuses an existing destination and does not clean up after a
partial failure. Delete only your generated folder with your normal file
manager when finished. It does not read, launch or modify any game.
