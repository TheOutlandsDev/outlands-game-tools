# Generated X-Ray log example

`create_example.py` creates one small synthetic log at a new local path supplied with `--output`. It does not read the game, real logs, a profile, or configuration. It refuses an existing destination and linked parents. See the [main instructions](../README.md#try-the-generated-example) for Windows and Linux commands.

The example contains these eleven lines:

| Lines | Intended observation |
| --- | --- |
| 1–4 | Startup, session, transport, and connection markers. |
| 5–6 | Two audio warnings with invented asset labels. |
| 7 | One missing treasure-item warning with an invented item label. |
| 8 | One other warning. |
| 9 | One script-error marker. |
| 10 | One fatal-error marker. |
| 11 | One shutdown marker. |

Scanning the example should return **exit 2**, `summary.complete: true`, `lines_read: 11`, `fatal_errors: 1`, `script_errors: 1`, and `warnings: 4`. All five `markers` values should be true. The generated asset/item labels never appear in the summary.

The deliberate error and connection strings are fabricated. They do not reproduce a game failure or verify a transport. No original game log, traceback, credential, address, or binary asset is included. Keep generated `.log` and `.json` files outside the checkout when making a source-only publication.
