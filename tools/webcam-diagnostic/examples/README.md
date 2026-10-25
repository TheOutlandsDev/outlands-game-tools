# Camera-free worked examples

The two JSON files in this folder are authored fictional reports, with fixed
example timestamps and `simulated: true`. They contain no camera recordings,
real device identifiers or real diagnostic receipts. Their FPS/timing values are
illustrative; a running demo uses the host scheduler and will vary slightly.

From the tool folder:

```text
python webcam_diagnostic.py --demo healthy --seconds 2 --output demo-healthy.json
```

Expected: `status: completed`, `simulated: true`, a positive frame count, and exit
0. No camera is opened. A new output file is created only because `--output` was
explicitly supplied. Compare its fields with [healthy.json](healthy.json).

```text
python webcam_diagnostic.py --demo read_failed --seconds 2 --output demo-failure.json
```

Expected: `status: read_failed`, five received fictional frames, one failed read,
`worker_stopped: true`, and exit **2**. This intentionally exercises the failure
path; compare [read_failed.json](read_failed.json). The report does not claim a
driver, cable or hardware cause.

Use a different output name if a file already exists. Without `--output`, the
same metadata is printed to the terminal and no report file is created.

To compare real backends later on Windows, run two separate explicit tests:

```text
python webcam_diagnostic.py --run --backend DSHOW --seconds 30 --output camera-dshow.json
python webcam_diagnostic.py --run --backend MSMF --seconds 30 --output camera-msmf.json
```

Close other camera apps first. Compare actual backend, frame count, elapsed time,
reported modes and observed FPS. Keep requested modes identical when comparing.
Neither an unavailable property nor a completed short test establishes general
device/application compatibility. The desktop app lets you perform and compare
these runs in its latest-20-results table without saving files.
