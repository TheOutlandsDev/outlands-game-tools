# Fictional examples

The built-in desktop demo and [demo-report.json](demo-report.json) are fully
fictional. `simulated: true` means no folder was read. It has three file records,
one nonempty duplicate candidate group and fixed example timestamps. It is
different from the four-file on-disk fixture below.

From the app folder, compile the example generator with the app:

```text
javac -encoding UTF-8 --release 17 -d bin FileAudit.java examples/CreateExample.java
java -cp bin CreateExample ../file-audit-example
```

Choose a **new** example directory under an existing local parent. The generator
creates only that new directory, two subfolders and four fictional input files:

```text
copies/alpha-copy.txt  # same 17 bytes as notes/alpha.txt
notes/alpha.txt
different.txt          # different 17 bytes
empty.txt              # zero bytes; not a duplicate candidate
```

An existing destination is rejected; there is no replacement/merge/delete option.
An I/O error may leave a partial new example directory for manual review.

```text
java -cp bin FileAudit --root ../file-audit-example --output ../file-audit-example-report.json
```

Expected exit: **0**. Expected report summary: four files, 51 observed/hashed
bytes, one candidate group containing the alpha pair, and no issues. The different
same-size file must not join that group. The empty file gets a SHA-256 but no
duplicate group. Real fixture timestamps vary; no absolute input root is exported.

To exercise an incomplete scan without creating large files:

```text
java -cp bin FileAudit --root ../file-audit-example --max-files 1
```

Expected exit: **2**, `status: partial` and a `file_limit` issue. Which file is
visited first can depend on the filesystem, so do not assert a particular first
filename when a limit stops traversal. A partial report is not a complete inventory.

For metadata-only inspection:

```text
java -cp bin FileAudit --root ../file-audit-example --metadata-only
```

Expected: four file records, `bytes_hashed: 0`, null SHA-256 values and no candidate
groups. Input content is not read. All report filenames must be new and outside
the selected input folder; omit `--output` to print JSON only.

Desktop users can select this new example folder, run Start audit and inspect
the Files, Duplicate candidates and Issues tabs. The text filter changes only
displayed rows. Export remains explicit and creates no source-folder files.
